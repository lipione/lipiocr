from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from app.integrations.idempotency import build_idempotency_key, remember_delivery


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def create_webhook_delivery(
    *,
    tenant_id: str,
    url: str,
    event: str,
    payload: dict[str, Any],
    secret: str,
) -> dict[str, Any]:
    key = build_idempotency_key(tenant_id=tenant_id, target=f"webhook:{url}:{event}", payload=payload)
    receipt = {
        "delivery_id": f"wh_{key.removeprefix('idem_')}",
        "mode": "webhook",
        "tenant_id": tenant_id,
        "target": url,
        "event": event,
        "status": "queued",
        "attempts": 0,
        "signature": sign_payload(payload, secret),
        "headers": {
            "X-LipiOCR-Event": event,
            "X-LipiOCR-Idempotency-Key": key,
            "X-LipiOCR-Signature": sign_payload(payload, secret),
        },
        "payload": payload,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    created, stored = remember_delivery(key, receipt)
    return {**stored, "duplicate": not created}


def mark_delivery_attempt(receipt: dict[str, Any], *, status: str, error: str = "") -> dict[str, Any]:
    receipt["attempts"] = int(receipt.get("attempts") or 0) + 1
    receipt["status"] = status
    receipt["last_error"] = error
    receipt["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return receipt
