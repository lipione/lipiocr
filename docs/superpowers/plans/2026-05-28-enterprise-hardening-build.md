# Enterprise Hardening Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the production-readiness gaps found in the project review while keeping the public LipiOCR product and dashboard usable under `/lipiocr`.

**Architecture:** Enforce API-key RBAC on sensitive API surfaces, replace public static upload serving with signed preview URLs, remove synthetic demo extraction, redact public LipiCore health details, and let the frontend persist an operator API key for protected calls. Keep the existing FastAPI/Next.js structure and add focused tests around the highest-risk behaviors.

**Tech Stack:** FastAPI, Pydantic settings, pytest/TestClient, Next.js/React, Docker Compose, Nginx subpath deployment.

---

### Task 1: Backend Security Regression Tests

**Files:**
- Modify: `backend/tests/test_production_foundations.py`
- Modify: `backend/tests/test_nepal_document_formats.py`

- [ ] **Step 1: Add failing tests**

Add tests that assert sensitive endpoints require an API key when auth is enabled, health is redacted publicly, upload preview URLs require signed access, dangerous filenames are normalized, and NIC ASIA fallback no longer injects Rudra demo data.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `cd backend && .venv/bin/python -m pytest tests/test_production_foundations.py tests/test_nepal_document_formats.py -q`

Expected: FAIL on the newly added security expectations before implementation.

### Task 2: Backend Implementation

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/security.py`
- Modify: `backend/app/services/gemma.py`
- Modify: `backend/app/services/enterprise_extraction.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement signed previews and safe stored names**

Generate UUID-based stored upload names, sign preview URLs with HMAC expiry, and serve `/api/uploads/{stored_name}` through a guarded endpoint instead of `StaticFiles`.

- [ ] **Step 2: Enforce RBAC consistently**

Add `Request` parameters and `require_permission` calls to all case/document/admin/analytics/integration routes that expose or mutate operational data.

- [ ] **Step 3: Redact public LipiCore health**

Return product-safe `LipiCore` health fields publicly and allow detailed internal fields only after admin authorization.

- [ ] **Step 4: Remove synthetic ASBA recovery**

Remove the hard-coded NIC ASIA demo-data recovery path and rely on OCR/LipiCore observations plus reviewer correction.

### Task 3: Frontend Protected Access

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [ ] **Step 1: Add API-key persistence**

Store an operator API key in `localStorage`, attach it to API requests, and show a compact access panel when requests return `401`.

- [ ] **Step 2: Remove brittle public model/demo identity text**

Keep product-facing wording as `LipiCore`, avoid raw model/provider names, and stop presenting fake reviewer identities as real system behavior.

### Task 4: Infra Defaults

**Files:**
- Modify: `infra/.env.example`
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: Production-safe defaults**

Default auth to enabled in compose/example config, require explicit API keys and stronger secret placeholders, and avoid exposing object storage ports unless deliberately enabled.

### Task 5: Verification and Deployment

**Files:**
- No code files unless deployment config requires a final correction.

- [ ] **Step 1: Run local verification**

Run: `make test`

- [ ] **Step 2: Deploy remote**

Sync the working tree to `/data/lipiocr`, rebuild containers, set remote auth/API-key env, and restart.

- [ ] **Step 3: Verify public behavior**

Check that `/lipiocr` returns `200`, public sensitive APIs return `401`, public health is redacted, and authenticated APIs return `200`.
