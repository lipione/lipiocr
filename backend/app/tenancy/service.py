from __future__ import annotations

from datetime import datetime
from typing import Iterable

from fastapi import HTTPException

from app.models import DocumentRecord, KycCase, TemplateProfile
from app.security.rbac import Principal
from app.tenancy.models import Tenant, TenantLifecycleEvent, TenantSettings, TenantUser


class TenantRegistry:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._events: list[TenantLifecycleEvent] = []

    def upsert_tenant(self, tenant: Tenant, *, actor: str = "system") -> Tenant:
        tenant.updated_at = datetime.utcnow()
        self._tenants[tenant.tenant_id] = tenant
        self._events.append(TenantLifecycleEvent(tenant_id=tenant.tenant_id, action="tenant_upserted", actor=actor))
        return tenant

    def update_settings(self, tenant_id: str, settings: TenantSettings, *, actor: str) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        tenant.settings = settings
        tenant.updated_at = datetime.utcnow()
        self._events.append(TenantLifecycleEvent(tenant_id=tenant_id, action="settings_updated", actor=actor))
        return tenant

    def add_user(self, tenant_id: str, user: TenantUser, *, actor: str) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        tenant.users = [item for item in tenant.users if item.user_id != user.user_id]
        tenant.users.append(user)
        tenant.updated_at = datetime.utcnow()
        self._events.append(TenantLifecycleEvent(tenant_id=tenant_id, action="user_upserted", actor=actor))
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant

    def list_tenants(self) -> list[Tenant]:
        return sorted(self._tenants.values(), key=lambda item: item.tenant_id)

    def events(self, tenant_id: str | None = None) -> list[TenantLifecycleEvent]:
        if tenant_id:
            return [event for event in self._events if event.tenant_id == tenant_id]
        return list(self._events)


tenant_registry = TenantRegistry()
tenant_registry.upsert_tenant(Tenant(tenant_id="demo-institution", name="Demo Institution"))


def ensure_principal_can_access_tenant(principal: Principal, tenant_id: str) -> None:
    if principal.role == "system":
        return
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


def filter_cases_for_principal(principal: Principal, cases: Iterable[KycCase]) -> list[KycCase]:
    if principal.role == "system":
        return list(cases)
    return [case for case in cases if case.institution_id == principal.tenant_id]


def filter_documents_for_principal(
    principal: Principal,
    documents: Iterable[DocumentRecord],
    document_tenants: dict[str, str],
) -> list[DocumentRecord]:
    if principal.role == "system":
        return list(documents)
    return [document for document in documents if document_tenants.get(document.id, principal.tenant_id) == principal.tenant_id]


def filter_templates_for_principal(principal: Principal, templates: Iterable[TemplateProfile]) -> list[TemplateProfile]:
    if principal.role == "system":
        return list(templates)
    return [template for template in templates if template.tenant_id == principal.tenant_id]
