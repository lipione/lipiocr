from __future__ import annotations

from datetime import datetime
from typing import Dict

from app.models import AuditEvent, KycCase


ADAPTERS: Dict[str, Dict[str, object]] = {
    "national_id_registry": {
        "key": "national_id_registry",
        "label": "National ID / Citizenship Registry",
        "status": "not_configured",
        "mode": "manual",
    },
    "pan_registry": {
        "key": "pan_registry",
        "label": "PAN / IRD Registry",
        "status": "not_configured",
        "mode": "manual",
    },
    "aml_screening": {
        "key": "aml_screening",
        "label": "AML / Sanctions Screening",
        "status": "not_configured",
        "mode": "manual",
    },
    "face_liveness": {
        "key": "face_liveness",
        "label": "Face Match / Liveness",
        "status": "not_configured",
        "mode": "manual",
    },
}


def list_adapters() -> Dict[str, object]:
    return {"adapters": list(ADAPTERS.values())}


def configure_adapter(adapter_key: str, payload: Dict[str, object]) -> Dict[str, object]:
    adapter = ADAPTERS.setdefault(
        adapter_key,
        {"key": adapter_key, "label": adapter_key.replace("_", " ").title(), "status": "not_configured"},
    )
    adapter.update(
        {
            "status": "configured" if payload.get("enabled", True) else "disabled",
            "mode": str(payload.get("mode") or "sandbox"),
            "endpoint": payload.get("endpoint"),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    return {"adapter": adapter}


def run_adapter(case: KycCase, adapter_key: str) -> Dict[str, object]:
    adapter = ADAPTERS.get(adapter_key)
    if adapter is None:
        adapter = configure_adapter(adapter_key, {"enabled": False})["adapter"]
    configured = adapter.get("status") == "configured"
    status = "passed" if configured else "not_configured"
    if adapter_key == "pan_registry" and configured:
        has_pan_doc = any(document.document_type.value == "pan" for document in case.documents)
        status = "passed" if has_pan_doc else "needs_review"
    check = {
        "key": adapter_key,
        "label": adapter.get("label", adapter_key),
        "status": status,
        "severity": "info" if status == "passed" else "warning",
        "message": "Adapter configured; sandbox decision generated."
        if configured
        else "Adapter requires institution credentials before live verification.",
        "next_step": "Review sandbox result before production rollout." if configured else "Configure adapter credentials.",
    }
    case.audit_events.append(
        AuditEvent(
            action="verification_adapter_run",
            actor="verification-registry",
            note=str(check["message"]),
            metadata={"adapter_key": adapter_key, "check": check},
        )
    )
    return {"case_id": case.id, "adapter": adapter, "check": check, "case": case}
