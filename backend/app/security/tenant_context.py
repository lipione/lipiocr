from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

from app.security.rbac import Principal


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    branch_code: Optional[str]
    user_id: str
    role: str
    auth_method: str


def context_from_principal(principal: Principal) -> TenantContext:
    return TenantContext(
        tenant_id=principal.tenant_id,
        branch_code=principal.branch_code,
        user_id=principal.user_id,
        role=principal.role,
        auth_method=principal.auth_method,
    )


def ensure_tenant_match(context: TenantContext, tenant_id: str | None) -> TenantContext:
    if not tenant_id or context.role == "system":
        return context
    if context.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context does not match requested resource")
    return context
