from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integrations.idempotency import build_idempotency_key, remember_delivery


def create_sftp_batch(
    *,
    tenant_id: str,
    target: str,
    profile_key: str,
    case_ids: list[str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = payload or {"profile_key": profile_key, "case_ids": case_ids}
    key = build_idempotency_key(tenant_id=tenant_id, target=f"sftp:{target}:{profile_key}", payload=body)
    receipt = {
        "delivery_id": f"sftp_{key.removeprefix('idem_')}",
        "mode": "sftp",
        "tenant_id": tenant_id,
        "target": target,
        "profile_key": profile_key,
        "case_ids": case_ids,
        "status": "queued",
        "attempts": 0,
        "payload": body,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "last_error": "Awaiting SFTP credential configuration",
    }
    created, stored = remember_delivery(key, receipt)
    return {**stored, "duplicate": not created}
