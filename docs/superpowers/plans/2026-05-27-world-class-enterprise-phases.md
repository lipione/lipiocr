# World-Class Enterprise Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand LipiOCR from the Phase 1 case foundation into a full enterprise scaffold covering KYC intelligence, integration kit, enterprise controls, and advanced verification interfaces for Nepal financial institutions.

**Architecture:** Keep the Phase 1 FastAPI/Next.js/Docker architecture. Add modular backend services for KYC checklist intelligence, AI split/classification, cross-document validation, integration contracts, RBAC/tenant controls, audit policy, and advanced verification stubs. Expose them as production-shaped APIs with deterministic local behavior; external dependencies such as National ID, AML, SSO, registry checks, and SFTP remain pluggable adapters until credentials are provided.

**Tech Stack:** FastAPI, Pydantic v2, Next.js 16, React 19, Tailwind CSS, Docker Compose, Gemma 4 26B vLLM endpoint, in-memory repository abstraction for this slice.

---

### Task 1: KYC Intelligence APIs

**Files:**
- Create: `backend/app/services/kyc_intelligence.py`
- Create: `backend/tests/test_kyc_intelligence_api.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [x] Add KYC checklists for Nepal individual KYC, business KYB, loan onboarding, and digitization.
- [x] Add document split preview that can describe logical document segments from a packet.
- [x] Add document classification and cross-document consistency result models.
- [x] Add endpoints:
  - `GET /api/cases/{case_id}/intelligence`
  - `POST /api/cases/{case_id}/split-preview`
  - `POST /api/cases/{case_id}/classify`
  - `POST /api/cases/{case_id}/validate`
- [x] Tests prove a sample individual case returns checklist gaps, classification labels, and validation warnings.

### Task 2: Integration Kit APIs

**Files:**
- Create: `backend/app/services/integrations.py`
- Create: `backend/tests/test_integration_kit_api.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [x] Add integration profiles for manual export, REST API, webhooks, SFTP, and embedded review.
- [x] Add signed webhook payload generation with deterministic HMAC for tests.
- [x] Add signed embedded review link generation.
- [x] Add export profile mapping for CBS/LOS-friendly JSON.
- [x] Add endpoints:
  - `GET /api/integrations/profiles`
  - `POST /api/integrations/webhook/test`
  - `POST /api/cases/{case_id}/embedded-review-link`
  - `GET /api/cases/{case_id}/export-profile/{profile_key}`
- [x] Tests prove webhook signatures, embedded links, and export profile mappings are stable.

### Task 3: Enterprise Controls APIs

**Files:**
- Create: `backend/app/services/enterprise_controls.py`
- Create: `backend/tests/test_enterprise_controls_api.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [x] Add tenant profile, branch policy, RBAC role matrix, retention policy, and audit integrity summary.
- [x] Add maker-checker SLA and review queue summary.
- [x] Add endpoints:
  - `GET /api/admin/tenant`
  - `GET /api/admin/rbac`
  - `GET /api/admin/audit-integrity`
  - `GET /api/review/queue`
- [x] Tests prove tenant policy, role permissions, audit hash chain, and queue summary are returned.

### Task 4: Advanced Verification Interfaces

**Files:**
- Create: `backend/app/services/advanced_verification.py`
- Create: `backend/tests/test_advanced_verification_api.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [x] Add provider-neutral stubs for National ID/PAN registry, AML/sanctions, face/liveness, tamper signals, signature/photo presence, and duplicate detection.
- [x] Add endpoint `POST /api/cases/{case_id}/verification/run`.
- [x] Tests prove verification returns provider status, clear `not_configured` state for unavailable external systems, and actionable next steps.

### Task 5: Enterprise Frontend Modules

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [x] Add dashboard sections for checklist intelligence, integrations, enterprise controls, and advanced verification.
- [x] Add buttons to run validate/classify/verification/export-profile flows.
- [x] Surface "not configured" external adapters clearly without blocking KYC review.
- [x] Keep the UI dense, operational, and Nepal financial-institution focused.
- [x] Run `npm run lint && npm run build`.

### Task 6: Verification, Remote Sync, Commit

**Files:**
- Modify: `README.md`

- [x] Run `make test`.
- [x] Browser verify local flow: sample case, intelligence, validation, verification, export profile.
- [x] Sync to `/data/lipiocr`.
- [x] Commit and push branch.

### Self-Review

- This plan does not fake live National ID, PAN, AML, SSO, SFTP, or core banking access. It implements production-shaped contracts and clear `not_configured` states.
- The architecture remains on-premise/private-cloud friendly for Nepal institutions.
- The implementation should avoid large shared rewrites by keeping backend capabilities in separate service files and adding thin routes in `main.py`.
