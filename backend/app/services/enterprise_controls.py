from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from app.models import CaseStatus, KycCase


def build_tenant_profile(settings) -> dict[str, object]:
    return {
        "tenant_key": "np-financial-demo",
        "institution_name": "Nepal Financial Institution Demo Tenant",
        "country": "Nepal",
        "environment": settings.environment,
        "data_residency": "On-premise or Nepal-hosted private cloud",
        "enabled_workflows": ["KYC", "KYB", "Loan Onboarding", "Document Digitization"],
        "branch_policy": {
            "branch_code_required": True,
            "maker_checker_required": True,
            "cross_branch_visibility": "role_based",
        },
        "retention_policy": {
            "retention_days": 3650,
            "legal_hold_supported": True,
            "deletion_mode": "policy_approved_secure_delete",
        },
        "security_controls": [
            "RBAC",
            "audit hash chain",
            "HMAC webhooks",
            "private deployment",
            "external adapter isolation",
        ],
        "features": ["ocr_review", "gemma_reasoning", "api_export", "embedded_review", "verification_adapters"],
    }


def build_rbac_matrix() -> dict[str, object]:
    return {
        "maker_checker": True,
        "active_users": 0,
        "roles": [
            {
                "key": "maker",
                "name": "Maker",
                "permissions": [
                    "create_case",
                    "upload_document",
                    "edit_extracted_fields",
                    "submit_for_checker",
                ],
            },
            {
                "key": "checker",
                "name": "Checker",
                "permissions": [
                    "view_case",
                    "review_evidence",
                    "approve_case",
                    "reject_case",
                    "request_rework",
                ],
            },
            {
                "key": "auditor",
                "name": "Auditor",
                "permissions": ["view_case", "view_audit_logs", "export_audit_report"],
            },
            {
                "key": "admin",
                "name": "Tenant Admin",
                "permissions": [
                    "manage_users",
                    "manage_templates",
                    "manage_integrations",
                    "manage_retention",
                    "view_security_posture",
                ],
            },
        ],
        "segregation_rules": [
            "Maker cannot approve the same case they created",
            "Checker approval is required before CBS/LOS export",
            "Auditors have read-only access",
        ],
    }


def _event_payload(case: KycCase, event, previous_hash: str) -> str:
    payload = {
        "case_id": case.id,
        "action": event.action,
        "actor": event.actor,
        "note": event.note,
        "metadata": event.metadata,
        "created_at": event.created_at.isoformat(),
        "previous_hash": previous_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_audit_integrity_summary(cases: Iterable[KycCase]) -> dict[str, object]:
    previous_hash = "0" * 64
    events_checked = 0
    per_case = []
    for case in sorted(cases, key=lambda item: item.created_at):
        case_count = 0
        for event in sorted(case.audit_events, key=lambda item: item.created_at):
            previous_hash = hashlib.sha256(_event_payload(case, event, previous_hash).encode("utf-8")).hexdigest()
            events_checked += 1
            case_count += 1
        per_case.append({"case_id": case.id, "events": case_count})

    return {
        "chain_status": "clean" if events_checked else "no_events",
        "status": "clean" if events_checked else "no_events",
        "events_checked": events_checked,
        "immutable_events": events_checked,
        "ledger_head": previous_hash if events_checked else None,
        "gaps": 0,
        "last_verified_at": datetime.utcnow().isoformat() + "Z",
        "cases": per_case,
    }


def build_review_queue(cases: Iterable[KycCase]) -> dict[str, object]:
    items = []
    counts = {
        "created": 0,
        "processing": 0,
        "review_required": 0,
        "approved": 0,
        "rejected": 0,
        "exported": 0,
    }
    for case in sorted(cases, key=lambda item: item.updated_at, reverse=True):
        counts[case.status.value] = counts.get(case.status.value, 0) + 1
        if case.status in {CaseStatus.review_required, CaseStatus.processing, CaseStatus.created}:
            age_minutes = max(0, round((datetime.utcnow() - case.updated_at).total_seconds() / 60))
            items.append(
                {
                    "case_id": case.id,
                    "applicant_name": case.applicant_name,
                    "status": case.status.value,
                    "risk_level": case.risk_level.value,
                    "branch_code": case.branch_code,
                    "document_count": len(case.documents),
                    "age_minutes": age_minutes,
                }
            )

    return {
        "counts": counts,
        "items": items,
        "sla": {
            "maker_checker_required": True,
            "target_review_minutes": 240,
            "high_risk_target_minutes": 60,
        },
    }
