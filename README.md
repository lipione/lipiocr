# LipiOCR Enterprise

LipiOCR Enterprise is a Nepal-focused KYC and financial document intelligence platform. It is designed for banks, cooperatives, MFIs, wallets, remittance companies, insurers, and lenders that need evidence-backed document extraction, human review, auditability, and integration with existing CBS/LOS/CRM/DMS systems.

## Current Scope

- Case-based FastAPI backend for KYC/KYB/document processing.
- Full-page OCR evidence model with blocks, bounding boxes, confidence, and page references.
- First-class Nepal document formats for citizenship, National ID, passport, smart driving license, account/KYC forms, IPO applications, C-ASBA forms, PAN/VAT, cheques, statements, and KYB documents.
- Gemma 4 26B reasoning client for OpenAI-compatible vLLM endpoints.
- Enterprise review console for case creation, document upload, evidence inspection, checklist intelligence, validation findings, approval, audit, verification, and JSON export.
- Reviewer workbench for assignment, comments, rework requests, evidence crops, and correction tracking.
- Template studio for coordinate-based document templates with validation rules.
- Nepal KYC intelligence APIs for individual KYC, business KYB, loan onboarding, and document digitization readiness.
- Integration kit APIs for REST, signed webhooks, configurable webhook delivery, SFTP-ready batch delivery, retry queues, embedded review links, and CBS/LOS/AML export profiles.
- Enterprise controls APIs for tenant policy, branch controls, RBAC, maker-checker queue, retention posture, and audit hash-chain summaries.
- Provider-neutral advanced verification interfaces and adapter registry for National ID/PAN registry, AML/sanctions, face/liveness, tamper signals, signature/photo presence, and duplicate detection.
- Accuracy analytics from reviewer corrections, field confidence drift, and document-type performance.
- Docker deployment shape for `/data/lipiocr` with API, frontend, Postgres, Redis, and MinIO.

## Architecture

```text
frontend/ Next.js enterprise review console
        |
        v
backend/ FastAPI KYC workflow API
        |
        +-- Full-page OCR evidence model
        +-- Gemma 4 26B reasoning layer
        +-- Nepal KYC/KYB intelligence, validation, and review workflow
        +-- Integration kit and export profiles
        +-- Enterprise controls and verification adapters
```

## Enterprise API Surface

Core case flow:

- `POST /api/cases`
- `POST /api/cases/{case_id}/documents`
- `GET /api/cases/{case_id}/intelligence`
- `POST /api/cases/{case_id}/split-preview`
- `POST /api/cases/{case_id}/classify`
- `POST /api/cases/{case_id}/validate`
- `POST /api/cases/{case_id}/verification/run`
- `POST /api/cases/{case_id}/verification/{adapter_key}/run`
- `PATCH /api/cases/{case_id}/review`
- `GET /api/cases/{case_id}/export-profile/{profile_key}`
- `GET /api/review/workbench/{case_id}`
- `POST /api/cases/{case_id}/assign`
- `POST /api/cases/{case_id}/comments`
- `POST /api/cases/{case_id}/rework`

Institution integration and controls:

- `GET /api/integrations/profiles`
- `GET /api/integrations/operations`
- `POST /api/integrations/webhook/test`
- `POST /api/integrations/webhooks/configure`
- `POST /api/integrations/sftp/batch`
- `POST /api/integrations/retry/{event_id}`
- `POST /api/cases/{case_id}/embedded-review-link`
- `GET /api/platform/status`
- `GET /api/ocr/pipeline`
- `GET /api/dashboard/operations`
- `GET /api/admin/tenant`
- `GET /api/admin/rbac`
- `GET /api/admin/audit-integrity`
- `GET /api/admin/templates/studio`
- `POST /api/admin/templates/studio`
- `GET /api/review/queue`
- `GET /api/verification/adapters`
- `POST /api/verification/adapters/{adapter_key}/configure`
- `GET /api/analytics/accuracy`
- `POST /api/analytics/corrections`

External systems that require real institution credentials return explicit `not_configured` states instead of pretending to verify live National ID, PAN, AML, liveness, or SFTP connections.

## Enterprise UX

The frontend is now organized as a route-backed enterprise workspace instead of one overloaded demo page:

- `/`: Command center for portfolio KPIs, platform readiness, work queues, and decision signals.
- `/cases`: Case management with intake, selected case detail, review, verification, export, and audit context.
- `/documents`: Document intake, full-packet upload, OCR evidence, extracted fields, and decision checklist.
- `/review`: Maker-checker workbench with assignment, comments, rework, correction capture, and audit history.
- `/verification`: Verification hub with case evidence, validation findings, registry adapter configuration, and adapter runs.
- `/templates`: Template studio and production extraction pipeline.
- `/integrations`: Integration center for CBS/LOS/CRM/DMS profiles, webhooks, SFTP batches, retry queue, and payload export.
- `/analytics`: Accuracy analytics for reviewer corrections, field confidence, and drift.
- `/admin`: Platform readiness and audit posture for tenant/security operations.

The visual system uses a Corporate Trust treatment: Plus Jakarta Sans typography, slate surfaces, indigo/violet actions, colored elevation shadows, rounded operational cards, a top module switcher instead of a bulky sidebar, and route-level density controls so each module stays focused.

## Run Locally

Backend:

```bash
make backend-install
make backend-dev
```

Frontend:

```bash
make frontend-install
make frontend-dev
```

Open `http://localhost:3000`. The frontend expects the API at `http://localhost:8010`.

## Verification

```bash
make test
```

Backend only:

```bash
make backend-test
```

Frontend only:

```bash
make frontend-build
```

## Gemma 4 26B

Local development defaults to deterministic fallback so the app works without GPU access:

```bash
LIPIOCR_GEMMA_ENABLED=false make backend-dev
```

On the remote server, use the existing vLLM endpoint:

```bash
LIPIOCR_GEMMA_ENABLED=true
LIPIOCR_GEMMA_API_BASE=http://host.docker.internal:8003/v1
LIPIOCR_GEMMA_MODEL=gemma-4-26b-4bit
LIPIOCR_GEMMA_RETRIES=2
LIPIOCR_GEMMA_REQUIRE_JSON=true
```

## Production Foundations

LipiOCR now supports production-shaped foundations behind environment flags:

- PostgreSQL-capable repository via `LIPIOCR_REPOSITORY_BACKEND=sql` and `DATABASE_URL`.
- MinIO/S3 document storage via `LIPIOCR_STORAGE_BACKEND=s3`, `S3_ENDPOINT_URL`, and `S3_BUCKET`.
- OCR provider selection via `LIPIOCR_OCR_PROVIDER=mock|tesseract|paddleocr|gemma_vision`.
- Gemma 4 strict JSON extraction with retry/timeout controls.
- API-key RBAC enforcement via `LIPIOCR_API_AUTH_ENABLED=true` and `LIPIOCR_API_KEYS=key:role,key2:role2`.

Local development keeps `memory`, `local`, `mock`, and auth-disabled defaults so the app runs without infrastructure. The Docker Compose profile defaults to SQL repository and MinIO/S3 storage.

API-key roles:

- `maker`: create cases, upload documents, classify/validate/verify.
- `checker`: review, approve/reject, export, webhook/review-link handoff.
- `auditor`: read/audit-oriented role for the next reporting phase.
- `admin`: all permissions.

## Docker Deployment

Prepare remote files:

```bash
make remote-sync
```

On the server:

```bash
cd /data/lipiocr/infra
cp .env.example .env
docker compose --env-file .env up -d --build
```

Default ports:

- Frontend: `http://server:3020`
- API: `http://server:8020`
- MinIO API: `http://server:9100`
- MinIO Console: `http://server:9101`

For locked-down servers, override `LIPIOCR_FRONTEND_PORT`, `LIPIOCR_API_PORT`, `NEXT_PUBLIC_API_BASE_URL`, and `LIPIOCR_CORS_ORIGINS` in `infra/.env`.

## OCR Providers

The local development default provider is `mock`:

```bash
LIPIOCR_OCR_PROVIDER=mock make backend-dev
```

Remote deployments should use Gemma vision OCR/ICR when the vLLM endpoint supports image input:

```bash
LIPIOCR_OCR_PROVIDER=gemma_vision
LIPIOCR_GEMMA_ENABLED=true
LIPIOCR_GEMMA_API_BASE=http://host.docker.internal:8003/v1
LIPIOCR_GEMMA_MODEL=gemma-4-26b-4bit
```

`gemma_vision` sends the full page image to Gemma and asks for every printed or handwritten Nepali/English line as structured OCR evidence. Handwritten lines are retained as `handwriting_ocr` fields for human review and template mapping.

Optional OCR dependencies can be installed later:

```bash
cd backend
.venv/bin/python -m pip install -e '.[ocr]'
```

Then run with `LIPIOCR_OCR_PROVIDER=tesseract` or `LIPIOCR_OCR_PROVIDER=paddleocr`.

## Pilot Notes

The first demo is intentionally workflow-first. For bank pilots, keep custom training out of scope until real samples, review feedback, accuracy reports, and integration requirements are understood.
