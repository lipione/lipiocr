from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, Request

from app.security.rbac import (
    ROLE_PERMISSIONS,
    Principal,
    require_any_permission_for_principal,
    require_permission_for_principal,
)
from app.security.sessions import session_store_from_settings


def _api_key_map(api_keys: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for raw_item in api_keys.split(","):
        item = raw_item.strip()
        if not item:
            continue
        key, _, role = item.partition(":")
        mapping[key.strip()] = (role or "maker").strip()
    return mapping


def _fingerprint(api_key: str) -> str:
    return f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "short-key"


def _bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _session_token(settings, request: Request) -> str:
    cookie_name = getattr(settings, "session_cookie_name", "lipiocr_session")
    return request.cookies.get(cookie_name, "") or _bearer_token(request)


def _api_key(request: Request) -> str:
    return request.headers.get("X-LipiOCR-API-Key", "") or _bearer_token(request)


def resolve_principal(settings, request: Request) -> Principal:
    default_tenant_id = getattr(settings, "default_tenant_id", "demo-institution")
    if not settings.api_auth_enabled:
        return Principal(
            role="system",
            user_id="auth-disabled",
            tenant_id=default_tenant_id,
            branch_code=None,
            auth_method="disabled",
            api_key_fingerprint="auth-disabled",
        )

    session_token = _session_token(settings, request)
    session_principal = session_store_from_settings(settings).verify(session_token)
    if session_principal is not None:
        return Principal.from_session(session_principal)

    api_key = _api_key(request)
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing operator session")

    role = _api_key_map(settings.api_keys).get(api_key)
    if role is None:
        raise HTTPException(status_code=401, detail="Invalid operator credentials")

    fingerprint = _fingerprint(api_key)
    return Principal(
        role=role,
        user_id=f"api-key:{fingerprint}",
        tenant_id=default_tenant_id if role != "system" else "system",
        branch_code=None,
        auth_method="api_key",
        api_key_fingerprint=fingerprint,
    )


def require_permission(settings, request: Request, permission: str) -> Principal:
    return require_permission_for_principal(resolve_principal(settings, request), permission)


def require_any_permission(settings, request: Request, permissions: set[str]) -> Principal:
    return require_any_permission_for_principal(resolve_principal(settings, request), permissions)
