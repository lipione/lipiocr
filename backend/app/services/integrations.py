from __future__ import annotations

import hashlib
import hmac
import json
import os
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app.models import AuditEvent, IntegrationEvent, KycCase


WEBHOOK_SECRET = os.getenv("LIPIOCR_WEBHOOK_SECRET", "lipiocr-demo-secret")
PUBLIC_APP_BASE_URL = os.getenv("LIPIOCR_PUBLIC_APP_BASE_URL", "http://localhost:3000")


def _fields(case: KycCase) -> dict[str, str]:
    return {field.key: field.value for field in case.extracted_fields}


def _confidence(case: KycCase) -> dict[str, float]:
    return {field.key: field.confidence for field in case.extracted_fields}


def list_integration_profiles() -> dict[str, Any]:
    return {
        "product": "LipiOCR Enterprise Integration Kit",
        "country": "Nepal",
        "profiles": [
            {
                "key": "manual_export",
                "name": "Manual JSON/CSV Export",
                "category": "operations",
                "mode": "download",
                "status": "configured",
                "description": "Maker/checker export for institutions without live API access.",
            },
            {
                "key": "rest_api",
                "name": "REST API",
                "category": "system_integration",
                "mode": "pull",
                "status": "configured",
                "description": "CBS, LOS, CRM, and document-management systems can fetch approved case payloads.",
            },
            {
                "key": "webhooks",
                "name": "Signed Webhooks",
                "category": "eventing",
                "mode": "push",
                "status": "configured",
                "description": "HMAC-signed case lifecycle events for downstream workflow triggers.",
            },
            {
                "key": "sftp",
                "name": "SFTP Batch Drop",
                "category": "batch",
                "mode": "batch",
                "status": "not_configured",
                "description": "Nightly encrypted packet delivery for legacy back-office systems.",
            },
            {
                "key": "embedded_review",
                "name": "Embedded Review Link",
                "category": "workflow",
                "mode": "iframe_or_link",
                "status": "configured",
                "description": "Open LipiOCR review inside a financial institution portal.",
            },
            {
                "key": "cbs_standard",
                "name": "CBS Standard Customer Export",
                "category": "export_profile",
                "mode": "json_mapping",
                "status": "configured",
                "description": "Core banking customer-master payload for approved KYC records.",
            },
            {
                "key": "los_loan",
                "name": "Loan Origination Export",
                "category": "export_profile",
                "mode": "json_mapping",
                "status": "configured",
                "description": "Borrower and exception payload for loan onboarding systems.",
            },
            {
                "key": "aml_case",
                "name": "AML Case Export",
                "category": "export_profile",
                "mode": "json_mapping",
                "status": "configured",
                "description": "Subject and source-document payload for AML screening workflows.",
            },
        ],
        "export_profiles": ["cbs_standard", "los_loan", "aml_case"],
        "events": [
            "case.created",
            "document.processed",
            "review.required",
            "case.approved",
            "case.rejected",
            "verification.completed",
            "export.completed",
        ],
        "security": {
            "webhook_signature": "HMAC-SHA256",
            "transport": "HTTPS or private network",
            "auth": ["API key", "mTLS-ready reverse proxy", "SSO/OIDC adapter"],
        },
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _signature(payload: dict[str, Any], secret: str = WEBHOOK_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), _canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_webhook_test_payload(case: KycCase, event: str = "case.approved") -> dict[str, Any]:
    payload = {
        "event": event,
        "event_id": f"evt_{case.id}_{event.replace('.', '_')}",
        "case_id": case.id,
        "status": case.status.value,
        "institution_id": case.institution_id,
        "branch_code": case.branch_code,
        "integration_ref": case.integration_ref,
        "occurred_at": "2026-05-27T00:00:00Z",
        "customer": {
            "name": case.applicant_name,
            "reference": case.integration_ref,
        },
    }
    case.integration_events.append(
        IntegrationEvent(mode="webhook", status="test_generated", target=event)
    )
    case.audit_events.append(
        AuditEvent(action="webhook_test_generated", actor="integration-kit", note=event)
    )
    return {
        "status": "signed",
        "event_id": payload["event_id"],
        "signature": _signature(payload),
        "payload": payload,
        "headers": {
            "X-LipiOCR-Event": event,
            "X-LipiOCR-Signature": _signature(payload),
        },
    }


def build_embedded_review_link(case: KycCase, settings) -> dict[str, Any]:
    expires_at = datetime.utcnow() + timedelta(hours=4)
    token_payload = f"{case.id}:{case.integration_ref or ''}:{int(expires_at.timestamp())}"
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), token_payload.encode("utf-8"), hashlib.sha256).digest()
    token = urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    base_url = PUBLIC_APP_BASE_URL.rstrip("/")
    url = f"{base_url}/review/{case.id}?token={token}"
    case.integration_events.append(
        IntegrationEvent(mode="embedded_review", status="link_generated", target=url)
    )
    case.audit_events.append(
        AuditEvent(action="embedded_review_link_generated", actor="integration-kit", note="4 hour review link")
    )
    return {
        "case_id": case.id,
        "url": url,
        "review_url": url,
        "token": token,
        "expires_at": expires_at.isoformat() + "Z",
        "environment": settings.environment,
    }


def build_export_profile(case: KycCase, profile_key: str) -> dict[str, Any]:
    fields = _fields(case)
    confidence = _confidence(case)
    base_customer = {
        "reference": case.integration_ref,
        "name": fields.get("full_name") or case.applicant_name,
        "mobile": fields.get("mobile", ""),
        "email": fields.get("email", ""),
        "citizenship_number": fields.get("citizenship_number", ""),
        "pan_number": fields.get("pan_number") or fields.get("pan", ""),
    }

    if profile_key == "cbs_standard":
        payload = {
            "customer": base_customer,
            "branch": {"code": case.branch_code, "institution_id": case.institution_id},
            "kyc": {
                "case_id": case.id,
                "case_type": case.case_type.value,
                "status": case.status.value,
                "risk_level": case.risk_level.value,
                "field_confidence": confidence,
            },
            "documents": [
                {
                    "document_id": document.id,
                    "type": document.document_type.value,
                    "filename": document.filename,
                    "page_count": document.page_count,
                }
                for document in case.documents
            ],
        }
    elif profile_key == "los_loan":
        payload = {
            "borrower": base_customer,
            "loan_onboarding": {
                "case_id": case.id,
                "risk_level": case.risk_level.value,
                "income_documents": [
                    document.id for document in case.documents if document.document_type.value == "bank_statement"
                ],
            },
            "exceptions": [
                finding.model_dump(mode="json") for finding in case.validation_findings if finding.severity == "error"
            ],
        }
    elif profile_key == "aml_case":
        payload = {
            "subject": base_customer,
            "screening_context": {
                "country": "Nepal",
                "case_id": case.id,
                "institution_id": case.institution_id,
                "branch_code": case.branch_code,
            },
            "source_documents": [
                {"document_id": document.id, "type": document.document_type.value} for document in case.documents
            ],
        }
    else:
        raise HTTPException(status_code=404, detail="Unknown export profile")

    case.integration_events.append(
        IntegrationEvent(mode="export_profile", status="generated", target=profile_key)
    )
    case.audit_events.append(
        AuditEvent(action="export_profile_generated", actor="integration-kit", note=profile_key)
    )
    return {
        "case_id": case.id,
        "profile_key": profile_key,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "payload": payload,
    }
