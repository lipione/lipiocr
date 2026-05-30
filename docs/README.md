# LipiOCR Documentation

This directory is the operating manual for LipiOCR Enterprise. It should stay aligned with the code, not with sales promises.

## Start Here

| Reader | First document | Why |
| --- | --- | --- |
| New developer | [Developer Onboarding](./developer-onboarding.md) | Local setup, repo map, test commands, common workflows. |
| Backend engineer | [Architecture](./architecture.md) | Service boundaries, data flow, OCR/LipiCore pipeline, tenancy model. |
| Frontend engineer | [Developer Onboarding](./developer-onboarding.md) and [Frontend README](../frontend/README.md) | Next.js routes, API client behavior, UI conventions. |
| Integrator | [API Reference](./api-reference.md) | Auth, case flow, document upload, review, exports, webhooks, SFTP batches. |
| DevOps engineer | [Configuration](./configuration.md) and [Deployment](./deployment.md) | Environment variables, Docker Compose, Helm, reverse proxy, backups. |
| Security reviewer | [Production Security Checklist](./security/production-security-checklist.md) | Production controls that must be verified before go-live. |
| Incident responder | [Incident Response Runbook](./runbooks/incident-response.md) | First response, containment, communication, closure. |
| DR operator | [Disaster Recovery Runbook](./runbooks/disaster-recovery.md) | Restore sequence and evidence requirements. |

## Product Shape

LipiOCR is a Nepal-focused document intelligence platform for financial institutions. The system handles applicant onboarding, KYC/KYB review, document digitization, bilingual normalization, evidence-backed correction, and controlled export into existing CBS, LOS, CRM, DMS, AML, or registry systems.

The product is not a simple OCR demo. It is built around:

- Full-page OCR evidence with pages, blocks, bounding boxes, confidence, and raw text retention.
- LipiCore reasoning for bilingual field pairing, date normalization, entity reconciliation, confidence repair, and reviewer-safe correction.
- Human review with editable fields, audit trail, assignment, comments, rework, and maker-checker workflow.
- Template studio for known forms and a fallback full-page extraction path for unknown documents.
- Tenant-aware APIs, role permissions, signed delivery, idempotency, and compliance reports.
- On-prem/private-cloud deployment first, with SaaS controls layered through tenant isolation.

## Current Production Readiness

Implemented foundations:

- FastAPI backend with memory and SQL repository modes.
- Next.js frontend with route-backed workspace modules.
- Local storage and S3/MinIO storage modes.
- Mock, Tesseract, PaddleOCR, and Gemma vision OCR provider interfaces.
- Async job queue model for document processing.
- Session and API-key auth, RBAC, tenant context, upload policy, signed image previews.
- Template drafts, profiles, approval, rollback, import/export, and test runs.
- Accuracy analytics and benchmark report scaffolding.
- Signed webhook and SFTP delivery receipts with idempotency keys.
- Compliance reports, retention posture, backup readiness, incident and DR runbooks.
- Docker Compose, Helm skeleton, Nginx subpath config, backup/restore/health scripts.

Known production work that still needs real institution integration:

- SSO/OIDC/SAML provider integration.
- Real registry, PAN/VAT, AML, liveness, and CBS/LOS/DMS credentials.
- Real OCR benchmark dataset collected from institution-approved samples.
- Hardened production database migrations and external worker orchestration.
- Per-tenant encryption key management and observability stack integration.

## Repository Docs Policy

- Root [README](../README.md) is the product and quickstart entry point.
- `docs/*.md` contains operator and developer reference.
- `docs/superpowers/*` contains implementation planning history, not the product manual.
- Real credentials, server passwords, private keys, customer data, and institution samples must never be committed.
