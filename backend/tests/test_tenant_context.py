from fastapi import HTTPException

from app.security.rbac import Principal
from app.security.tenant_context import TenantContext, context_from_principal, ensure_tenant_match


def test_context_contains_user_role_tenant_and_branch():
    principal = Principal(
        role="checker",
        user_id="checker.one",
        tenant_id="nic-asia",
        branch_code="NPR-22",
        auth_method="session",
    )

    assert context_from_principal(principal) == TenantContext(
        tenant_id="nic-asia",
        branch_code="NPR-22",
        user_id="checker.one",
        role="checker",
        auth_method="session",
    )


def test_cross_tenant_access_is_rejected():
    context = TenantContext(
        tenant_id="tenant-a",
        branch_code=None,
        user_id="maker.one",
        role="maker",
        auth_method="session",
    )

    try:
        ensure_tenant_match(context, "tenant-b")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("cross tenant access should fail")


def test_system_context_can_cross_tenant_for_integrations():
    context = TenantContext(
        tenant_id="system",
        branch_code=None,
        user_id="api-key",
        role="system",
        auth_method="api_key",
    )

    assert ensure_tenant_match(context, "tenant-b") == context
