# LipiOCR Enterprise

LipiOCR Enterprise is a Nepal-focused document intelligence platform for financial institutions. It helps banks, cooperatives, MFIs, wallets, remittance companies, insurers, lenders, brokers, and merchant banks process KYC/KYB documents, onboarding packets, forms, and archives with evidence-backed OCR/ICR, bilingual normalization, human review, audit controls, and integration-ready exports.

LipiOCR is not positioned as "OCR only." The core product is LipiCore-assisted document understanding:

- OCR and ICR evidence capture.
- Bilingual Nepali/English field pairing.
- BS/AD date normalization.
- Nepal location registry normalization for province, district, municipality/gaunpalika, legacy VDC wording, and ward checks.
- Address intelligence RAG for Nepal KYC: administrative registry matching, road/tole evidence, fuzzy address suggestions, and reviewer-approved learning.
- Nepali name lexicon correction candidates for reviewer-safe name repair.
- Entity reconciliation across documents.
- Confidence repair with audit reasons.
- Permanent Nepal identity templates for citizenship, National ID, passport, and driving license, with Super Admin governance.
- Reviewer-safe correction before export.

## What It Does

- Reads full-page documents and keeps OCR evidence: pages, blocks, bounding boxes, raw text, confidence, and page references.
- Supports Nepal document workflows: old/new citizenship, front/back citizenship copies on one photocopied page, National ID, passport, smart driving license, PAN/VAT, bank KYC/account forms, IPO/C-ASBA forms, cheques, statements, KYB documents, and unknown document packets.
- Extracts fields using both full-page LipiCore reasoning and tenant-specific templates.
- Tracks visual evidence regions such as photos, signatures, stamps, and thumbprints where templates or OCR evidence identify them. It does not perform biometric, signature, or fraud verification unless a configured adapter provides that capability.
- Lets reviewers correct uncertain fields while preserving original OCR values and audit history.
- Normalizes Nepali and English fields into export-ready structures for downstream CBS, LOS, CRM, DMS, registry, and archive systems.
- Provides validation, verification adapter scaffolding, maker-checker workflow, comments, rework, and approval.
- Exports JSON/API payloads and supports signed webhooks, SFTP batch receipts, idempotency keys, and embedded review links.
- Supports on-prem/private-cloud deployment and SaaS-oriented tenant controls.

## Documentation

Start with [docs/README.md](./docs/README.md).

Key references:

- [Developer Onboarding](./docs/developer-onboarding.md)
- [Architecture](./docs/architecture.md)
- [Model Training Strategy](./docs/model-training-strategy.md)
- [Interface System](./.interface-design/system.md)
- [API Reference](./docs/api-reference.md)
- [Configuration](./docs/configuration.md)
- [Deployment](./docs/deployment.md)
- [Production Security Checklist](./docs/security/production-security-checklist.md)
- [Incident Response Runbook](./docs/runbooks/incident-response.md)
- [Disaster Recovery Runbook](./docs/runbooks/disaster-recovery.md)

## Repository Layout

```text
backend/   FastAPI API, OCR/LipiCore services, repositories, jobs, security
frontend/  Next.js enterprise workspace
infra/     Docker Compose production-shaped stack
deploy/    On-prem pack: Compose docs, Helm skeleton, scripts, Nginx reference
docs/      Product, developer, API, deployment, security, and runbook docs
```

## Quick Start

Install dependencies:

```bash
make backend-install
make frontend-install
```

Run the backend:

```bash
make backend-dev
```

Run the frontend:

```bash
make frontend-dev
```

Open:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8010`
- API docs: `http://localhost:8010/docs`
- Demo extraction lab: `http://localhost:3000/demo`

Local defaults use memory storage, local uploads, mock OCR, disabled auth, and disabled LipiCore remote calls so the app runs without infrastructure. Mock mode is for UI, workflow, and test development only. Real pilots must configure an approved OCR/LipiCore provider and benchmark it against institution-approved samples.

## Demo Extraction Lab

The `/demo` route is the fastest way to test the product story before a pilot meeting. It accepts single-page or multipage uploads, runs the demo extraction API, shows a scanning overlay, displays document understanding, keeps raw OCR evidence, exposes editable extracted fields, shows bilingual normalization where available, and includes visual evidence crops such as photo and fingerprint/thumbprint regions when detected.

Local test:

```bash
curl -F "file=@/path/to/sample.jpg" \
  -F prefer_lipicore=true \
  http://localhost:8010/api/demo/extract
```

Multipage test:

```bash
curl -F "files=@/path/to/page-1.jpg" \
  -F "files=@/path/to/page-2.jpg" \
  -F prefer_lipicore=true \
  http://localhost:8010/api/demo/extract-pages
```

## Verification

Run the full gate before committing:

```bash
make test
```

Focused checks:

```bash
make backend-test
make frontend-test
make frontend-build
```

## Local OCR/LipiCore Modes

Mock mode:

```bash
LIPIOCR_OCR_PROVIDER=mock LIPIOCR_GEMMA_ENABLED=false make backend-dev
```

Gemma vision mode:

```bash
LIPIOCR_OCR_PROVIDER=gemma_vision \
LIPIOCR_GEMMA_ENABLED=true \
LIPIOCR_GEMMA_API_BASE=http://127.0.0.1:8003/v1 \
LIPIOCR_GEMMA_MODEL=gemma-4-26b-4bit \
make backend-dev
```

Optional local OCR dependencies:

```bash
cd backend
.venv/bin/python -m pip install -e '.[ocr]'
```

Then run with `LIPIOCR_OCR_PROVIDER=tesseract` or `LIPIOCR_OCR_PROVIDER=paddleocr`.

## OCR And Vision Training Direction

LipiOCR should train a model family, not one all-purpose model. Fine-tuned PaddleOCR should be the primary trainable OCR layer for printed Nepali/English. A separate handwriting recognizer should be trained on reviewer-approved line crops. A Gemma-style vision model should be fine-tuned as LipiVision for document understanding, field mapping, bilingual reasoning, and structured JSON extraction. LipiCore remains the verifier and correction layer for Nepal names, addresses, BS/AD dates, cross-document reconciliation, and reviewer-safe confidence repair.

See [Model Training Strategy](./docs/model-training-strategy.md).

## Auth And API Keys

Local development can run with auth disabled:

```bash
LIPIOCR_API_AUTH_ENABLED=false make backend-dev
```

When auth is enabled, send an API key:

```bash
curl http://localhost:8010/api/cases \
  -H 'X-LipiOCR-API-Key: maker-demo-key'
```

Or create a session:

```bash
curl -i -X POST http://localhost:8010/api/auth/session \
  -H 'Content-Type: application/json' \
  -d '{"username":"maker.one","role":"maker","tenant_id":"demo-institution"}'
```

Use `super_admin` only for platform-level operations such as revising permanent Nepal identity templates. Tenant `admin` users can manage custom templates but cannot overwrite permanent ID formats.

Real deployment keys must be generated and stored outside Git:

```bash
openssl rand -hex 32
```

See [Configuration](./docs/configuration.md) for all environment variables.

## Production-Shaped Compose

```bash
cp infra/.env.example infra/.env
deploy/scripts/validate-env.sh infra/.env
make compose-build
make compose-up
deploy/scripts/health-check.sh http://localhost:8020
```

Default Compose ports:

- Frontend: `http://localhost:3020`
- API: `http://localhost:8020`
- MinIO API: `127.0.0.1:9100`
- MinIO Console: `127.0.0.1:9101`

See [Deployment](./docs/deployment.md) and [deploy/compose/README.md](./deploy/compose/README.md) before using this for a real institution.

## Current Production Foundations

Implemented:

- PostgreSQL-capable repository and local memory fallback.
- S3/MinIO document storage and local upload fallback.
- OCR provider interface for mock, Tesseract, PaddleOCR, and Gemma vision.
- Session and API-key auth, RBAC, upload hardening, signed previews.
- Tenant context, tenant registry, and tenant-scoped object keys.
- Permanent Nepal identity templates for citizenship, National ID, passport, and driving license.
- Template studio, multipage drafts, profiles, approval, rollback, import/export, and test runs.
- Nepal administrative location resolver for province, district, municipality/gaunpalika, legacy VDC wording, and ward checks.
- Tenant-safe address evidence store for approved road, street, tole, and area aliases.
- Nepali name lexicon suggestions for reviewer-safe correction candidates.
- Accuracy analytics and benchmark report scaffolding.
- Signed webhook/SFTP delivery receipts with idempotency keys.
- Compliance reports, backup readiness, incident response, and DR runbooks.
- Docker Compose, Helm skeleton, Nginx subpath reference, backup/restore/health scripts.

Still requires institution-specific production integration:

- Real SSO/OIDC/SAML.
- Real National ID/PAN/VAT/AML/liveness/CBS/LOS/DMS credentials.
- Real Nepali document accuracy benchmark dataset.
- Institution-approved address/name reference datasets and review governance.
- Reviewer-approved training dataset capture, export, model registry, and benchmark governance.
- External worker orchestration and production migration policy.
- Per-tenant encryption key management and observability stack.

## Product Boundary

LipiOCR should not claim fully automatic approval, perfect handwriting recognition, fraud detection, signature verification, or direct registry verification unless those adapters are actually configured and tested. The production posture is AI-assisted extraction with human verification, audit controls, and explicit integration states.
