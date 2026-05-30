from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.integrations.idempotency import list_delivery_receipts
from app.integrations.sftp_delivery import create_sftp_batch
from app.integrations.webhook_delivery import create_webhook_delivery


WEBHOOK_CONFIGS: List[Dict[str, object]] = []
INTEGRATION_EVENTS: List[Dict[str, object]] = []


def configure_webhook(payload: Dict[str, object]) -> Dict[str, object]:
    webhook = {
        "key": str(payload.get("key") or f"webhook_{len(WEBHOOK_CONFIGS) + 1}"),
        "url": str(payload.get("url") or ""),
        "events": list(payload.get("events") or []),
        "secret_ref": str(payload.get("secret_ref") or "configured-secret"),
        "status": "configured",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    WEBHOOK_CONFIGS[:] = [item for item in WEBHOOK_CONFIGS if item["key"] != webhook["key"]]
    WEBHOOK_CONFIGS.append(webhook)
    return {"webhook": webhook}


def queue_sftp_batch(payload: Dict[str, object]) -> Dict[str, object]:
    event = create_sftp_batch(
        tenant_id=str(payload.get("tenant_id") or "demo-institution"),
        target=str(payload.get("target") or ""),
        profile_key=str(payload.get("profile_key") or "cbs_standard"),
        case_ids=[str(item) for item in list(payload.get("case_ids") or [])],
    )
    event["event_id"] = event["delivery_id"]
    INTEGRATION_EVENTS.append(event)
    return event


def queue_webhook_delivery(payload: Dict[str, object]) -> Dict[str, object]:
    event = create_webhook_delivery(
        tenant_id=str(payload.get("tenant_id") or "demo-institution"),
        url=str(payload.get("url") or ""),
        event=str(payload.get("event") or "case.approved"),
        payload=dict(payload.get("payload") or {}),
        secret=str(payload.get("secret") or "lipiocr-demo-secret"),
    )
    event["event_id"] = event["delivery_id"]
    INTEGRATION_EVENTS.append(event)
    return event


def retry_event(event_id: str) -> Dict[str, object]:
    for event in INTEGRATION_EVENTS:
        if event["event_id"] == event_id:
            event["status"] = "retry_scheduled"
            event["attempts"] = int(event.get("attempts") or 0) + 1
            event["updated_at"] = datetime.utcnow().isoformat() + "Z"
            return {"event": event}
    event = {
        "event_id": event_id,
        "mode": "unknown",
        "status": "retry_scheduled",
        "attempts": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    INTEGRATION_EVENTS.append(event)
    return {"event": event}


def integration_operations() -> Dict[str, object]:
    retry_queue = [event for event in INTEGRATION_EVENTS if event["status"] in {"queued", "failed", "retry_scheduled"}]
    dead_letters = [event for event in INTEGRATION_EVENTS if event["status"] == "dead_letter"]
    return {
        "webhooks": WEBHOOK_CONFIGS,
        "retry_queue": retry_queue,
        "dead_letters": dead_letters,
        "delivery_receipts": list_delivery_receipts(),
        "sftp": {
            "status": "not_configured" if not INTEGRATION_EVENTS else "queued",
            "pending_batches": len(retry_queue),
        },
    }
