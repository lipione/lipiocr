# Nepal Document Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Nepal-first document intelligence for variants, full OCR ledgering, visual assets, bilingual entity records, and reviewer correction memory.

**Architecture:** Extend the existing `document_intelligence` service instead of adding a second pipeline. `apply_document_intelligence` becomes the single place that attaches document variant, assets, ledger, entity records, and correction metadata to `FinancialDocument` and `DocumentRecord`.

**Tech Stack:** Python FastAPI/Pydantic backend, existing deterministic OCR and LipiCore extraction path, React/Next frontend, TypeScript workspace types.

---

### Task 1: Backend Intelligence Contract

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_document_intelligence.py`

- [ ] Write failing tests for variant, assets, ledger, and entity records.
- [ ] Add `DocumentAsset`, `EvidenceLedgerEntry`, and optional intelligence fields to `FinancialDocument` and `DocumentRecord`.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_document_intelligence.py -q`.

### Task 2: Variant, Ledger, Asset, Entity Implementation

**Files:**
- Modify: `backend/app/services/document_intelligence.py`

- [ ] Add a Nepal variant registry with scored OCR signals.
- [ ] Build an evidence ledger from every OCR block.
- [ ] Detect photo, fingerprint, signature, stamp/seal, and chip assets from block metadata and OCR text.
- [ ] Build bilingual entity records from canonical fields and normalizations.
- [ ] Attach intelligence payload to the document in `apply_document_intelligence`.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_document_intelligence.py -q`.

### Task 3: API Persistence and Correction Memory

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/accuracy_analytics.py`
- Modify: `backend/tests/test_enterprise_completion_api.py`

- [ ] Write failing API tests for standalone upload intelligence payload and correction memory.
- [ ] Copy intelligence fields when converting a standalone document to a case document.
- [ ] Include document variant in uploaded `DocumentRecord` responses.
- [ ] Add correction memory to accuracy analytics.
- [ ] Run `cd backend && .venv/bin/python -m pytest tests/test_enterprise_completion_api.py -q`.

### Task 4: Frontend Intelligence Surface

**Files:**
- Modify: `frontend/src/types/workspace.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Modify: `frontend/scripts/workspace-types.test.mjs`

- [ ] Add TypeScript models for document assets, ledger entries, variant metadata, and entity records.
- [ ] Show embedded intelligence for standalone documents instead of hiding it.
- [ ] Add compact panels for variant, evidence ledger, assets, and bilingual entity records.
- [ ] Run `cd frontend && npm run lint && npm run test && npm run build`.

### Task 5: End-to-End Verification

**Files:**
- No new files.

- [ ] Run full backend tests from `backend`.
- [ ] Run frontend lint, tests, and build.
- [ ] Restart local backend/frontend servers if needed.
- [ ] Browser-check the document workspace for the new LipiCore intelligence sections.
