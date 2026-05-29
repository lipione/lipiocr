# Production Readiness Phase 1 Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split LipiOCR's largest backend and frontend modules into focused boundaries while preserving current product behavior.

**Architecture:** This phase is a behavior-preserving refactor. Backend endpoints move from the monolithic FastAPI module into routers, and frontend API/types/template utilities move out of the main workspace component. Existing tests and route behavior remain the acceptance baseline.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, React, TypeScript, Node test runner, ESLint.

---

## File Structure

### Backend files

- Create `backend/app/routers/__init__.py`: router package marker and router list.
- Create `backend/app/routers/health.py`: `/health` and `/api/ai/health`.
- Create `backend/app/routers/integration_manifest.py`: public integration manifest route.
- Create `backend/app/routers/templates.py`: template studio routes.
- Create `backend/app/app_context.py`: shared app singletons and helper accessors for settings, repository, storage, OCR provider, and LipiCore client.
- Modify `backend/app/main.py`: assemble app, include routers, keep only endpoints not yet moved in this phase.
- Create `backend/tests/test_router_structure.py`: verifies router modules import and expose `router`.
- Create `backend/tests/test_router_behavior.py`: verifies moved endpoints preserve behavior.

### Frontend files

- Create `frontend/src/types/workspace.ts`: shared workspace and API response types.
- Create `frontend/src/lib/api-client.ts`: API base resolution, stored key access, `apiJson`, and API errors.
- Move existing `frontend/src/lib/api-errors.ts`: keep error formatter consumed by `api-client`.
- Create `frontend/src/components/templates/template-studio.tsx`: Template Creation Studio UI and local handlers.
- Modify `frontend/src/components/enterprise-workspace.tsx`: import extracted types/API/template component.
- Create `frontend/scripts/api-client.test.mjs`: tests API error formatting and API base resolution helper.

## Task 1: Backend Router Structure Guard

**Files:**

- Create: `backend/tests/test_router_structure.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/app/routers/integration_manifest.py`
- Create: `backend/app/routers/templates.py`

- [ ] **Step 1: Write the failing router import test**

Create `backend/tests/test_router_structure.py`:

```python
import importlib


def test_production_router_modules_export_fastapi_router():
    module_names = [
        "app.routers.health",
        "app.routers.integration_manifest",
        "app.routers.templates",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert hasattr(module, "router")
        assert module.router.routes
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_structure.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers'`.

- [ ] **Step 3: Add router package skeletons**

Create `backend/app/routers/__init__.py`:

```python
from app.routers.health import router as health_router
from app.routers.integration_manifest import router as integration_manifest_router
from app.routers.templates import router as templates_router

__all__ = ["health_router", "integration_manifest_router", "templates_router"]
```

Create `backend/app/routers/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/__router_probe__/health")
def health_router_probe():
    return {"router": "health"}
```

Create `backend/app/routers/integration_manifest.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["integration-manifest"])


@router.get("/__router_probe__/integration-manifest")
def integration_manifest_router_probe():
    return {"router": "integration-manifest"}
```

Create `backend/app/routers/templates.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["templates"])


@router.get("/__router_probe__/templates")
def templates_router_probe():
    return {"router": "templates"}
```

- [ ] **Step 4: Run the router structure test**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_structure.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/routers backend/tests/test_router_structure.py
git commit -m "refactor: add backend router package"
```

## Task 2: Shared Backend App Context

**Files:**

- Create: `backend/app/app_context.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_router_behavior.py`

- [ ] **Step 1: Write the app context test**

Create `backend/tests/test_router_behavior.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_routes_remain_available_after_router_split():
    assert client.get("/health").json()["status"] == "ok"
    public_ai = client.get("/api/ai/health").json()
    assert public_ai["provider"] == "LipiCore"
    assert public_ai["model"] == "LipiCore"


def test_integration_manifest_remains_public_after_router_split():
    response = client.get("/api/integrations/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "LipiOCR Enterprise"
    assert "rest_api" in body["modes"]
```

- [ ] **Step 2: Run the behavior test before moving code**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_behavior.py -q
```

Expected: PASS. This is the behavior baseline for moved routes.

- [ ] **Step 3: Create shared app context**

Create `backend/app/app_context.py`:

```python
from pathlib import Path

from app.core.config import get_settings
from app.services.gemma import GemmaReasoningClient
from app.services.ocr import get_ocr_provider
from app.services.repository import repository
from app.services.storage import build_storage

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(settings.upload_dir)
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
object_storage = build_storage(settings)


def gemma_client() -> GemmaReasoningClient:
    return GemmaReasoningClient(settings)


def ocr_provider():
    return get_ocr_provider(settings.ocr_provider, settings=settings)
```

- [ ] **Step 4: Modify main imports to use app context**

In `backend/app/main.py`, replace the existing settings/repository/storage singleton setup with:

```python
from app.app_context import UPLOAD_DIR, gemma_client as _gemma_client, object_storage, ocr_provider, repository, settings
```

Then replace direct calls to:

```python
get_ocr_provider(settings.ocr_provider, settings=settings)
```

with:

```python
ocr_provider()
```

Remove no longer used imports from `backend/app/main.py`:

```python
from app.core.config import get_settings
from app.services.gemma import GemmaReasoningClient
from app.services.ocr import get_ocr_provider
from app.services.repository import repository
from app.services.storage import build_storage
```

- [ ] **Step 5: Run backend behavior tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_behavior.py tests/test_production_foundations.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/app_context.py backend/app/main.py backend/tests/test_router_behavior.py
git commit -m "refactor: centralize backend app context"
```

## Task 3: Move Public Health And Manifest Routes

**Files:**

- Modify: `backend/app/routers/health.py`
- Modify: `backend/app/routers/integration_manifest.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_router_behavior.py`

- [ ] **Step 1: Replace health router probe with real routes**

Update `backend/app/routers/health.py`:

```python
from typing import Dict, Optional

from fastapi import APIRouter, Request

from app.app_context import gemma_client, settings
from app.services.security import require_permission

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": "lipiocr-enterprise",
        "environment": settings.environment,
    }


@router.get("/api/ai/health")
def ai_health(http_request: Request, detail: Optional[str] = None):
    if detail == "internal":
        require_permission(settings, http_request, "view_audit")
        return gemma_client().health(include_internal=True)
    return gemma_client().health(include_internal=False)
```

- [ ] **Step 2: Replace integration manifest router probe with real route**

Update `backend/app/routers/integration_manifest.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["integration-manifest"])


@router.get("/api/integrations/manifest")
def integration_manifest():
    return {
        "product": "LipiOCR Enterprise",
        "country": "Nepal",
        "modes": ["manual_export", "rest_api", "webhooks", "sftp", "embedded_review"],
        "events": [
            "case.created",
            "document.processed",
            "review.required",
            "case.approved",
            "case.rejected",
            "export.completed",
        ],
        "core_endpoints": [
            "POST /api/cases",
            "POST /api/cases/{case_id}/documents",
            "GET /api/cases/{case_id}/export",
        ],
    }
```

- [ ] **Step 3: Include public routers in main**

In `backend/app/main.py`, after middleware setup, add:

```python
from app.routers import health_router, integration_manifest_router

app.include_router(health_router)
app.include_router(integration_manifest_router)
```

Remove the old route functions from `backend/app/main.py`:

```python
@app.get("/health")
def health() -> Dict[str, str]:
    ...

@app.get("/api/ai/health")
def ai_health(...):
    ...

@app.get("/api/integrations/manifest")
def integration_manifest():
    ...
```

- [ ] **Step 4: Run moved route tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_structure.py tests/test_router_behavior.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full backend suite**

Run:

```bash
cd backend && .venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/routers/health.py backend/app/routers/integration_manifest.py backend/app/main.py backend/tests/test_router_behavior.py
git commit -m "refactor: move public routes into routers"
```

## Task 4: Extract Frontend API Client

**Files:**

- Create: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Test: `frontend/scripts/api-client.test.mjs`

- [ ] **Step 1: Write failing frontend API client test**

Create `frontend/scripts/api-client.test.mjs`:

```javascript
import assert from "node:assert/strict";
import test from "node:test";

import { formatApiError } from "../src/lib/api-errors.ts";
import { resolveApiBaseFromConfig } from "../src/lib/api-client.ts";

test("resolveApiBaseFromConfig returns configured URL", () => {
  assert.equal(
    resolveApiBaseFromConfig({
      configured: "https://example.test/api",
      basePath: "",
      apiPort: "8020",
      origin: "https://ai.silverlining.com.np",
      hostname: "ai.silverlining.com.np",
      protocol: "https:",
    }),
    "https://example.test/api",
  );
});

test("resolveApiBaseFromConfig supports reverse-proxy base path", () => {
  assert.equal(
    resolveApiBaseFromConfig({
      configured: "auto",
      basePath: "/lipiocr",
      apiPort: "8020",
      origin: "https://ai.silverlining.com.np",
      hostname: "ai.silverlining.com.np",
      protocol: "https:",
    }),
    "/lipiocr",
  );
});

test("formatApiError hides raw missing-key JSON", () => {
  assert.equal(formatApiError(401, '{"detail":"Missing API key"}'), "Operator API key required");
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run:

```bash
cd frontend && npm run test
```

Expected: FAIL with module not found for `../src/lib/api-client.ts`.

- [ ] **Step 3: Create API client module**

Create `frontend/src/lib/api-client.ts`:

```typescript
import { formatApiError } from "./api-errors";

export const API_KEY_STORAGE_KEY = "lipiocr.operatorApiKey";

type ApiBaseConfig = {
  configured: string;
  basePath: string;
  apiPort: string;
  origin: string;
  hostname: string;
  protocol: string;
};

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail || `${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export function resolveApiBaseFromConfig(config: ApiBaseConfig) {
  if (config.configured !== "auto") {
    return config.configured;
  }
  const basePath = config.basePath.replace(/\/$/, "");
  if (basePath) {
    return basePath;
  }
  return `${config.protocol}//${config.hostname}:${config.apiPort}`;
}

export function resolveApiBase() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
  if (typeof window === "undefined") {
    return configured === "auto" ? "http://localhost:8010" : configured;
  }
  return resolveApiBaseFromConfig({
    configured,
    basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
    apiPort: process.env.NEXT_PUBLIC_API_PORT ?? "13001",
    origin: window.location.origin,
    hostname: window.location.hostname,
    protocol: window.location.protocol,
  });
}

export function storedApiKey() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(API_KEY_STORAGE_KEY)?.trim() ?? "";
}

export function isUnauthorized(error: unknown) {
  return error instanceof ApiRequestError && error.status === 401;
}

const API_BASE = resolveApiBase();

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const apiKey = storedApiKey();
  if (apiKey && !headers.has("X-LipiOCR-API-Key")) {
    headers.set("X-LipiOCR-API-Key", apiKey);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiRequestError(response.status, formatApiError(response.status, detail));
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 4: Replace local API helpers in workspace**

In `frontend/src/components/enterprise-workspace.tsx`, remove local definitions for:

```typescript
function resolveApiBase() { ... }
const API_BASE = resolveApiBase();
const API_KEY_STORAGE_KEY = "lipiocr.operatorApiKey";
class ApiRequestError extends Error { ... }
function storedApiKey() { ... }
function isUnauthorized(error: unknown) { ... }
async function apiJson<T>(path: string, init?: RequestInit): Promise<T> { ... }
```

Add import:

```typescript
import { API_KEY_STORAGE_KEY, apiJson, isUnauthorized, storedApiKey } from "../lib/api-client";
```

Remove import:

```typescript
import { formatApiError } from "../lib/api-errors";
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm run test
```

Expected: PASS.

- [ ] **Step 6: Run frontend build**

Run:

```bash
make frontend-build
```

Expected: lint and Next build pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add frontend/src/lib/api-client.ts frontend/src/components/enterprise-workspace.tsx frontend/scripts/api-client.test.mjs
git commit -m "refactor: extract frontend api client"
```

## Task 5: Extract Shared Frontend Workspace Types

**Files:**

- Create: `frontend/src/types/workspace.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Test: `frontend/scripts/workspace-types.test.mjs`

- [ ] **Step 1: Write type export smoke test**

Create `frontend/scripts/workspace-types.test.mjs`:

```javascript
import assert from "node:assert/strict";
import test from "node:test";

import { workspaceSections } from "../src/types/workspace.ts";

test("workspaceSections exposes production route order", () => {
  assert.deepEqual(workspaceSections, [
    "command",
    "cases",
    "documents",
    "review",
    "verification",
    "templates",
    "integrations",
    "analytics",
    "admin",
  ]);
});
```

- [ ] **Step 2: Run the type smoke test to verify it fails**

Run:

```bash
cd frontend && npm run test
```

Expected: FAIL with module not found for `../src/types/workspace.ts`.

- [ ] **Step 3: Create shared workspace type module**

Create `frontend/src/types/workspace.ts` and move TypeScript type definitions from the top of `frontend/src/components/enterprise-workspace.tsx` into this file. Include this exported constant:

```typescript
export const workspaceSections = [
  "command",
  "cases",
  "documents",
  "review",
  "verification",
  "templates",
  "integrations",
  "analytics",
  "admin",
] as const;

export type WorkspaceSection = (typeof workspaceSections)[number];
```

Keep all exported names used by `EnterpriseWorkspace`, including:

```typescript
export type CaseType = "individual_kyc" | "business_kyb" | "loan_onboarding" | "document_digitization";
export type CaseStatus = "created" | "processing" | "review_required" | "approved" | "rejected" | "exported";
export type DocumentLane = "application" | "standalone";
export type PreviewOverlayMode = "clean" | "evidence" | "blocks";
```

Move the remaining object types exactly as named in the component:

- `DocumentType`
- `OcrBlock`
- `OcrPage`
- `ExtractedField`
- `ValidationFinding`
- `KycCase`
- `TemplateStudio`
- `TemplateProfilePage`
- `TemplateProfileField`
- `TemplateDraft`
- `DocumentRecord`
- `DocumentVersion`
- `ResourceState`
- all integration, review, verification, analytics response types used by the component.

- [ ] **Step 4: Import shared types in workspace**

In `frontend/src/components/enterprise-workspace.tsx`, replace local type declarations with:

```typescript
import type {
  AccuracyAnalytics,
  AiHealth,
  AssignmentResponse,
  CaseIntelligence,
  CaseStatus,
  CaseType,
  ClassificationResponse,
  CorrectionResponse,
  DocumentLane,
  DocumentRecord,
  DocumentType,
  EmbeddedReviewLinkResponse,
  ExportProfileResponse,
  ExtractedField,
  IntegrationOperations,
  IntegrationProfilesResponse,
  KycCase,
  OcrBlock,
  OcrPage,
  OcrPipelineProfile,
  PlatformStatus,
  PreviewOverlayMode,
  ResourceState,
  ReviewWorkbench,
  SplitPreviewResponse,
  TemplateDraft,
  TemplateProfileField,
  TemplateProfilePage,
  TemplateStudio,
  ValidationResponse,
  VerificationAdapter,
  VerificationAdapterRunResponse,
  VerificationAdaptersResponse,
  VerificationResponse,
  WebhookTestResponse,
  WorkspaceSection,
} from "../types/workspace";
```

- [ ] **Step 5: Run frontend tests and build**

Run:

```bash
cd frontend && npm run test
make frontend-build
```

Expected: tests, lint, and build pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src/types/workspace.ts frontend/src/components/enterprise-workspace.tsx frontend/scripts/workspace-types.test.mjs
git commit -m "refactor: extract workspace types"
```

## Task 6: Extract Template Studio Component Boundary

**Files:**

- Create: `frontend/src/components/templates/template-studio.tsx`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Test: `frontend/scripts/template-canvas.test.mjs`

- [ ] **Step 1: Strengthen existing canvas test**

Update `frontend/scripts/template-canvas.test.mjs` with this additional test:

```javascript
test("resizes southeast handle without moving northwest anchor", () => {
  const bbox = computeTemplateDragBbox({
    mode: "resize-se",
    startBbox: [100, 100, 180, 150],
    startClientX: 100,
    startClientY: 100,
    clientX: 200,
    clientY: 170,
    page,
    canvasRect,
  });

  assert.deepEqual(bbox, [100, 100, 300, 290]);
});
```

- [ ] **Step 2: Run template canvas tests**

Run:

```bash
cd frontend && npm run test
```

Expected: PASS before component extraction. This protects canvas geometry during the move.

- [ ] **Step 3: Create Template Studio component**

Create `frontend/src/components/templates/template-studio.tsx` with props matching the state and handlers currently used by the `section === "templates"` block:

```typescript
"use client";

import { FileCog, FileSearch, FileText, Layers3, Plus, Upload } from "lucide-react";
import { PointerEvent as ReactPointerEvent, RefObject } from "react";

import { computeTemplateDragBbox, type TemplateDragMode } from "../../lib/template-canvas";
import type { DocumentType, OcrPage, TemplateDraft, TemplateProfileField, TemplateProfilePage, TemplateStudio } from "../../types/workspace";

type TemplateDragState = {
  fieldId: string;
  mode: TemplateDragMode;
  startBbox: number[];
  startClientX: number;
  startClientY: number;
};

export type TemplateStudioPanelProps = {
  busy: boolean;
  activeAction: string | null;
  templateName: string;
  templateDocumentType: DocumentType;
  templateFiles: File[];
  templateDraft: TemplateDraft | null;
  selectedTemplatePage: TemplateProfilePage | null;
  selectedTemplateField: TemplateProfileField | null;
  selectedTemplatePageFields: TemplateProfileField[];
  templateStudio: { data?: TemplateStudio };
  templateCanvasRef: RefObject<HTMLDivElement | null>;
  templateDrag: TemplateDragState | null;
  setTemplateName: (value: string) => void;
  setTemplateDocumentType: (value: DocumentType) => void;
  setTemplateFiles: (files: File[]) => void;
  setSelectedTemplatePageNumber: (value: number) => void;
  setSelectedTemplateFieldId: (value: string | null) => void;
  uploadTemplateDraft: (event: React.FormEvent<HTMLFormElement>) => void;
  addTemplateField: () => void;
  updateTemplateField: (fieldId: string, patch: Partial<TemplateProfileField>) => void;
  updateTemplateFieldBbox: (fieldId: string, index: number, value: string) => void;
  deleteTemplateField: (fieldId: string) => void;
  saveTemplateDraft: () => void;
  publishTemplateDraft: () => void;
  startTemplateFieldDrag: (event: ReactPointerEvent<HTMLElement>, field: TemplateProfileField, mode: TemplateDragMode) => void;
};

export function TemplateStudioPanel(_props: TemplateStudioPanelProps) {
  return null;
}
```

This first commit creates the boundary. The JSX move happens in the next step.

- [ ] **Step 4: Move JSX from EnterpriseWorkspace**

Move the entire `section === "templates"` panel block from `frontend/src/components/enterprise-workspace.tsx` into `TemplateStudioPanel`.

Keep helper calls available by either moving the helper into `template-studio.tsx` or passing it as a prop. Move these template-only constants into `template-studio.tsx`:

```typescript
const templateDocumentTypes = [
  { value: "unknown", label: "Auto" },
  { value: "citizenship", label: "Citizenship" },
  { value: "national_id", label: "National ID" },
  { value: "asba_application", label: "ASBA" },
  { value: "account_opening", label: "Account Form" },
  { value: "passport", label: "Passport" },
  { value: "driving_license", label: "License" },
] as const;

const templateFieldTypes = ["text", "name", "address", "date", "amount", "number", "phone", "email", "checkbox", "table", "photo", "signature"];
```

In `EnterpriseWorkspace`, render:

```tsx
{section === "templates" ? (
  <TemplateStudioPanel
    busy={busy}
    activeAction={activeAction}
    templateName={templateName}
    templateDocumentType={templateDocumentType}
    templateFiles={templateFiles}
    templateDraft={templateDraft}
    selectedTemplatePage={selectedTemplatePage}
    selectedTemplateField={selectedTemplateField}
    selectedTemplatePageFields={selectedTemplatePageFields}
    templateStudio={templateStudio}
    templateCanvasRef={templateCanvasRef}
    templateDrag={templateDrag}
    setTemplateName={setTemplateName}
    setTemplateDocumentType={setTemplateDocumentType}
    setTemplateFiles={setTemplateFiles}
    setSelectedTemplatePageNumber={setSelectedTemplatePageNumber}
    setSelectedTemplateFieldId={setSelectedTemplateFieldId}
    uploadTemplateDraft={uploadTemplateDraft}
    addTemplateField={addTemplateField}
    updateTemplateField={updateTemplateField}
    updateTemplateFieldBbox={updateTemplateFieldBbox}
    deleteTemplateField={deleteTemplateField}
    saveTemplateDraft={saveTemplateDraft}
    publishTemplateDraft={publishTemplateDraft}
    startTemplateFieldDrag={startTemplateFieldDrag}
  />
) : null}
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
make frontend-build
```

Expected: lint and build pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src/components/templates/template-studio.tsx frontend/src/components/enterprise-workspace.tsx frontend/scripts/template-canvas.test.mjs
git commit -m "refactor: extract template studio component"
```

## Task 7: Phase Verification And Size Check

**Files:**

- Modify: no production files unless verification exposes a defect.

- [ ] **Step 1: Run full suite**

Run:

```bash
make test
```

Expected:

- Backend tests pass.
- Frontend Node tests pass.
- ESLint passes.
- Next production build passes.

- [ ] **Step 2: Check large-file reduction**

Run:

```bash
wc -l backend/app/main.py frontend/src/components/enterprise-workspace.tsx frontend/src/components/templates/template-studio.tsx frontend/src/lib/api-client.ts frontend/src/types/workspace.ts
```

Expected:

- `frontend/src/components/enterprise-workspace.tsx` is smaller than before this phase.
- `backend/app/main.py` is smaller than before this phase.
- New files have single, clear responsibilities.

- [ ] **Step 3: Check route behavior**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_router_behavior.py tests/test_production_foundations.py -q
```

Expected: PASS.

- [ ] **Step 4: Check frontend template page still builds**

Run:

```bash
cd frontend && npm run build
```

Expected: `/templates` appears in the Next route output.

- [ ] **Step 5: Commit verification notes if docs changed**

If a verification note is added to this plan, run:

```bash
git add docs/superpowers/plans/2026-05-29-production-readiness-phase-1-architecture-refactor.md
git commit -m "docs: record phase 1 verification"
```

If no files changed after verification, do not create an empty commit.

## Phase 1 Completion Criteria

- `make test` passes.
- Router modules exist and at least public routes are moved out of `backend/app/main.py`.
- Frontend API client is extracted and tested.
- Workspace types are extracted and tested.
- Template Studio has its own component boundary.
- No product copy introduces raw model/provider names.
- No behavior change is shipped without a test.
