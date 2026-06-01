# Template Creation Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-class Template Creation Studio where operators upload one or more template pages, LipiCore proposes fields, users manually adjust labels/metadata, and saved profiles become reusable extraction templates.

**Architecture:** Add a focused backend template-profile service with draft upload, draft update, and publish APIs. Reuse existing OCR/page processing and template persistence, while preserving richer profile metadata for multi-page template editing. Add a dedicated `/templates` UI with upload intake, page thumbnails, document canvas overlays, a field inspector, add/delete field actions, and publish.

**Tech Stack:** FastAPI, Pydantic, existing LipiCore OCR pipeline, JSON-backed persistence, Next.js React, Tailwind-style utility classes, lucide-react.

---

### Task 1: Backend Template Draft/Profile API

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/template_profiles.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_template_studio_api.py`

- [ ] Add models for `TemplateProfilePage`, `TemplateProfileField`, `TemplateDraft`, `TemplateProfile`, and `TemplateDraftUpdate`.
- [ ] Add a service that stores drafts/profiles in memory and persists profiles/drafts to `_template_profiles.json` when template store is enabled.
- [ ] Add `POST /api/admin/templates/drafts`, `PATCH /api/admin/templates/drafts/{draft_id}`, and `POST /api/admin/templates/drafts/{draft_id}/publish`.
- [ ] Test multi-page upload creates draft pages and field proposals.
- [ ] Test draft update + publish saves a rich profile and updates the existing template studio list.

### Task 2: Template Studio UI

**Files:**
- Modify: `frontend/src/components/enterprise-workspace.tsx`

- [ ] Add frontend types for template drafts/profiles.
- [ ] Add template upload state: files, name, selected page, selected field, draft.
- [ ] Build dedicated template UI when `section === "templates"`:
  - upload panel
  - page thumbnails
  - central canvas with image and overlay boxes
  - field list
  - inspector with label/key/type/required/bbox editing
  - add/delete field
  - publish button
- [ ] Keep controls visible and avoid dropdowns where possible.
- [ ] Reuse existing `sourceImageUrl`, `bboxStyle`, `ActionButton`, `Info`, `StatusBadge` helpers.

### Task 3: Verification and Deploy

**Files:**
- No new files.

- [ ] Run targeted backend tests.
- [ ] Run `make test`.
- [ ] Rebuild/deploy remote compose services.
- [ ] Verify live upload/draft/publish APIs and `/templates` UI controls.
