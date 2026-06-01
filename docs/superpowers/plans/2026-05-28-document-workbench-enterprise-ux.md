# Document Workbench Enterprise UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the document workbench into an enterprise-grade, reviewer-friendly flow where operators can upload any Nepal financial document, see full-page extraction, correct fields, use LipiCore bilingual/date intelligence, reanalyze or replace documents, and export clean data to downstream systems.

**Architecture:** Keep the current FastAPI + Next.js + Docker Compose architecture. Backend additions stay as focused lifecycle endpoints and deterministic tests. Frontend work remains inside the existing `EnterpriseWorkspace` component for this pass, using local helper functions to organize extracted fields and expose intelligent review cues without introducing a second design system.

**Tech Stack:** FastAPI, Pydantic v2, Next.js 16, React 19, Tailwind CSS, LipiCore intelligence endpoint, Docker Compose remote deployment.

---

### Task 1: Reviewer-First Document Workspace

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [x] **Step 1: Preserve two upload lanes but remove unclear choices**

Use explicit language:

```tsx
{[
  { value: "application", label: "Application Documents" },
  { value: "standalone", label: "Document Library" },
]}
```

Expected behavior: application uploads attach to a KYC/onboarding file; library uploads analyze any loose document before it is linked to an application.

- [x] **Step 2: Add search to application and document selectors**

Use `applicationSearch`, `documentSearch`, `matchesSearch`, `filteredCases`, and `filteredStandaloneDocuments` so long lists remain usable.

- [x] **Step 3: Make preview and data correction a true split view**

Change the workbench grid to keep preview and extracted data side by side from tablet width upward:

```tsx
<div className="grid min-w-0 gap-4 md:grid-cols-[minmax(0,0.95fr)_minmax(330px,1.05fr)] xl:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
```

- [x] **Step 4: Keep action controls visible**

Keep export, save, approve, reanalyze, replace, archive, copy, and move in the Extracted Data panel header so reviewers do not hunt for actions.

- [x] **Step 5: Verify frontend build**

Run:

```bash
cd frontend && npm run lint && npm run build
```

Expected: exit code 0.

### Task 2: Intelligent Field Review

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [x] **Step 1: Group extracted fields by business meaning**

Use `fieldGroupMeta()` and `groupExtractionFields()` to create Identity, Address, Dates, Contact, Banking, Amounts, Other, and Raw OCR groups.

- [x] **Step 2: Render correction inputs by group**

Replace the flat `editableExtractionFields.map(...)` renderer with `groupedEditableFields.map(...)`, keeping each field editable through the existing `fieldDrafts` state.

- [x] **Step 3: Show changed values clearly**

Keep the existing changed-state styling:

```tsx
changed ? "border-indigo-300 bg-indigo-50/60" : "border-slate-200 bg-white"
```

- [x] **Step 4: Verify correction path**

Upload/select a document, edit one field, press Save, and confirm the correction remains after reload.

### Task 3: LipiCore Bilingual and Calendar Intelligence

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Existing backend service: `backend/app/services/document_intelligence.py`
- Existing backend service: `backend/app/services/calendar_intelligence.py`

- [x] **Step 1: Surface bilingual pairs**

Use `selectedDocumentIntelligence.language_pairs` and case-level `intelligence.data.language_pairs` to show Nepali/English related fields together.

- [x] **Step 2: Surface AD/BS checks**

Show `semanticChecks` from LipiCore cross-checks, including date-pair status and message.

- [x] **Step 3: Do not expose internal model names**

Use LipiCore labels only in UI copy.

- [x] **Step 4: Verify intelligence panel**

Open `/documents`, select an application document with intelligence output, and confirm bilingual/date cues appear without blocking correction.

### Task 4: Document Lifecycle for Attached Documents

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_enterprise_cases_api.py`
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [x] **Step 1: Add case document source lookup**

Map a case document id back to the stored upload filename using `document_uploaded` and `document_processed` audit events.

- [x] **Step 2: Add attached-document reanalysis endpoint**

Implement:

```http
POST /api/cases/{case_id}/documents/{document_id}/reanalyze
```

Expected behavior: reuse the original upload, replace the matching document fields/findings, preserve the same document id, and append `document_reanalyzed`.

- [x] **Step 3: Add attached-document replacement endpoint**

Implement:

```http
POST /api/cases/{case_id}/documents/{document_id}/replace
```

Expected behavior: accept a replacement upload, preserve the same document id, update fields/findings, and append upload/replaced audit events.

- [x] **Step 4: Add frontend controls for application documents**

Show Reanalyze and Replace in the application-document lane as well as the standalone lane.

- [x] **Step 5: Verify backend tests**

Run:

```bash
cd backend && uv run pytest backend/tests/test_enterprise_cases_api.py -q
```

Expected: attached document reanalysis and replacement tests pass.

### Task 5: Export Readiness and Operator Clarity

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [x] **Step 1: Add reviewer-readable summary metrics**

Keep Fields, Needs Check, and OCR Text counts visible.

- [x] **Step 2: Add export readiness panel**

Show whether data is ready, needs correction, or has missing values before exporting.

- [x] **Step 3: Keep labels business-facing**

Avoid unexplained terms such as packets, evidence blocks, sync templates, and raw CBS/LOS references in the primary document screen.

### Task 6: Verification and Remote Deployment

**Files:**
- Modify: remote deployment at `/data/lipiocr`

- [x] **Step 1: Run full local verification**

Run:

```bash
make test
```

Expected: backend tests, frontend lint, and frontend build all pass.

- [x] **Step 2: Sync and rebuild remote**

Run:

```bash
make remote-sync
ssh -i ~/.ssh/lipiocr_codex_ed25519 -p 41447 ekduiteen@202.51.2.50 'cd /data/lipiocr/infra && docker compose --env-file .env up -d --build api frontend'
```

- [x] **Step 3: Browser verify**

Open:

```text
http://localhost:8100/documents
```

Expected: upload lanes, split preview, editable grouped fields, LipiCore intelligence, lifecycle actions, and export preview are visible and usable.

### Self-Review

- The plan keeps the enterprise promise but removes unexplained jargon from the main workflow.
- The system still supports application-attached and standalone document processing.
- Unknown documents remain analyzable through the Document Library.
- Bilingual/date intelligence is shown as reviewer help, not as a false promise of fully automatic approval.
