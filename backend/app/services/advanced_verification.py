from __future__ import annotations

from datetime import datetime
from typing import Iterable

from app.models import AuditEvent, KycCase


def _all_text(case: KycCase) -> str:
    return "\n".join(
        block.text
        for document in case.documents
        for page in document.pages
        for block in page.blocks
        if block.text
    ).lower()


def _field(case: KycCase, key: str) -> str:
    for field in case.extracted_fields:
        if field.key == key:
            return field.value
    return ""


def _check(key: str, label: str, status: str, message: str, next_step: str, severity: str = "warning") -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "severity": severity,
        "message": message,
        "next_step": next_step,
    }


def run_verification(case: KycCase, all_cases: Iterable[KycCase]) -> dict[str, object]:
    text = _all_text(case)
    citizenship_number = _field(case, "citizenship_number")
    duplicate_cases = [
        item.id
        for item in all_cases
        if item.id != case.id
        and citizenship_number
        and any(field.key == "citizenship_number" and field.value == citizenship_number for field in item.extracted_fields)
    ]
    has_signature = "signature" in text or "thumbprint" in text or "fingerprint" in text
    has_photo = "photo" in text or "photograph" in text
    tamper_terms = ("overwritten", "tampered", "blurred", "cut paste", "mismatch")
    tamper_detected = any(term in text for term in tamper_terms)

    checks = [
        _check(
            "national_id_registry",
            "National ID / citizenship registry",
            "not_configured",
            "Live Government of Nepal identity registry access is not configured for this demo tenant.",
            "Connect institution-approved registry adapter or keep manual checker verification.",
        ),
        _check(
            "pan_registry",
            "PAN registry",
            "not_configured",
            "IRD/PAN online verification requires institution credentials and adapter approval.",
            "Configure PAN adapter for tax-profile verification.",
        ),
        _check(
            "aml_screening",
            "AML and sanctions screening",
            "not_configured",
            "Sanctions, PEP, adverse media, and FIU/goAML workflows are adapter boundaries.",
            "Connect the institution AML provider and define match escalation thresholds.",
        ),
        _check(
            "face_liveness",
            "Face match and liveness",
            "not_configured",
            "Liveness and selfie match are outside OCR and require a biometric provider.",
            "Integrate approved liveness provider for digital onboarding.",
        ),
        _check(
            "document_tamper",
            "Document tamper signals",
            "needs_review" if tamper_detected else "passed",
            "OCR text contains tamper-like wording." if tamper_detected else "No deterministic tamper terms found in OCR text.",
            "Route to manual forensic review." if tamper_detected else "Continue with normal checker review.",
            "error" if tamper_detected else "info",
        ),
        _check(
            "signature_presence",
            "Signature/photo presence",
            "passed" if has_signature or has_photo else "needs_review",
            "Signature or photo signal found in the OCR packet."
            if has_signature or has_photo
            else "No signature/photo signal was found in OCR text.",
            "Checker should visually inspect signature/photo crop before approval.",
            "info" if has_signature or has_photo else "warning",
        ),
        _check(
            "duplicate_case",
            "Duplicate KYC case",
            "needs_review" if duplicate_cases else "passed",
            f"Possible duplicate cases: {', '.join(duplicate_cases)}"
            if duplicate_cases
            else "No duplicate citizenship number found in the in-memory case set.",
            "Merge or reject duplicate applications." if duplicate_cases else "No action required.",
            "warning" if duplicate_cases else "info",
        ),
    ]

    blocking = [check for check in checks if check["severity"] == "error"]
    not_configured = [check for check in checks if check["status"] == "not_configured"]
    next_steps = [
        "Complete checker review before export",
        "Configure registry/AML/liveness adapters for production deployment",
    ]
    if blocking:
        next_steps.insert(0, "Resolve blocking verification signals")

    case.audit_events.append(
        AuditEvent(
            action="advanced_verification_run",
            actor="verification-orchestrator",
            note=f"{len(not_configured)} external adapter(s) not configured",
        )
    )
    return {
        "case_id": case.id,
        "run_id": f"verify_{case.id}",
        "status": "review_required" if blocking or not_configured else "passed",
        "decision": "manual_review",
        "score": 72 if not_configured else 91,
        "checks": checks,
        "findings": [],
        "next_steps": next_steps,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "case": case,
    }
