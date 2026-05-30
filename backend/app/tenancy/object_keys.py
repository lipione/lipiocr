from __future__ import annotations

import re


def safe_tenant_segment(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    normalized = normalized.replace("..", ".").strip(".-")
    if not normalized:
        raise ValueError("tenant segment is required")
    return normalized[:80]


def tenant_object_key(*, tenant_id: str, category: str, object_id: str, filename: str | None = None) -> str:
    parts = [
        "tenants",
        safe_tenant_segment(tenant_id),
        safe_tenant_segment(category),
        safe_tenant_segment(object_id),
    ]
    if filename:
        parts.append(safe_tenant_segment(filename))
    return "/".join(parts)


def object_key_belongs_to_tenant(key: str, tenant_id: str) -> bool:
    return key.startswith(f"tenants/{safe_tenant_segment(tenant_id)}/")
