# LipiOCR Production Readiness Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn LipiOCR from a strong enterprise pilot into an on-premise production product and a SaaS-ready platform.

**Architecture:** Production readiness is split into independent phase plans. Each phase must produce testable software, keep the existing demo working, and preserve reviewer-safe OCR/ICR behavior. On-premise readiness is delivered before hosted SaaS multi-tenancy.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/Postgres, Alembic, Redis, worker queue, MinIO/S3, Next.js, React, Docker Compose, Helm/Kubernetes, LipiCore/Gemma-compatible OCR and reasoning.

---

## Source Design

Use this approved spec as the source of truth:

- `docs/superpowers/specs/2026-05-29-production-readiness-design.md`

## Phase Order

### Phase 1: Architecture Refactor

**Plan:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-1-architecture-refactor.md`

**Goal:** Split the largest backend and frontend files into clear modules while preserving current behavior.

**Exit gate:**

- `make test` passes.
- `backend/app/main.py` is reduced to app assembly and shared helpers only.
- `frontend/src/components/enterprise-workspace.tsx` is reduced by moving API/client/types and at least one large route section out.
- Existing live routes continue to work.

### Phase 2: Production Database And Audit

**Plan file to create after Phase 1 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-2-database-audit.md`

**Goal:** Replace JSON-payload persistence as the primary model with normalized Postgres tables and immutable audit events.

**Files expected:**

- Create `backend/migrations/`
- Create `backend/alembic.ini`
- Create `backend/app/db/session.py`
- Create `backend/app/db/models.py`
- Create `backend/app/repositories/cases.py`
- Create `backend/app/repositories/documents.py`
- Create `backend/app/repositories/audit.py`
- Modify `backend/app/services/repository.py`
- Test `backend/tests/test_database_repository.py`
- Test `backend/tests/test_audit_repository.py`

**Exit gate:**

- Alembic can create all production tables.
- Cases, documents, OCR blocks, extracted fields, corrections, reviews, exports, jobs, and audit events include `tenant_id`.
- Every exported field can be traced to field evidence and audit history.

### Phase 3: Async OCR Worker Pipeline

**Plan file to create after Phase 2 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-3-async-ocr-workers.md`

**Goal:** Move OCR, LipiCore reasoning, template test runs, and export delivery out of request-response flows.

**Files expected:**

- Create `backend/app/jobs/models.py`
- Create `backend/app/jobs/queue.py`
- Create `backend/app/jobs/worker.py`
- Create `backend/app/jobs/document_jobs.py`
- Modify `backend/app/routers/documents.py`
- Modify `backend/app/routers/templates.py`
- Modify `infra/docker-compose.yml`
- Test `backend/tests/test_document_jobs.py`
- Test `backend/tests/test_upload_job_api.py`

**Exit gate:**

- Upload returns a job ID.
- UI shows queued, processing, completed, failed, and retry states.
- Failed OCR/LipiCore jobs can be retried.
- Multi-page files do not block API workers.

### Phase 4: Security Foundation

**Plan file to create after Phase 3 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-4-security-foundation.md`

**Goal:** Replace pilot API-key access for operators with real authenticated sessions, RBAC, tenant context, and upload security.

**Files expected:**

- Create `backend/app/security/sessions.py`
- Create `backend/app/security/rbac.py`
- Create `backend/app/security/tenant_context.py`
- Create `backend/app/security/upload_policy.py`
- Create `frontend/src/lib/auth-client.ts`
- Create `frontend/src/components/auth/login-panel.tsx`
- Modify `backend/app/services/security.py`
- Modify all protected routers to use tenant-aware dependencies.
- Test `backend/tests/test_session_auth.py`
- Test `backend/tests/test_tenant_scope.py`
- Test `backend/tests/test_upload_policy.py`

**Exit gate:**

- Operators no longer use browser-stored API keys.
- API integration keys remain only for system integrations.
- Every protected action includes user, role, tenant, and branch context.
- Upload file size and MIME rules are enforced.

### Phase 5: OCR Benchmark And Accuracy

**Plan file to create after Phase 4 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-5-accuracy-benchmark.md`

**Goal:** Produce a real Nepal document accuracy program and exportable benchmark report.

**Files expected:**

- Create `backend/app/accuracy/dataset.py`
- Create `backend/app/accuracy/metrics.py`
- Create `backend/app/accuracy/report.py`
- Create `backend/tests/fixtures/accuracy/manifest.json`
- Create `backend/tests/test_accuracy_metrics.py`
- Create `frontend/src/components/analytics/accuracy-report.tsx`

**Exit gate:**

- Character error rate, word error rate, field precision, field recall, field F1, and reviewer correction rate are computed.
- Accuracy is broken down by document type and field key.
- Handwriting is reported separately from printed OCR.

### Phase 6: Template Governance

**Plan file to create after Phase 5 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-6-template-governance.md`

**Goal:** Make Template Studio safe for institution use with profile versions, approval, rollback, test runs, tenant scope, import, and export.

**Files expected:**

- Modify `backend/app/services/template_profiles.py`
- Create `backend/app/services/template_testing.py`
- Create `backend/app/routers/templates.py`
- Create `frontend/src/components/templates/template-version-panel.tsx`
- Test `backend/tests/test_template_governance.py`

**Exit gate:**

- Templates are tenant-scoped.
- Publishing requires admin approval.
- A published template can be rolled back.
- A template can be tested against sample pages before activation.

### Phase 7: On-Prem Production Pack

**Plan file to create after Phase 6 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-7-on-prem-pack.md`

**Goal:** Package LipiOCR for reliable institution-owned deployment.

**Files expected:**

- Create `deploy/compose/`
- Create `deploy/helm/lipiocr/`
- Create `deploy/scripts/validate-env.sh`
- Create `deploy/scripts/backup.sh`
- Create `deploy/scripts/restore.sh`
- Create `deploy/scripts/health-check.sh`
- Modify `infra/docker-compose.yml`
- Test `backend/tests/test_deployment_config.py`

**Exit gate:**

- Fresh VM deployment instructions are deterministic.
- Backups and restore are tested.
- TLS reverse proxy config exists.
- Offline image bundle instructions exist.

### Phase 8: Integrations Hardening

**Plan file to create after Phase 7 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-8-integrations-hardening.md`

**Goal:** Make exports and institution integrations traceable, idempotent, signed, retryable, and auditable.

**Files expected:**

- Create `backend/app/integrations/idempotency.py`
- Create `backend/app/integrations/webhook_delivery.py`
- Create `backend/app/integrations/sftp_delivery.py`
- Modify `backend/app/services/integrations.py`
- Modify `backend/app/services/integration_operations.py`
- Test `backend/tests/test_integration_idempotency.py`
- Test `backend/tests/test_webhook_delivery.py`

**Exit gate:**

- Webhooks are signed.
- Retries keep delivery receipts.
- Exports use idempotency keys.
- Export history is visible by case and document.

### Phase 9: SaaS Multi-Tenancy

**Plan file to create after Phase 8 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-9-saas-multitenancy.md`

**Goal:** Prepare hosted SaaS with strict tenant isolation and tenant lifecycle operations.

**Files expected:**

- Create `backend/app/tenancy/models.py`
- Create `backend/app/tenancy/service.py`
- Create `backend/app/tenancy/object_keys.py`
- Create `frontend/src/components/admin/tenant-admin.tsx`
- Test `backend/tests/test_cross_tenant_isolation.py`
- Test `backend/tests/test_tenant_object_keys.py`

**Exit gate:**

- Automated tests prove that one tenant cannot read another tenant's cases, documents, object URLs, jobs, templates, exports, or audit logs.
- Tenant admin can manage tenant settings, users, roles, retention, and exports.

### Phase 10: Compliance Operations

**Plan file to create after Phase 9 passes:** `docs/superpowers/plans/2026-05-29-production-readiness-phase-10-compliance-operations.md`

**Goal:** Produce financial-institution review material and operational controls.

**Files expected:**

- Create `backend/app/compliance/reports.py`
- Create `backend/app/compliance/retention.py`
- Create `backend/app/compliance/dr.py`
- Create `docs/runbooks/incident-response.md`
- Create `docs/runbooks/disaster-recovery.md`
- Create `docs/security/production-security-checklist.md`
- Test `backend/tests/test_compliance_reports.py`

**Exit gate:**

- Access review report exists.
- Audit integrity report exists.
- Retention report exists.
- Backup report exists.
- Incident and disaster recovery runbooks exist.

## Global Rules For All Phases

- Run `make test` before every phase is marked complete.
- Keep existing pilot behavior working unless the phase explicitly replaces it.
- Keep LipiCore as the external product name in frontend copy.
- Do not claim full Nepali handwriting automation.
- Do not fake external registry, AML, SFTP, CBS, LOS, or DMS verification.
- Commit after every task that produces passing tests.
- Do not mix unrelated phase work into a task.

## Execution Recommendation

Use subagent-driven development for each phase. Dispatch one subagent per task, review the diff, run tests, then continue. Start with Phase 1 because it reduces the risk of every later production feature.
