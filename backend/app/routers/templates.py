from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Body, Request

from app.app_context import settings
from app.services.security import require_permission, resolve_principal
from app.services.template_profiles import (
    approve_template_profile,
    export_template_profile,
    get_template_profile,
    import_template_profile,
    list_template_profiles,
    rollback_template_profile,
)
from app.services.template_testing import test_template_profile


router = APIRouter(prefix="/api/admin/templates", tags=["templates"])


@router.get("/profiles")
def template_profiles(http_request: Request):
    principal = require_permission(settings, http_request, "view_audit")
    return {
        "profiles": [profile.model_dump(mode="json") for profile in list_template_profiles(tenant_id=principal.tenant_id)]
    }


@router.post("/profiles/{profile_id}/approve")
def approve_template(profile_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = require_permission(settings, http_request, "manage_templates")
    actor = str(payload.get("actor") or principal.user_id)
    return {"profile": approve_template_profile(profile_id, actor=actor)}


@router.post("/profiles/{profile_id}/rollback")
def rollback_template(profile_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = require_permission(settings, http_request, "manage_templates")
    target_version = int(payload.get("target_version") or 1)
    return {"profile": rollback_template_profile(profile_id, target_version=target_version, actor=principal.user_id)}


@router.get("/profiles/{profile_id}/export")
def export_template(profile_id: str, http_request: Request):
    require_permission(settings, http_request, "manage_templates")
    return export_template_profile(profile_id)


@router.post("/profiles/import", status_code=201)
def import_template(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    principal = require_permission(settings, http_request, "manage_templates")
    return {"profile": import_template_profile(payload, tenant_id=principal.tenant_id, actor=principal.user_id)}


@router.post("/profiles/{profile_id}/test")
def test_template(profile_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    require_permission(settings, http_request, "manage_templates")
    profile = get_template_profile(profile_id)
    fields = list(payload.get("fields") or [])
    return {"result": test_template_profile(profile, fields)}
