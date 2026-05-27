# LipiOCR Enterprise

LipiOCR Enterprise is a Nepal-focused KYC and financial document intelligence platform. It is designed for banks, cooperatives, MFIs, wallets, remittance companies, insurers, and lenders that need evidence-backed document extraction, human review, auditability, and integration with existing CBS/LOS/CRM/DMS systems.

## Current Scope

- Case-based FastAPI backend for KYC/KYB/document processing.
- Full-page OCR evidence model with blocks, bounding boxes, confidence, and page references.
- Gemma 4 26B reasoning client for OpenAI-compatible vLLM endpoints.
- Enterprise review console for case creation, document upload, evidence inspection, validation findings, approval, audit, and JSON export.
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
        +-- Nepal KYC/KYB validation and review workflow
        +-- Integration-ready export API
```

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
```

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

## OCR Providers

The default provider is `mock`:

```bash
LIPIOCR_OCR_PROVIDER=mock make backend-dev
```

Optional OCR dependencies can be installed later:

```bash
cd backend
.venv/bin/python -m pip install -e '.[ocr]'
```

Then run with `LIPIOCR_OCR_PROVIDER=tesseract` or `LIPIOCR_OCR_PROVIDER=paddleocr`.

## Pilot Notes

The first demo is intentionally workflow-first. For bank pilots, keep custom training out of scope until real samples, review feedback, accuracy reports, and integration requirements are understood.
