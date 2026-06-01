# Developer Onboarding

This guide gets a new engineer from clone to a working LipiOCR development environment.

## Prerequisites

- macOS or Linux shell.
- Python 3.9 or newer.
- Node.js compatible with Next.js 16.
- Docker and Docker Compose for production-shaped local runs.
- Optional: Tesseract, PaddleOCR, or a Gemma vision endpoint for real OCR/ICR.

The default local path uses mock OCR and in-memory storage so the product runs without GPU, Postgres, Redis, or MinIO.

## Repository Map

| Path | Purpose |
| --- | --- |
| `backend/app/main.py` | Main FastAPI app and case/document workflow endpoints. |
| `backend/app/core/config.py` | Environment-driven settings. |
| `backend/app/models.py` | Pydantic domain models for cases, documents, templates, review, and extraction. |
| `backend/app/services/` | OCR, LipiCore reasoning, validation, extraction, integrations, templates, review, security. |
| `backend/app/repositories/` | Memory and SQL-backed persistence adapters. |
| `backend/app/jobs/` | Async job queue models and runner. |
| `backend/app/security/` | RBAC, session auth, tenant context, upload policy. |
| `backend/app/tenancy/` | Tenant registry, isolation helpers, object key namespacing. |
| `backend/app/integrations/` | Webhook/SFTP delivery and idempotency helpers. |
| `backend/app/compliance/` | Access, audit, retention, export, and backup readiness reports. |
| `frontend/src/app/` | Next.js route modules. |
| `frontend/src/components/` | Product UI components and workbench modules. |
| `frontend/src/lib/` | API client, auth client, error formatting, template canvas helpers. |
| `frontend/src/types/` | Frontend workspace and API-facing types. |
| `infra/` | Docker Compose production-shaped stack. |
| `deploy/` | On-prem deployment pack: Compose docs, Helm skeleton, scripts, Nginx config. |
| `docs/` | Product, developer, deployment, and runbook documentation. |

## First Local Setup

From the repository root:

```bash
make backend-install
make frontend-install
```

Create local environment files when you need to customize defaults:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

The current Make targets do not automatically load `backend/.env`; export variables in your shell or run with explicit prefixes when needed:

```bash
LIPIOCR_OCR_PROVIDER=mock LIPIOCR_API_AUTH_ENABLED=false make backend-dev
```

## Run The App

Start the backend:

```bash
make backend-dev
```

Start the frontend in another terminal:

```bash
make frontend-dev
```

Open:

- Frontend: `http://localhost:3000`
- API health: `http://localhost:8010/health`
- API docs: `http://localhost:8010/docs`

Local defaults:

- API auth disabled.
- Repository backend auto-falls back to memory unless `DATABASE_URL` is set.
- Storage backend auto-falls back to local uploads.
- OCR provider is `mock`.
- LipiCore/Gemma calls are disabled.

## Day-One Product Workflow

1. Open `http://localhost:3000`.
2. Use the product home to enter the workspace.
3. Go to `Cases` and create a case.
4. Upload one or more documents under the selected case.
5. Go to `Documents` for standalone packet/document processing.
6. Inspect full-page OCR evidence, extracted fields, confidence, and review checklist.
7. Correct fields in the review workflow.
8. Run validation, verification, export profile, and audit views.
9. Use `Templates` to draft or import a template for known document formats.
10. Use `Integrations` to inspect REST, webhook, SFTP, and retry flows.

## Auth During Development

Auth is controlled by `LIPIOCR_API_AUTH_ENABLED`.

When auth is disabled:

```bash
LIPIOCR_API_AUTH_ENABLED=false make backend-dev
```

The backend resolves a demo operator and most API calls work without a key.

When auth is enabled, use either a session cookie or an API key.

Session login:

```bash
curl -i -X POST http://localhost:8010/api/auth/session \
  -H 'Content-Type: application/json' \
  -d '{"username":"maker.one","role":"maker","tenant_id":"demo-institution","branch_code":"KTM-01"}'
```

API-key header:

```bash
curl http://localhost:8010/api/cases \
  -H 'X-LipiOCR-API-Key: maker-demo-key'
```

Development example keys are placeholders only. Generate real deployment keys with:

```bash
openssl rand -hex 32
```

Then configure:

```bash
LIPIOCR_API_KEYS=<maker-key>:maker,<checker-key>:checker,<admin-key>:admin,<super-admin-key>:super_admin
```

Roles:

- `maker`: create cases, upload documents, classify, validate, verify.
- `checker`: review, approve/reject, export, hand off review links.
- `auditor`: read audit and compliance posture.
- `admin`: tenant administration, integrations, custom templates, and operational controls.
- `super_admin`: platform administration and permanent Nepal identity template revision.

## Tests And Verification

Run the full gate before committing:

```bash
make test
```

Focused commands:

```bash
make backend-test
make frontend-test
make frontend-build
```

Backend targeted test example:

```bash
cd backend
.venv/bin/python -m pytest tests/test_document_jobs.py -q
```

Frontend targeted test example:

```bash
cd frontend
npm run test
```

## OCR And LipiCore Modes

Mock local mode:

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

Optional OCR libraries:

```bash
cd backend
.venv/bin/python -m pip install -e '.[ocr]'
```

Then use:

```bash
LIPIOCR_OCR_PROVIDER=tesseract make backend-dev
LIPIOCR_OCR_PROVIDER=paddleocr make backend-dev
```

## Nepali Name Lexicon

The raw Nepali name dataset should stay outside Git. Build a compact local lexicon from an approved CSV:

```bash
cd backend
.venv/bin/python scripts/build_nepali_name_lexicon.py /path/to/NepaliNameDatasetKaggle.csv
```

The generated file defaults to `backend/storage/name-lexicon/nepali_name_lexicon.json` and is ignored by Git. Override with `LIPIOCR_NEPALI_NAME_LEXICON` when deploying a tenant-approved lexicon path.

## Address Evidence Dataset

LipiOCR ships with a small safe development seed in `backend/app/data/address_evidence_seed.json`.
Tenant-approved evidence is stored outside Git by default:

```bash
export LIPIOCR_ADDRESS_EVIDENCE_PATH=storage/address-evidence/address_evidence.json
```

Use the Super Admin Address Dataset panel or `/api/reference/address-evidence/import` to add institution-approved road, street, and tole records.
Reviewer-corrected full home addresses must remain tenant-private. Convert only non-personal area, tole, road, or street names into reusable evidence.

## Persistence Modes

Memory/local development:

```bash
LIPIOCR_REPOSITORY_BACKEND=memory
LIPIOCR_STORAGE_BACKEND=local
```

SQL/S3 production shape:

```bash
LIPIOCR_REPOSITORY_BACKEND=sql
DATABASE_URL=postgresql://user:password@localhost:5432/lipiocr
LIPIOCR_STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET=lipiocr-documents
AWS_ACCESS_KEY_ID=<access-key>
AWS_SECRET_ACCESS_KEY=<secret-key>
```

Use Docker Compose when you want Postgres, Redis, MinIO, API, and frontend together:

```bash
cp infra/.env.example infra/.env
deploy/scripts/validate-env.sh infra/.env
make compose-up
```

## Common Development Tasks

Add or change an API endpoint:

1. Add or update backend tests in `backend/tests/`.
2. Update `backend/app/main.py` or a router in `backend/app/routers/`.
3. Keep auth permission checks explicit.
4. Update frontend API client usage if the response shape changes.
5. Update [API Reference](./api-reference.md).
6. Run focused tests, then `make test`.

Add a document intelligence behavior:

1. Update tests around `backend/app/services/document_intelligence.py`, `enterprise_extraction.py`, or `ocr.py`.
2. Preserve original OCR values and add normalized/corrected values separately.
3. Include audit reasons when confidence is repaired or values are derived.
4. Keep uncertain fields reviewer-editable.
5. Update docs if the behavior changes operator expectations.

Add a new template capability:

1. Add tests in `backend/tests/test_template_*.py`.
2. Update `backend/app/services/templates.py` or `template_profiles.py`.
3. Keep templates tenant-scoped and versioned.
4. Update the `Templates` frontend module if reviewers need a new control.
5. Update [Architecture](./architecture.md) and [API Reference](./api-reference.md).

## Coding Rules For This Repo

- Keep extraction evidence-backed: every exported value should trace to OCR, template, reviewer correction, or deterministic rule.
- Do not overwrite OCR text blindly; keep original, normalized, corrected, source field, confidence, and reason where applicable.
- Do not fake external checks. Use `not_configured`, sandbox, or explicit failure states.
- Keep tenant boundaries visible in new persistence, object keys, jobs, templates, exports, and audit events.
- Treat Nepali and English fields as paired data, not as competing strings.
- Keep production docs updated in the same change as production behavior.

## Troubleshooting

`401 {"detail":"Missing API key"}`

- Auth is enabled.
- Use `X-LipiOCR-API-Key` with a configured key, or create a session via `/api/auth/session`.
- For local demo work, run with `LIPIOCR_API_AUTH_ENABLED=false`.

Frontend says `Failed to fetch`

- Confirm backend is running at `http://localhost:8010`.
- Confirm `NEXT_PUBLIC_API_BASE_URL=http://localhost:8010`.
- Confirm CORS includes the frontend origin through `LIPIOCR_CORS_ORIGINS`.

Uploads fail

- Check upload size against `LIPIOCR_MAX_UPLOAD_BYTES`.
- Check MIME type and extension allowlists.
- Check `storage/uploads` permissions for local storage.

Gemma extraction returns fallback or empty data

- Confirm `LIPIOCR_GEMMA_ENABLED=true`.
- Confirm `LIPIOCR_GEMMA_API_BASE` points to the OpenAI-compatible vLLM endpoint.
- Confirm the selected model supports the requested text or vision input.
- Use mock mode if you only need UI/workflow development.

Compose fails at startup

- Run `deploy/scripts/validate-env.sh infra/.env`.
- Replace all placeholder secrets in `infra/.env`.
- Check port conflicts for API, frontend, MinIO, and Postgres.
