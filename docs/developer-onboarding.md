# Developer Onboarding

This guide gets a new engineer from clone to a working LipiOCR development environment.

## Prerequisites

- macOS or Linux shell.
- Python 3.9 or newer.
- Node.js compatible with Next.js 16.
- Docker and Docker Compose for production-shaped local runs.
- Optional: Tesseract, PaddleOCR, or a Gemma vision endpoint for real OCR/ICR.
- Optional for ML work: a GPU environment for PaddleOCR, handwriting OCR, YOLO/RT-DETR, or Gemma-style LoRA/QLoRA fine-tuning.

The default local path uses mock OCR and in-memory storage so the product runs without GPU, Postgres, Redis, or MinIO.

## Repository Map

| Path | Purpose |
| --- | --- |
| `backend/app/main.py` | Main FastAPI app and case/document workflow endpoints. |
| `backend/app/core/config.py` | Environment-driven settings. |
| `backend/app/models.py` | Pydantic domain models for cases, documents, templates, review, and extraction. |
| `backend/app/services/` | OCR, LipiCore reasoning, validation, extraction, integrations, templates, review, security. |
| `backend/app/services/demo_extraction.py` | Demo extraction lab service for single-page/multipage uploads, document understanding, profile-assisted extraction, and visual evidence crops. |
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
- Demo extraction lab: `http://localhost:3000/demo`

Local defaults:

- API auth disabled.
- Repository backend auto-falls back to memory unless `DATABASE_URL` is set.
- Storage backend auto-falls back to local uploads.
- OCR provider is `mock`.
- LipiCore/Gemma calls are disabled.

## Day-One Product Workflow

1. Open `http://localhost:3000`.
2. Use the product home to enter the workspace.
3. Open `Demo` at `/demo` when you need to quickly test a Nepali citizenship, ASBA, or other KYC sample without creating a case.
4. Go to `Cases` and create a case.
5. Upload one or more documents under the selected case.
6. Go to `Documents` for standalone packet/document processing.
7. Inspect full-page OCR evidence, extracted fields, confidence, and review checklist.
8. Correct fields in the review workflow.
9. Run validation, verification, export profile, and audit views.
10. Use `Templates` to draft or import a template for known document formats.
11. Use `Admin` to inspect tenant settings, RBAC, compliance, and address dataset controls.
12. Use `Integrations` to inspect REST, webhook, SFTP, and retry flows.

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
LIPIOCR_GEMMA_MODEL=lipione-gemma4-12b \
LIPIOCR_LEGACY_OCR_FALLBACK_ENABLED=false \
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

## Demo Extraction Lab

The demo lab is useful for tomorrow-style product demos and OCR debugging. It supports one file through `/api/demo/extract` and multipage uploads through `/api/demo/extract-pages`.

Single-page API test:

```bash
curl -s -F "file=@/path/to/citizenship.jpg" \
  -F prefer_lipicore=true \
  http://localhost:8010/api/demo/extract
```

Multipage API test:

```bash
curl -s -F "files=@/path/to/front.jpg" \
  -F "files=@/path/to/back.jpg" \
  -F prefer_lipicore=true \
  http://localhost:8010/api/demo/extract-pages
```

Expected response shape:

- `document_type`
- `document_understanding`
- `summary`
- `fields`
- `raw_text`
- `warnings`
- `providers`
- `pages` for multipage requests
- `visual_assets` for crops such as photo and fingerprint/thumbprint when available

Operator-facing UI should call the reasoning layer LipiCore. Keep provider and model names in diagnostics, configuration, or admin-only contexts.

## Model Training Workflows

Read [Model Training Strategy](./model-training-strategy.md) before adding training-data behavior.

Training work should create approved datasets from the product:

1. Save original files and page images.
2. Save OCR evidence with boxes and confidence.
3. Save reviewer-approved corrected fields.
4. Save crop images for printed and handwritten text.
5. Save boxes for photo, fingerprint/thumbprint, signature, stamp, table, label, and value regions.
6. Export PaddleOCR, YOLO/COCO, LipiVision JSONL, and benchmark report formats.

Do not train from raw OCR guesses. Only reviewer-approved or manually labeled values are ground truth.

## Nepali Name Lexicon

The raw Nepali name dataset should stay outside Git. Build a compact local lexicon from an approved CSV:

```bash
cd backend
.venv/bin/python scripts/build_nepali_name_lexicon.py /path/to/NepaliNameDatasetKaggle.csv
```

The generated file defaults to `backend/storage/name-lexicon/nepali_name_lexicon.json` and is ignored by Git. Override with `LIPIOCR_NEPALI_NAME_LEXICON` when deploying a tenant-approved lexicon path.

The lexicon is used for correction candidates, not blind replacement. If OCR reads `kaki` but the Nepali/English pair and lexicon support `karki`, the reviewer should see a candidate with original value, suggested value, confidence, sources, and audit reason.

## Address Evidence Dataset

LipiOCR ships with a small safe development seed in `backend/app/data/address_evidence_seed.json`.
Tenant-approved evidence is stored outside Git by default:

```bash
export LIPIOCR_ADDRESS_EVIDENCE_PATH=storage/address-evidence/address_evidence.json
```

Use the Admin Address Dataset panel or `/api/reference/address-evidence/import` to add institution-approved road, street, and tole records.
Reviewer-corrected full home addresses must remain tenant-private. Convert only non-personal area, tole, road, or street names into reusable evidence.

Minimal CSV columns for local import tooling:

```text
district,local_level,ward,kind,name_en,aliases_en,confidence_weight
Kathmandu,Kathmandu Metropolitan City,26,area_or_tole,Samakhusi,"Samakushi|Samakhusi Tole",0.9
```

Use `tenant_private` evidence for institution-specific data. Shared reference data needs platform approval.

## Template Studio Workflow

1. Open `Templates`.
2. Upload a blank or sample form. Multipage PDFs are expanded into template pages when supported locally.
3. Let the system suggest document type, labels, preset fields, and quality checks.
4. Zoom and pan the canvas, then add, move, resize, rename, or remove boxes.
5. Save the draft.
6. Publish and approve the profile.
7. Run a test extraction against known samples before using the profile in a pilot.

Permanent templates for citizenship, National ID, passport, and smart driving license are platform templates. Tenant admins can build custom institution forms, but only `super_admin` can revise permanent identity templates.

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

Add training-data capture:

1. Add backend tests for approved correction export and rejected/unapproved sample exclusion.
2. Keep real KYC files, raw personal names, and full addresses outside Git.
3. Store original OCR value, corrected value, crop path, bounding box, confidence, source, and audit reason.
4. Export standard formats without leaking tenant-private data across tenants.
5. Update [Model Training Strategy](./model-training-strategy.md), [Architecture](./architecture.md), and [API Reference](./api-reference.md) when API shapes change.

Add a new template capability:

1. Add tests in `backend/tests/test_template_*.py`.
2. Update `backend/app/services/templates.py` or `template_profiles.py`.
3. Keep templates tenant-scoped and versioned.
4. Update the `Templates` frontend module if reviewers need a new control.
5. Update [Architecture](./architecture.md) and [API Reference](./api-reference.md).

Add or change reference intelligence:

1. Add backend tests for the reference store or resolver.
2. Keep customer-specific data tenant-private.
3. Return suggestions with source evidence and audit reasons.
4. Do not silently raise confidence unless another field, registry match, or approved evidence supports it.
5. Update [Configuration](./configuration.md), [Architecture](./architecture.md), and [API Reference](./api-reference.md) if operators need to know the behavior.

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

Template mapping looks wrong

- Check image quality, skew, and crop boundaries.
- Use zoom in the template studio and resize boxes manually.
- Confirm the document really matches the selected template or create a new tenant template variant.
- For citizenship/National ID front/back photocopies on one page, use document intelligence output and reviewer correction when one fixed coordinate template cannot cover every historical layout.

Name or address suggestions are missing

- Confirm the Nepali name lexicon was generated and mounted through `LIPIOCR_NEPALI_NAME_LEXICON`.
- Confirm address evidence exists through the Admin Address Dataset panel or `/api/reference/address-evidence`.
- Confirm the field key is a name/address-like key so document intelligence attaches suggestions.

Compose fails at startup

- Run `deploy/scripts/validate-env.sh infra/.env`.
- Replace all placeholder secrets in `infra/.env`.
- Check port conflicts for API, frontend, MinIO, and Postgres.
