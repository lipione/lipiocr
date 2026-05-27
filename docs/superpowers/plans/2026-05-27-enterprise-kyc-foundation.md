# Enterprise KYC Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first enterprise LipiOCR slice for Nepal-focused KYC case processing using Gemma 4 26B as the reasoning model.

**Architecture:** The first slice is case-based instead of document-only. FastAPI exposes KYC case, document upload, review, export, AI health, and integration manifest APIs; OCR produces full-page evidence structures; Gemma 4 26B converts page evidence into normalized KYC fields and findings. The frontend becomes an enterprise review console, and Docker Compose targets `/data/lipiocr` with backend, worker-ready API, frontend, Postgres, Redis, and MinIO services.

**Tech Stack:** FastAPI, Pydantic v2, httpx, Next.js 16, React 19, Tailwind CSS, Docker Compose, Gemma 4 26B vLLM endpoint at `http://127.0.0.1:8003/v1`.

---

### Task 1: Backend Domain And Tests

**Files:**
- Create: `backend/tests/test_enterprise_cases_api.py`
- Create: `backend/tests/test_gemma_reasoning.py`
- Create: `backend/app/core/config.py`
- Replace: `backend/app/models.py`
- Create: `backend/app/services/gemma.py`
- Create: `backend/app/services/enterprise_extraction.py`
- Replace: `backend/app/services/repository.py`
- Replace: `backend/app/main.py`

- [ ] Write failing tests for creating KYC cases, uploading documents, evidence-backed extraction, review approval, export JSON, and Gemma response parsing.
- [ ] Run `cd backend && .venv/bin/python -m pytest -q` and verify the new tests fail because enterprise endpoints and Gemma service are missing.
- [ ] Implement Pydantic domain models for cases, documents, pages, OCR blocks, extracted fields, validations, audit events, integrations, and Gemma health.
- [ ] Implement a local repository interface with in-memory storage for this slice.
- [ ] Implement `GemmaReasoningClient` with configurable OpenAI-compatible base URL, model `gemma-4-26b-4bit`, JSON parsing, and deterministic fallback for local demos.
- [ ] Implement enterprise extraction orchestration that creates page OCR blocks, asks Gemma for fields/findings when enabled, and always returns evidence references.
- [ ] Add FastAPI routes for `/api/cases`, `/api/cases/{id}/documents`, `/api/cases/{id}/review`, `/api/cases/{id}/export`, `/api/ai/health`, and `/api/integrations/manifest`.
- [ ] Run backend tests and keep legacy pilot document tests passing or update them to call compatibility endpoints.

### Task 2: Enterprise Frontend

**Files:**
- Replace: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/package.json`

- [ ] Replace the document-only screen with a KYC case console: case list, metrics, upload, document packet, extracted fields, evidence panel, validation findings, review actions, export, and integration readiness.
- [ ] Configure the UI to use `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8010`.
- [ ] Run `cd frontend && npm run lint && npm run build` and fix all errors.

### Task 3: Deployment Shape

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `infra/docker-compose.yml`
- Create: `infra/.env.example`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] Add Docker images for backend and frontend so the remote server does not need host Node/npm.
- [ ] Add Compose services for API, frontend, Postgres, Redis, and MinIO.
- [ ] Configure API containers to reach host Gemma 4 26B using `http://host.docker.internal:8003/v1`.
- [ ] Add Make targets for enterprise local dev and remote sync.
- [ ] Document `/data/lipiocr` deployment and integration endpoints.

### Task 4: Verification And Remote Scaffold

**Files:**
- No source changes expected.

- [ ] Run `make test`.
- [ ] Browser-test the local app: create sample KYC case, upload a sample document, approve, export.
- [ ] Sync the scaffold to `ekduiteen@202.51.2.50:/data/lipiocr`.
- [ ] Verify remote files and Gemma 4 26B endpoint configuration without starting conflicting ports.

### Self-Review

- Scope is intentionally Phase 1. It does not promise registry checks, liveness, signature verification, fraud detection, custom model training, or complete Postgres persistence yet.
- Gemma 4 26B is used as the reasoning endpoint, with deterministic fallback so local development and CI do not depend on GPU availability.
- Every extracted field in the new API carries evidence, confidence, model/source, and review status.
