from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models import CaseType, KycCase, TemplateProfile
from app.security.rbac import Principal
from app.tenancy.models import Tenant, TenantSettings, TenantUser
from app.tenancy.service import (
    ensure_principal_can_access_tenant,
    filter_cases_for_principal,
    filter_templates_for_principal,
    tenant_registry,
)


client = TestClient(app)


def test_cross_tenant_access_is_denied_for_operator_principal():
    principal = Principal(
        role="admin",
        user_id="admin.a",
        tenant_id="tenant-a",
        branch_code=None,
        auth_method="session",
    )

    try:
        ensure_principal_can_access_tenant(principal, "tenant-b")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("cross-tenant access should fail")


def test_cases_and_templates_are_filtered_by_tenant():
    principal = Principal(role="maker", user_id="maker.a", tenant_id="tenant-a", branch_code=None, auth_method="session")
    cases = [
        KycCase(case_type=CaseType.individual_kyc, applicant_name="A", institution_id="tenant-a"),
        KycCase(case_type=CaseType.individual_kyc, applicant_name="B", institution_id="tenant-b"),
    ]
    templates = [
        TemplateProfile(name="A Template", tenant_id="tenant-a"),
        TemplateProfile(name="B Template", tenant_id="tenant-b"),
    ]

    assert [case.applicant_name for case in filter_cases_for_principal(principal, cases)] == ["A"]
    assert [template.name for template in filter_templates_for_principal(principal, templates)] == ["A Template"]


def test_tenant_admin_can_manage_settings_users_roles_retention_and_exports():
    tenant_registry.upsert_tenant(Tenant(tenant_id="tenant-admin-test", name="Tenant Admin Test"))
    tenant = tenant_registry.update_settings(
        "tenant-admin-test",
        TenantSettings(retention_days=365, allowed_export_profiles=["cbs_standard"]),
        actor="admin",
    )
    tenant = tenant_registry.add_user(
        "tenant-admin-test",
        TenantUser(user_id="maker.one", role="maker", branch_code="KTM-01"),
        actor="admin",
    )

    assert tenant.settings.retention_days == 365
    assert tenant.settings.allowed_export_profiles == ["cbs_standard"]
    assert tenant.users[0].role == "maker"


def test_tenant_admin_api_lists_tenants():
    tenant_registry.upsert_tenant(Tenant(tenant_id="tenant-api-test", name="Tenant API Test"))

    response = client.get("/api/admin/tenants")

    assert response.status_code == 200
    assert any(tenant["tenant_id"] == "tenant-api-test" for tenant in response.json()["tenants"])
