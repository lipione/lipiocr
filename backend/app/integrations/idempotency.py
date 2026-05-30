from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


_IDEMPOTENCY_STORE: dict[str, dict[str, Any]] = {}


def build_idempotency_key(*, tenant_id: str, target: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(f"{tenant_id}:{target}:{canonical}".encode("utf-8")).hexdigest()[:24]
    return f"idem_{digest}"


def remember_delivery(key: str, receipt: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    existing = _IDEMPOTENCY_STORE.get(key)
    if existing is not None:
        return False, existing
    stored = {**receipt, "idempotency_key": key, "created_at": datetime.utcnow().isoformat() + "Z"}
    _IDEMPOTENCY_STORE[key] = stored
    return True, stored


def get_delivery_receipt(key: str) -> dict[str, Any] | None:
    return _IDEMPOTENCY_STORE.get(key)


def list_delivery_receipts() -> list[dict[str, Any]]:
    return list(_IDEMPOTENCY_STORE.values())
