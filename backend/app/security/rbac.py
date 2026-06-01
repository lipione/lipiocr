from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from fastapi import HTTPException

from app.security.sessions import SessionPrincipal


MAKER_PERMISSIONS = {"create_case", "upload_document", "edit_fields", "submit_review", "view_case"}
CHECKER_PERMISSIONS = {"view_case", "review_case", "approve_case", "reject_case", "export_case"}
AUDITOR_PERMISSIONS = {"view_case", "view_audit", "export_audit", "export_case"}
TENANT_ADMIN_PERMISSIONS = (
    MAKER_PERMISSIONS
    | CHECKER_PERMISSIONS
    | AUDITOR_PERMISSIONS
    | {"admin", "manage_templates", "manage_integrations"}
)
SUPER_ADMIN_PERMISSIONS = TENANT_ADMIN_PERMISSIONS | {"manage_system_templates"}

ROLE_PERMISSIONS: Dict[str, set[str]] = {
    "maker": {"create_case", "upload_document", "edit_fields", "submit_review", "view_case"},
    "checker": {"view_case", "review_case", "approve_case", "reject_case", "export_case"},
    "auditor": {"view_case", "view_audit", "export_audit", "export_case"},
    "admin": TENANT_ADMIN_PERMISSIONS,
    "super_admin": SUPER_ADMIN_PERMISSIONS,
    "system": TENANT_ADMIN_PERMISSIONS,
}


@dataclass(frozen=True)
class Principal:
    role: str
    user_id: str
    tenant_id: str
    branch_code: Optional[str]
    auth_method: str
    api_key_fingerprint: Optional[str] = None

    @classmethod
    def from_session(cls, principal: SessionPrincipal) -> "Principal":
        return cls(
            role=principal.role,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            branch_code=principal.branch_code,
            auth_method=principal.auth_method,
        )


def has_permission_for_principal(principal: Principal, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(principal.role, set())
    return "*" in permissions or permission in permissions


def can_manage_system_templates(principal: Principal) -> bool:
    if principal.role == "system" and principal.auth_method == "disabled":
        return True
    return has_permission_for_principal(principal, "manage_system_templates")


def require_permission_for_principal(principal: Principal, permission: str) -> Principal:
    if not has_permission_for_principal(principal, permission):
        raise HTTPException(status_code=403, detail=f"Role {principal.role} lacks {permission}")
    return principal


def require_any_permission_for_principal(principal: Principal, permissions: set[str]) -> Principal:
    principal_permissions = ROLE_PERMISSIONS.get(principal.role, set())
    if "*" in principal_permissions or principal_permissions.intersection(permissions):
        return principal
    raise HTTPException(status_code=403, detail=f"Role {principal.role} lacks required permission")
