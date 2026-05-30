# Production Readiness Phase 4 Security Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace browser-stored operator API keys with operator sessions, tenant-aware request context, RBAC, and enforced upload policy while preserving API-key support for integrations.

**Architecture:** Keep the public FastAPI route surface stable and add a focused `app.security` package for session auth, RBAC, tenant context, and upload validation. The existing `app.services.security` module remains a compatibility facade so route changes stay small and legacy API-key tests keep working.

**Tech Stack:** FastAPI, Pydantic, pytest, opaque HMAC-backed session tokens, React/Next.js fetch clients, existing LipiOCR repository abstractions.

---

## File Structure

- Create `backend/app/security/__init__.py`: exports the security package surface.
- Create `backend/app/security/sessions.py`: session principals, opaque token issuance, verification, revocation, and expiry.
- Create `backend/app/security/rbac.py`: role permission matrix and permission checks for session/API principals.
- Create `backend/app/security/tenant_context.py`: tenant/branch/user context derived from the authenticated principal.
- Create `backend/app/security/upload_policy.py`: file size, MIME, extension, and empty-file upload checks.
- Modify `backend/app/services/security.py`: preserve existing imports while delegating to the new package.
- Modify `backend/app/core/config.py`: add session and upload-policy environment settings.
- Modify `backend/app/main.py`: add `/api/auth/session`, `/api/auth/me`, `/api/auth/logout`; enforce upload policy before storage writes.
- Create `backend/tests/test_session_auth.py`: tests for session lifecycle, cookie/bearer auth, RBAC, and API-key compatibility.
- Create `backend/tests/test_tenant_context.py`: tests for tenant context resolution and cross-tenant mismatch handling.
- Create `backend/tests/test_upload_policy.py`: tests for file size, MIME, extension, and empty upload rejection.
- Create `frontend/src/lib/auth-client.ts`: browser session client using cookies instead of local operator API-key storage.
- Create `frontend/src/components/auth/login-panel.tsx`: operator session panel with tenant, branch, role, and username fields.
- Modify `frontend/src/lib/api-client.ts`: send credentials for cookies and keep API-key fallback only for integration/admin debugging.
- Modify `frontend/src/components/enterprise-workspace.tsx`: show operator session state instead of API-key-first access.

---

### Task 1: Session Principal And Store

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/sessions.py`
- Test: `backend/tests/test_session_auth.py`

- [ ] **Step 1: Write failing session-store tests**

```python
from datetime import timedelta

from app.security.sessions import InMemorySessionStore, SessionPrincipal


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
        SessionPrincipal(user_id="checker.one", role="checker", tenant_id="global", branch_code=None, auth_method="session")
    )
    store._sessions[token].expires_at = store._sessions[token].issued_at - timedelta(seconds=1)

    assert store.verify(token) is None
```

- [ ] **Step 2: Run failing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py -q`

Expected: import failure for `app.security.sessions`.

- [ ] **Step 3: Implement session store**

Implement:
- `SessionPrincipal`
- `SessionRecord`
- `InMemorySessionStore.create(principal)`
- `InMemorySessionStore.verify(token)`
- `InMemorySessionStore.revoke(token)`
- `session_store_from_settings(settings)` cached factory

- [ ] **Step 4: Run passing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py -q`

Expected: session tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/__init__.py backend/app/security/sessions.py backend/tests/test_session_auth.py
git commit -m "feat: add operator session store"
```

### Task 2: RBAC And Compatibility Facade

**Files:**
- Create: `backend/app/security/rbac.py`
- Modify: `backend/app/services/security.py`
- Test: `backend/tests/test_session_auth.py`

- [ ] **Step 1: Add failing RBAC tests**

```python
from fastapi import HTTPException

from app.security.rbac import Principal, require_permission_for_principal


def test_maker_cannot_approve_case():
    principal = Principal(role="maker", user_id="maker.one", tenant_id="nmb-bank", branch_code="KTM-01", auth_method="session")

    try:
        require_permission_for_principal(principal, "approve_case")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("maker approval should fail")


def test_admin_can_manage_templates():
    principal = Principal(role="admin", user_id="admin.one", tenant_id="nmb-bank", branch_code=None, auth_method="session")

    assert require_permission_for_principal(principal, "manage_templates") == principal
```

- [ ] **Step 2: Run failing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py -q`

Expected: `app.security.rbac` import failure.

- [ ] **Step 3: Implement RBAC**

Implement `ROLE_PERMISSIONS`, `Principal`, `require_permission_for_principal`, and `require_any_permission_for_principal`. Preserve `admin` and `system` wildcard semantics.

- [ ] **Step 4: Update compatibility facade**

Update `app.services.security` so existing route imports still work:
- Parse API keys as before.
- Resolve a session cookie or bearer session token before API-key fallback.
- Return the new `Principal` with `user_id`, `tenant_id`, `branch_code`, `role`, `auth_method`, and optional `api_key_fingerprint`.

- [ ] **Step 5: Run passing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py -q`

Expected: all session/RBAC tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/security/rbac.py backend/app/services/security.py backend/tests/test_session_auth.py
git commit -m "feat: add session-aware rbac"
```

### Task 3: Tenant Context

**Files:**
- Create: `backend/app/security/tenant_context.py`
- Test: `backend/tests/test_tenant_context.py`

- [ ] **Step 1: Write failing tenant-context tests**

```python
from fastapi import HTTPException

from app.security.rbac import Principal
from app.security.tenant_context import TenantContext, context_from_principal, ensure_tenant_match


def test_context_contains_user_role_tenant_and_branch():
    principal = Principal(role="checker", user_id="checker.one", tenant_id="nic-asia", branch_code="NPR-22", auth_method="session")

    assert context_from_principal(principal) == TenantContext(
        tenant_id="nic-asia",
        branch_code="NPR-22",
        user_id="checker.one",
        role="checker",
        auth_method="session",
    )


def test_cross_tenant_access_is_rejected():
    context = TenantContext(tenant_id="tenant-a", branch_code=None, user_id="maker.one", role="maker", auth_method="session")

    try:
        ensure_tenant_match(context, "tenant-b")
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("cross tenant access should fail")
```

- [ ] **Step 2: Run failing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_tenant_context.py -q`

Expected: import failure.

- [ ] **Step 3: Implement tenant context**

Implement `TenantContext`, `context_from_principal`, and `ensure_tenant_match`. Allow `system` principals to bypass tenant mismatch because integration jobs can operate cross-tenant.

- [ ] **Step 4: Run passing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_tenant_context.py -q`

Expected: tenant tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/tenant_context.py backend/tests/test_tenant_context.py
git commit -m "feat: add tenant request context"
```

### Task 4: Upload Policy

**Files:**
- Create: `backend/app/security/upload_policy.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_upload_policy.py`

- [ ] **Step 1: Write failing upload-policy tests**

```python
from fastapi import HTTPException

from app.security.upload_policy import UploadPolicy, validate_upload_policy


def test_rejects_empty_upload():
    try:
        validate_upload_policy("citizenship.jpg", "image/jpeg", b"", UploadPolicy())
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("empty upload should fail")


def test_rejects_oversized_upload():
    policy = UploadPolicy(max_bytes=4, allowed_mime_types={"image/jpeg"}, allowed_extensions={".jpg", ".jpeg"})
    try:
        validate_upload_policy("citizenship.jpg", "image/jpeg", b"12345", policy)
    except HTTPException as exc:
        assert exc.status_code == 413
    else:
        raise AssertionError("oversized upload should fail")


def test_rejects_unsupported_mime_and_extension():
    policy = UploadPolicy(max_bytes=1024, allowed_mime_types={"image/jpeg"}, allowed_extensions={".jpg"})
    try:
        validate_upload_policy("script.exe", "application/x-msdownload", b"123", policy)
    except HTTPException as exc:
        assert exc.status_code == 415
    else:
        raise AssertionError("unsupported upload should fail")
```

- [ ] **Step 2: Run failing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_upload_policy.py -q`

Expected: import failure.

- [ ] **Step 3: Implement upload policy**

Implement `UploadPolicy`, `upload_policy_from_settings(settings)`, and `validate_upload_policy(filename, content_type, content, policy)`.

- [ ] **Step 4: Add config fields**

Add:
- `session_secret`
- `session_ttl_seconds`
- `session_cookie_name`
- `default_tenant_id`
- `max_upload_bytes`
- `allowed_upload_mime_types`
- `allowed_upload_extensions`

- [ ] **Step 5: Run passing tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_upload_policy.py -q`

Expected: upload policy tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/security/upload_policy.py backend/app/core/config.py backend/tests/test_upload_policy.py
git commit -m "feat: enforce upload policy"
```

### Task 5: FastAPI Session Endpoints And Upload Enforcement

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_session_auth.py`
- Test: `backend/tests/test_upload_policy.py`

- [ ] **Step 1: Add failing API tests**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_operator_session_can_access_cases(monkeypatch):
    monkeypatch.setenv("LIPIOCR_API_AUTH_ENABLED", "true")
    client = TestClient(app)

    login = client.post(
        "/api/auth/session",
        json={"username": "maker.one", "role": "maker", "tenant_id": "nmb-bank", "branch_code": "KTM-01"},
    )

    assert login.status_code == 201
    assert client.get("/api/cases").status_code == 200


def test_logout_revokes_operator_session(monkeypatch):
    monkeypatch.setenv("LIPIOCR_API_AUTH_ENABLED", "true")
    client = TestClient(app)
    assert client.post("/api/auth/session", json={"username": "maker.one"}).status_code == 201

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/cases").status_code == 401
```

- [ ] **Step 2: Run failing API tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py tests/test_upload_policy.py -q`

Expected: missing `/api/auth/session` and `/api/auth/logout` routes.

- [ ] **Step 3: Implement auth routes**

Add `POST /api/auth/session`, `GET /api/auth/me`, and `POST /api/auth/logout`. Return principal metadata and set/clear an HttpOnly cookie named by `settings.session_cookie_name`.

- [ ] **Step 4: Enforce upload policy at all upload entry points**

Call `validate_upload_policy` immediately after `await file.read()` in:
- `create_template_draft_upload`
- `upload_case_document`
- `replace_case_document`
- `upload_document`
- `replace_document`
- other `UploadFile` endpoints found by `rg "UploadFile" backend/app/main.py`

- [ ] **Step 5: Run focused tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py tests/test_upload_policy.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_session_auth.py backend/tests/test_upload_policy.py
git commit -m "feat: add operator session api"
```

### Task 6: Frontend Operator Session UX

**Files:**
- Create: `frontend/src/lib/auth-client.ts`
- Create: `frontend/src/components/auth/login-panel.tsx`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Test: `frontend/scripts/api-client.test.mjs`

- [ ] **Step 1: Add failing client tests**

```javascript
test("api requests include credentials for operator sessions", async () => {
  const init = buildApiInit({ method: "GET" });
  assert.equal(init.credentials, "include");
});
```

- [ ] **Step 2: Run failing frontend tests**

Run: `cd frontend && npm run test`

Expected: missing helper or credentials assertion failure.

- [ ] **Step 3: Implement auth client**

Add `createOperatorSession`, `loadOperatorSession`, and `logoutOperatorSession` helpers that call `/api/auth/session`, `/api/auth/me`, and `/api/auth/logout` with `credentials: "include"`.

- [ ] **Step 4: Implement login panel**

Add a compact login panel for username, tenant, branch, and role; no API key input as the primary operator flow.

- [ ] **Step 5: Wire workspace**

Replace API-key-first blocking with operator-session state. Keep API-key fallback only for existing integration/debug storage so old local dev flows do not break.

- [ ] **Step 6: Run frontend tests**

Run: `cd frontend && npm run test`

Expected: frontend test suite passes.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/auth-client.ts frontend/src/components/auth/login-panel.tsx frontend/src/lib/api-client.ts frontend/src/components/enterprise-workspace.tsx frontend/scripts/api-client.test.mjs
git commit -m "feat: add operator session ux"
```

### Task 7: Verification And Phase Closeout

**Files:**
- Modify: `docs/superpowers/plans/2026-05-30-production-readiness-phase-4-security-foundation.md`

- [ ] **Step 1: Run backend focused tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py tests/test_tenant_context.py tests/test_upload_policy.py -q`

Expected: pass.

- [ ] **Step 2: Run full test suite**

Run: `make test`

Expected: backend, frontend, lint, and build pass.

- [ ] **Step 3: Update verification log**

Append a section named `## Verification Log` with exact commands and results.

- [ ] **Step 4: Commit verification notes**

```bash
git add docs/superpowers/plans/2026-05-30-production-readiness-phase-4-security-foundation.md
git commit -m "docs: record phase 4 verification"
```

## Self-Review

- Spec coverage: operator sessions, API-key integration compatibility, tenant/branch/user/role context, RBAC, and upload policy are all covered.
- Placeholder scan: no task uses TBD/TODO placeholders.
- Type consistency: `SessionPrincipal`, `Principal`, and `TenantContext` all use `user_id`, `role`, `tenant_id`, `branch_code`, and `auth_method`.

## Verification Log

- `cd backend && .venv/bin/python -m pytest tests/test_session_auth.py tests/test_tenant_context.py tests/test_upload_policy.py -q`
  - Result: `14 passed in 0.43s`
- `cd backend && .venv/bin/python -m pytest tests/test_production_foundations.py tests/test_documents_api.py tests/test_enterprise_cases_api.py tests/test_upload_job_api.py tests/test_session_auth.py tests/test_tenant_context.py tests/test_upload_policy.py -q`
  - Result: `34 passed in 1.15s`
- `cd frontend && npm run test`
  - Result: `13 passed`
- `cd frontend && npm run lint`
  - Result: passed
- `cd frontend && npm run build`
  - Result: passed; Next.js generated all 13 static routes
- Browser smoke test at `http://127.0.0.1:8100/documents` with API auth enabled and API at `http://127.0.0.1:8010`
  - Result: session-required panel rendered, old API-key prompt absent, operator sign-in succeeded, session-active panel rendered
  - Screenshot: `artifacts/phase4-session-ui.png`
- `make test`
  - Result: backend `113 passed`, frontend Node `13 passed`, ESLint passed, Next.js build passed
