from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from fastapi import HTTPException, Request


ROLE_PERMISSIONS: Dict[str, set[str]] = {
    "maker": {"create_case", "upload_document", "edit_fields", "submit_review", "view_case"},
    "checker": {"view_case", "review_case", "approve_case", "reject_case", "export_case"},
    "auditor": {"view_case", "view_audit", "export_audit"},
    "admin": {"*"},
    "system": {"*"},
}


@dataclass(frozen=True)
class Principal:
    role: str
    api_key_fingerprint: str


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


def resolve_principal(settings, request: Request) -> Principal:
    if not settings.api_auth_enabled:
        return Principal(role="system", api_key_fingerprint="auth-disabled")

    api_key = request.headers.get("X-LipiOCR-API-Key", "")
    auth_header = request.headers.get("Authorization", "")
    if not api_key and auth_header.lower().startswith("bearer "):
        api_key = auth_header[7:].strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    role = _api_key_map(settings.api_keys).get(api_key)
    if role is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return Principal(role=role, api_key_fingerprint=_fingerprint(api_key))


def require_permission(settings, request: Request, permission: str) -> Principal:
    principal = resolve_principal(settings, request)
    permissions = ROLE_PERMISSIONS.get(principal.role, set())
    if "*" not in permissions and permission not in permissions:
        raise HTTPException(status_code=403, detail=f"Role {principal.role} lacks {permission}")
    return principal
