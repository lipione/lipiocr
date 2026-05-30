from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Body, Request

from app.app_context import settings
from app.services.security import require_permission, resolve_principal
from app.tenancy.models import Tenant, TenantSettings, TenantUser
from app.tenancy.service import ensure_principal_can_access_tenant, tenant_registry


router = APIRouter(prefix="/api/admin/tenants", tags=["tenants"])


@router.get("")
def list_tenants(http_request: Request):
    require_permission(settings, http_request, "view_audit")
    return {"tenants": [tenant.model_dump(mode="json") for tenant in tenant_registry.list_tenants()]}


@router.post("", status_code=201)
def upsert_tenant(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = require_permission(settings, http_request, "manage_integrations")
    tenant = Tenant(
        tenant_id=str(payload.get("tenant_id") or ""),
        name=str(payload.get("name") or payload.get("tenant_id") or ""),
        status=str(payload.get("status") or "active"),
    )
    return {"tenant": tenant_registry.upsert_tenant(tenant, actor=principal.user_id).model_dump(mode="json")}


@router.patch("/{tenant_id}/settings")
def update_tenant_settings(tenant_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = resolve_principal(settings, http_request)
    require_permission(settings, http_request, "manage_integrations")
    ensure_principal_can_access_tenant(principal, tenant_id)
    settings_update = TenantSettings.model_validate(payload)
    return {
        "tenant": tenant_registry.update_settings(tenant_id, settings_update, actor=principal.user_id).model_dump(mode="json")
    }


@router.post("/{tenant_id}/users", status_code=201)
def upsert_tenant_user(tenant_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = resolve_principal(settings, http_request)
    require_permission(settings, http_request, "manage_integrations")
    ensure_principal_can_access_tenant(principal, tenant_id)
    user = TenantUser.model_validate(payload)
    return {"tenant": tenant_registry.add_user(tenant_id, user, actor=principal.user_id).model_dump(mode="json")}
