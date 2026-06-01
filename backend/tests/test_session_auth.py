from datetime import timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.app_context import settings
from app.main import app
from app.security.rbac import Principal, require_permission_for_principal
from app.security.sessions import InMemorySessionStore, SessionPrincipal, session_store_from_settings


def test_session_token_round_trip_and_revoke():
    store = InMemorySessionStore(secret="test-secret", ttl_seconds=3600)
    principal = SessionPrincipal(
        user_id="maker.one",
        role="maker",
        tenant_id="nmb-bank",
        branch_code="KTM-01",
        auth_method="session",
    )

    token = store.create(principal)
    assert store.verify(token) == principal

    store.revoke(token)
    assert store.verify(token) is None


def test_session_token_expires():
    store = InMemorySessionStore(secret="test-secret", ttl_seconds=1)
    token = store.create(
        SessionPrincipal(
            user_id="checker.one",
            role="checker",
            tenant_id="global",
            branch_code=None,
            auth_method="session",
        )
    )
    store._sessions[token].expires_at = store._sessions[token].issued_at - timedelta(seconds=1)

    assert store.verify(token) is None


def test_maker_cannot_approve_case():
    principal = Principal(
        role="maker",
        user_id="maker.one",
        tenant_id="nmb-bank",
        branch_code="KTM-01",
        auth_method="session",
    )

    try:
        require_permission_for_principal(principal, "approve_case")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("maker approval should fail")


def test_admin_can_manage_templates():
    principal = Principal(
        role="admin",
        user_id="admin.one",
        tenant_id="nmb-bank",
        branch_code=None,
        auth_method="session",
    )

    assert require_permission_for_principal(principal, "manage_templates") == principal


def test_only_super_admin_can_manage_system_templates():
    admin = Principal(
        role="admin",
        user_id="admin.one",
        tenant_id="nmb-bank",
        branch_code=None,
        auth_method="session",
    )
    super_admin = Principal(
        role="super_admin",
        user_id="root.one",
        tenant_id="nmb-bank",
        branch_code=None,
        auth_method="session",
    )

    try:
        require_permission_for_principal(admin, "manage_system_templates")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("tenant admin should not revise permanent system templates")

    assert require_permission_for_principal(super_admin, "manage_system_templates") == super_admin


def test_operator_session_can_access_cases():
    original_enabled = settings.api_auth_enabled
    try:
        settings.api_auth_enabled = True
        client = TestClient(app)

        login = client.post(
            "/api/auth/session",
            json={"username": "maker.one", "role": "maker", "tenant_id": "nmb-bank", "branch_code": "KTM-01"},
        )

        assert login.status_code == 201
        assert login.json()["principal"]["tenant_id"] == "nmb-bank"
        assert client.get("/api/cases").status_code == 200
    finally:
        settings.api_auth_enabled = original_enabled


def test_operator_session_binds_created_case_to_session_tenant():
    original_enabled = settings.api_auth_enabled
    try:
        settings.api_auth_enabled = True
        client = TestClient(app)

        login = client.post(
            "/api/auth/session",
            json={"username": "maker.other", "role": "maker", "tenant_id": "other-bank"},
        )
        create = client.post(
            "/api/cases",
            json={
                "case_type": "individual_kyc",
                "applicant_name": "Tenant Bound Customer",
                "institution_id": "demo-institution",
            },
        )

        assert login.status_code == 201
        assert create.status_code == 201
        assert create.json()["institution_id"] == "other-bank"
    finally:
        settings.api_auth_enabled = original_enabled


def test_super_admin_operator_session_is_supported():
    original_enabled = settings.api_auth_enabled
    try:
        settings.api_auth_enabled = True
        client = TestClient(app)

        login = client.post(
            "/api/auth/session",
            json={"username": "root.one", "role": "super_admin", "tenant_id": "nmb-bank"},
        )

        assert login.status_code == 201
        assert login.json()["principal"]["role"] == "super_admin"
    finally:
        settings.api_auth_enabled = original_enabled


def test_logout_revokes_operator_session():
    original_enabled = settings.api_auth_enabled
    store = session_store_from_settings(settings)
    try:
        settings.api_auth_enabled = True
        client = TestClient(app)
        assert client.post("/api/auth/session", json={"username": "maker.one"}).status_code == 201

        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/cases").status_code == 401
    finally:
        settings.api_auth_enabled = original_enabled
        for token in list(store._sessions):
            store.revoke(token)


def test_api_key_auth_still_works_for_integrations():
    original_enabled = settings.api_auth_enabled
    original_keys = settings.api_keys
    try:
        settings.api_auth_enabled = True
        settings.api_keys = "integration-secret:system"
        client = TestClient(app)

        response = client.get("/api/cases", headers={"X-LipiOCR-API-Key": "integration-secret"})

        assert response.status_code == 200
    finally:
        settings.api_auth_enabled = original_enabled
        settings.api_keys = original_keys
