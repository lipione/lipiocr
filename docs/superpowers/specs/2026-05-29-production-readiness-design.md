# LipiOCR Production Readiness Design

**Date:** 2026-05-29  
**Product:** LipiOCR Enterprise  
**Deployment goals:** on-premise financial institution deployment and SaaS readiness  
**Country focus:** Nepal  

## Objective

Make LipiOCR production-ready as a Nepal-focused document intelligence platform for banks, microfinance institutions, cooperatives, insurers, wallets, lenders, remittance companies, and broker/merchant-bank operations.

The product must support two commercial deployment modes:

1. **On-premise/private deployment:** institution-owned environment, institution-owned data, private network friendly, no public SaaS dependency.
2. **SaaS deployment:** multi-tenant hosted platform with strict tenant isolation, per-tenant configuration, operational monitoring, and auditability.

The first production target is on-premise/private deployment. SaaS readiness follows after the data model, security model, tenant isolation, and operational controls are mature.

## Current Assessment

The existing system has the correct product direction:

- KYC/KYB/document digitization workflows.
- Full-page OCR evidence with blocks, bounding boxes, confidence, and page references.
- Nepal document formats including citizenship, National ID, passport, smart license, account forms, IPO/C-ASBA forms, PAN/VAT, cheques, statements, and KYB documents.
- LipiCore reasoning over OCR evidence.
- Bilingual field pairing, AD/BS date handling, confidence repair, and reviewer-safe correction metadata.
- Human review, audit events, template creation, JSON exports, provider-neutral verification adapter concepts, and integration profile concepts.
- Docker Compose deployment with API, frontend, Postgres, Redis, and MinIO.

The system is not yet production-ready because:

- Authentication is static API-key based and currently not enterprise identity.
- The repository stores broad JSON payloads rather than normalized production tables.
- OCR/ICR accuracy is not measured against a real Nepali document benchmark.
- Upload/OCR/Gemma work is synchronous and can block request flows.
- Frontend and backend core files are too large for long-term maintenance.
- Security/compliance controls are incomplete for regulated financial data.
- Multi-tenant SaaS isolation is not yet implemented.

## Production Principles

1. **Reviewer-first, not automation-first:** all uncertain OCR/ICR fields must remain editable and auditable.
2. **Evidence-backed extraction:** every exported field should trace to OCR block, page, document, reviewer action, or derived rule.
3. **Nepal-aware intelligence:** preserve Nepali and English values, normalize where useful, support AD/BS conversion, and never overwrite originals without audit metadata.
4. **On-prem first:** deploy reliably inside a financial institution before offering hosted SaaS.
5. **No fake integrations:** unavailable registry, AML, SFTP, CBS, LOS, or DMS connections must show explicit `not_configured` or sandbox state.
6. **Tenant and role boundaries:** every production action belongs to a tenant, user, role, branch, and audit event.
7. **Measured accuracy:** OCR confidence must be backed by benchmark results, not only model self-confidence.

## Recommended Approach

### Option A: Harden Current App In Place

Keep the existing module shape and add production controls directly.

**Pros:** fastest short-term path.  
**Cons:** large files, weak boundaries, hard to test, increased regression risk.  
**Decision:** rejected except for temporary pilot hotfixes.

### Option B: Production Core Refactor First

Refactor backend routes/services and frontend modules before adding major production features.

**Pros:** maintainable, testable, easier to secure, supports both on-prem and SaaS.  
**Cons:** slower initial visible progress.  
**Decision:** recommended.

### Option C: Rebuild As New Platform

Start a fresh monorepo and port selected features.

**Pros:** clean architecture.  
**Cons:** high delivery risk, discards working demo, delays pilot.  
**Decision:** rejected for now.

## Target Architecture

```text
Browser / Institution Network
        |
        v
Next.js Frontend
        |
        v
FastAPI API Gateway
        |
        +-- Auth/RBAC/Tenant Context
        +-- Case + Document API
        +-- Review + Template API
        +-- Export + Integration API
        +-- Admin + Audit API
        |
        v
Postgres domain database
        |
        +-- cases
        +-- documents
        +-- document_pages
        +-- ocr_blocks
        +-- extracted_fields
        +-- field_corrections
        +-- reviews
        +-- audit_events
        +-- templates
        +-- exports
        +-- jobs
        |
        v
Object Storage
        |
        +-- original uploads
        +-- page renders
        +-- review crops
        +-- export artifacts
        |
        v
Worker Queue
        |
        +-- OCR/ICR jobs
        +-- LipiCore reasoning jobs
        +-- template test jobs
        +-- export delivery jobs
```

## Backend Design

### Route Boundaries

Split the FastAPI application into dedicated routers:

- `cases`: case creation, case list/detail, case-level review and export.
- `documents`: standalone upload, case upload, reanalyze, replace, archive, link to application.
- `review`: review queue, assignments, comments, rework, approval.
- `templates`: draft upload, canvas mapping, publish, versioning, test runs.
- `integrations`: export profiles, webhooks, SFTP batches, retry queue.
- `verification`: adapter configuration and adapter runs.
- `admin`: tenant policy, RBAC, audit integrity, platform status.
- `health`: public health and internal authenticated health.

### Service Boundaries

Create focused service modules:

- `auth`: session, user identity, RBAC, API integration keys.
- `tenant_context`: tenant resolution, branch context, data scope checks.
- `document_pipeline`: upload orchestration, page splitting, OCR job creation.
- `ocr_pipeline`: OCR providers, result normalization, confidence calibration.
- `lipicore_pipeline`: bilingual reasoning, entity reconciliation, confidence repair.
- `review_service`: corrections, approvals, maker-checker rules.
- `template_service`: template drafts, profiles, versioning, rollback.
- `export_service`: JSON/export profiles, idempotency, delivery receipts.
- `audit_service`: immutable audit events and hash-chain summaries.
- `retention_service`: data retention, deletion, legal hold.

### Database Design

Postgres becomes the source of truth. JSON payload storage is retained only for debug snapshots, not as the primary model.

Minimum tables:

- `tenants`
- `users`
- `roles`
- `api_keys`
- `cases`
- `documents`
- `document_versions`
- `document_pages`
- `ocr_blocks`
- `extracted_fields`
- `field_corrections`
- `reviews`
- `audit_events`
- `template_profiles`
- `template_versions`
- `exports`
- `integration_events`
- `jobs`

All tables that contain institution data include `tenant_id`.

## Frontend Design

The frontend should become operator-first:

1. **Documents:** upload, extraction status, split preview, editable fields, reanalyze, replace, export.
2. **Applications:** customer/application file, linked documents, readiness, review state.
3. **Review:** assigned work, corrections, approvals, comments, rework.
4. **Templates:** template creation, page canvas, fields, test extraction, publish/version.
5. **Integrations:** export profiles, webhook/SFTP status, retry queue.
6. **Admin:** tenant settings, users/roles, audit, health, retention.

The primary operator flow is:

```text
Upload document
→ OCR processing
→ split preview
→ correct fields
→ approve
→ export
```

Advanced technical details stay in Admin or Integrations. Model/provider names remain hidden behind LipiCore in product UI.

## OCR And LipiCore Design

### OCR/ICR Pipeline

The production pipeline has three layers:

1. **OCR evidence:** printed text, handwriting candidates, bounding boxes, confidence.
2. **LipiCore reasoning:** field extraction, bilingual pairing, date normalization, entity reconciliation.
3. **Reviewer confirmation:** manual correction, approval, export readiness.

Handwriting support is reviewer-assisted. The product can capture and suggest handwritten values, but should not claim fully reliable Nepali handwriting automation until benchmark evidence supports it.

### Accuracy Program

Build a benchmark harness with real Nepali samples:

- Citizenship front/back.
- National ID.
- Passport.
- Smart driving license.
- Account/KYC forms.
- IPO/C-ASBA forms.
- Mixed printed and handwritten pages.
- Low-quality scans and mobile photos.

Metrics:

- OCR character error rate and word error rate.
- Field precision, recall, F1.
- Confidence calibration.
- Reviewer correction rate.
- Per-document readiness.
- Per-field accuracy trend.

## Security Design

### On-Prem Security

Required controls:

- OIDC/SAML/LDAP login support.
- HttpOnly session cookies.
- Role-based access control.
- Tenant and branch scoping.
- API integration keys only for system-to-system calls.
- Key rotation and expiry.
- File size and type restrictions.
- Malware scanning hook.
- Object storage private by default.
- Encryption at rest and in transit.
- Signed preview URLs with short TTL.
- Rate limiting.
- Security headers.
- Immutable audit events.
- Backup encryption.

### SaaS Security

Additional controls:

- Hard tenant isolation in database queries, object keys, jobs, exports, templates, and audit logs.
- Per-tenant encryption key strategy.
- Tenant-level retention policy.
- Tenant admin console.
- Central operations monitoring without cross-tenant data exposure.
- Data export and deletion workflow.

## Deployment Design

### On-Prem

Supported installation modes:

1. Docker Compose for pilot and smaller institution environments.
2. Kubernetes/Helm for production-grade institution deployments.
3. Offline image bundle for restricted networks.

Deployment includes:

- API.
- Frontend.
- Worker service.
- Scheduler service.
- Postgres.
- Redis.
- MinIO/S3-compatible object storage.
- Reverse proxy/TLS.
- Backup/restore scripts.
- Environment validator.
- Health check script.
- Upgrade and rollback scripts.

### SaaS

SaaS architecture adds:

- Managed Postgres.
- Managed object storage.
- Managed Redis/queue.
- Per-tenant configuration store.
- Monitoring and alerting.
- Central admin/control plane.
- Separate tenant-scoped data plane controls.

## Integrations Design

Integrations remain adapter-based:

- REST API export.
- Signed webhooks.
- SFTP batch delivery.
- JSON profiles for CBS/LOS/CRM/DMS ingestion.
- Embedded review links.
- Verification adapters for PAN, National ID, AML/sanctions, face/liveness, duplicate checks, and tamper signals.

Every integration event has:

- `tenant_id`
- `case_id` or `document_id`
- idempotency key
- request payload hash
- status
- retry count
- delivery receipt
- audit event

## Compliance And Operations Design

Production requires operational evidence:

- Access review report.
- Audit integrity report.
- Retention report.
- Backup report.
- OCR accuracy report.
- Export history.
- Security event report.
- Incident response runbook.
- Disaster recovery drill checklist.

The product should support financial institution IT review without requiring trust in undocumented internals.

## Phased Delivery

### Phase 1: Architecture Refactor

Split frontend and backend into maintainable modules without changing product behavior.

### Phase 2: Production Database And Audit

Introduce Alembic migrations, normalized tables, tenant IDs, audit events, and correction history.

### Phase 3: Async OCR Worker Pipeline

Move OCR, LipiCore, template testing, and export delivery into jobs.

### Phase 4: Security Foundation

Replace browser-stored operator API keys with real session authentication, RBAC, tenant context, rate limits, and upload hardening.

### Phase 5: OCR Benchmark And Accuracy

Build the Nepal sample benchmark harness and accuracy reporting.

### Phase 6: Template Governance

Add versioning, approval, rollback, test runs, tenant-specific templates, and import/export.

### Phase 7: On-Prem Production Pack

Deliver Docker Compose, Helm, offline bundle, backup/restore, TLS proxy, health checks, and upgrade/rollback.

### Phase 8: Integrations Hardening

Add idempotency, delivery receipts, signed webhooks, retry policies, and export lifecycle audit.

### Phase 9: SaaS Multi-Tenancy

Implement strict tenant isolation, tenant admin, per-tenant encryption strategy, SaaS monitoring, and tenant lifecycle operations.

### Phase 10: Compliance Operations

Package access review, audit integrity, retention, backup, incident, and DR reports for institution review.

## Success Criteria

On-prem production pilot is ready when:

- A fresh VM can be installed and restored from backup.
- OCR jobs are asynchronous and recoverable.
- Every exported field traces to evidence and review history.
- Every sensitive operation is tied to an authenticated user and tenant.
- Uploads are restricted, scanned or scan-ready, and privately stored.
- Real benchmark accuracy report exists for supported document types.
- A bank/MFI operator can complete document review without technical assistance.

SaaS is ready when:

- Tenant isolation is proven in automated tests.
- Cross-tenant document, job, template, export, and object access is impossible by design.
- Tenant admin, retention, audit export, and deletion workflows exist.
- SaaS monitoring, backup, incident, and DR processes are documented and tested.

## Out Of Scope For This Production Readiness Cycle

- Fully automated fraud detection.
- Fully reliable Nepali handwriting recognition claims.
- Signature verification as a biometric decision.
- Public registry integration without institution credentials.
- Generic RAG/vector database architecture.
- Complex model fine-tuning before benchmark data exists.

## Self-Review Notes

- No requirements are left incomplete or ambiguous.
- On-prem delivery is intentionally prioritized before SaaS.
- SaaS readiness is included but gated behind tenant isolation and operational controls.
- The design avoids claiming full handwriting automation.
- The design focuses on maintainability, security, auditability, benchmark accuracy, and deployment reliability.
