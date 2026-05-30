# Production Readiness Phase 3 Async OCR Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move document OCR/LipiCore/template processing behind a job model so production uploads can return quickly, show queued/processing/completed/failed states, and retry failed work.

**Architecture:** Add a small durable job domain first, backed by an in-memory queue for tests and local demo with a clean interface that can later be backed by Redis/Postgres. Keep current synchronous upload behavior as the default until the UI switches over; when `LIPIOCR_ASYNC_JOBS_ENABLED=true`, upload/reanalyze/replace endpoints return a job envelope and the worker applies the same repository mutations that the synchronous route applies today.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy job table from Phase 2, pytest, Next.js/React operator UI, optional background worker process.

---

## File Structure

- Create `backend/app/jobs/models.py`: job enums, `ProcessingJob`, `JobTarget`, and serializable job result/error models.
- Create `backend/app/jobs/queue.py`: queue interface and `InMemoryJobQueue` implementation with enqueue/status/retry/list operations.
- Create `backend/app/jobs/worker.py`: job runner that marks queued jobs processing, executes handlers, records completion/failure, and supports retry.
- Create `backend/app/jobs/document_jobs.py`: document job payload builders and handlers for standalone uploads, case uploads, reanalysis, replacement, and template tests.
- Modify `backend/app/core/config.py`: add `async_jobs_enabled`.
- Modify `backend/app/main.py`: expose job endpoints and async-mode upload behavior while preserving sync default.
- Modify `frontend/src/types/workspace.ts`: add job state types.
- Modify `frontend/src/lib/api-client.ts`: add `getJob`, `retryJob`, `listJobs`.
- Modify `frontend/src/components/enterprise-workspace.tsx`: show job status panels and retry actions for async uploads.
- Test `backend/tests/test_document_jobs.py`: queue/worker document job behavior.
- Test `backend/tests/test_upload_job_api.py`: async upload returns job ID and retry/status endpoints work.
- Test `frontend/scripts/workspace-types.test.mjs`: route/type coverage for job statuses.

## Task 1: Job Domain And Queue

**Files:**

- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/models.py`
- Create: `backend/app/jobs/queue.py`
- Create: `backend/tests/test_document_jobs.py`

- [ ] **Step 1: Write failing queue tests**

Create `backend/tests/test_document_jobs.py` with tests that assert:

- `InMemoryJobQueue.enqueue()` returns a `ProcessingJob` with status `queued`.
- `claim_next()` moves the job to `processing`.
- `complete()` stores `result` and moves to `completed`.
- `fail()` stores an operator-safe error and moves to `failed`.
- `retry()` moves a failed job back to `queued`, increments attempts, and clears error.
- `list_jobs()` can filter by status.

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_document_jobs.py -q
```

Expected: FAIL with missing `app.jobs`.

- [ ] **Step 2: Implement job models and queue**

Implement:

```python
class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    retry_scheduled = "retry_scheduled"

class JobType(str, Enum):
    document_upload = "document_upload"
    document_reanalyze = "document_reanalyze"
    document_replace = "document_replace"
    case_document_upload = "case_document_upload"
    case_document_reanalyze = "case_document_reanalyze"
    case_document_replace = "case_document_replace"
    template_test = "template_test"
    export_delivery = "export_delivery"
```

`ProcessingJob` must include `id`, `job_type`, `status`, `target_type`, `target_id`, `payload`, `attempts`, `max_attempts`, `error`, `result`, `created_at`, `updated_at`, and optional `started_at/completed_at`.

- [ ] **Step 3: Verify and commit**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_document_jobs.py -q
```

Commit:

```bash
git add backend/app/jobs backend/tests/test_document_jobs.py
git commit -m "feat: add document job queue"
```

## Task 2: Worker Runner And Retry Semantics

**Files:**

- Create: `backend/app/jobs/worker.py`
- Modify: `backend/tests/test_document_jobs.py`

- [ ] **Step 1: Add failing worker tests**

Add tests proving:

- `run_next_job(queue, handlers)` completes a queued job when the handler returns a result.
- handler exceptions move the job to `failed` with no raw traceback in public error.
- `retry_failed_job()` returns a failed job to `queued`.
- unknown job types fail with a clear `unsupported_job_type` error.

- [ ] **Step 2: Implement worker**

`run_next_job` should claim one queued job, call a handler by `job.job_type`, and write result/error back through the queue. It must not swallow exceptions silently.

- [ ] **Step 3: Verify and commit**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_document_jobs.py -q
```

Commit:

```bash
git add backend/app/jobs/worker.py backend/tests/test_document_jobs.py
git commit -m "feat: add job worker runner"
```

## Task 3: Document Job Handlers

**Files:**

- Create: `backend/app/jobs/document_jobs.py`
- Modify: `backend/tests/test_document_jobs.py`

- [ ] **Step 1: Add failing document handler tests**

Add tests that use a fake OCR processor/repository and prove:

- standalone upload job stores a `DocumentRecord`.
- case upload job stores a processed document on the case.
- failed processing leaves the job failed and does not partially approve a document.

- [ ] **Step 2: Implement handlers**

Handlers must accept injected dependencies so tests do not require external OCR/Gemma:

```python
def build_document_job_handlers(*, repository, object_storage, processor, upload_dir, ocr_provider_factory, gemma_client_factory) -> dict[str, Callable]:
    ...
```

The handler result should include `document_id` or `case_id`, `document_type`, `status`, `summary`, and `review_url`.

- [ ] **Step 3: Verify and commit**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_document_jobs.py -q
```

Commit:

```bash
git add backend/app/jobs/document_jobs.py backend/tests/test_document_jobs.py
git commit -m "feat: add document job handlers"
```

## Task 4: Job API And Async Upload Mode

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_upload_job_api.py`

- [ ] **Step 1: Add failing API tests**

Create tests proving:

- With `Settings(async_jobs_enabled=True)`, standalone upload returns HTTP `202` with `job_id`, `status=queued`, and a `status_url`.
- `GET /api/jobs/{job_id}` returns queued/processing/completed/failed data.
- `POST /api/jobs/{job_id}/retry` moves failed jobs to queued.
- With async disabled, existing upload behavior remains unchanged.

- [ ] **Step 2: Implement API surface**

Add endpoints:

- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/jobs/run-next` for local/on-prem worker testing behind admin permission.

Add async-mode branches to upload/reanalyze/replace endpoints. Do not remove synchronous behavior yet.

- [ ] **Step 3: Verify and commit**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_upload_job_api.py tests/test_documents_api.py tests/test_enterprise_cases_api.py -q
```

Commit:

```bash
git add backend/app/core/config.py backend/app/main.py backend/tests/test_upload_job_api.py
git commit -m "feat: add async document job api"
```

## Task 5: Frontend Job States

**Files:**

- Modify: `frontend/src/types/workspace.ts`
- Modify: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/components/enterprise-workspace.tsx`
- Modify: `frontend/scripts/workspace-types.test.mjs`

- [ ] **Step 1: Add frontend type/client tests**

Extend the workspace type test to assert job statuses include `queued`, `processing`, `completed`, `failed`, and `retry_scheduled`.

- [ ] **Step 2: Implement UI states**

Show a concise processing panel in Documents and Templates:

- queued: "Waiting"
- processing: "Processing"
- completed: link to document/template result
- failed: retry button with operator-safe error

Avoid technical model/provider names; use `LipiCore` in UI copy.

- [ ] **Step 3: Verify and commit**

Run:

```bash
cd frontend && npm run test && npm run lint && npm run build
```

Commit:

```bash
git add frontend/src/types/workspace.ts frontend/src/lib/api-client.ts frontend/src/components/enterprise-workspace.tsx frontend/scripts/workspace-types.test.mjs
git commit -m "feat: show document job states"
```

## Task 6: Phase 3 Verification

**Files:**

- Modify: this plan only if recording verification notes.

- [ ] **Step 1: Run focused tests**

```bash
cd backend && .venv/bin/python -m pytest tests/test_document_jobs.py tests/test_upload_job_api.py -q
```

- [ ] **Step 2: Run full test/build**

```bash
make test
```

- [ ] **Step 3: Record verification**

Append a verification log to this plan and commit it if all checks pass.

## Phase 3 Completion Criteria

- Async-enabled upload returns a job ID.
- Job status can be read, listed, and retried.
- Worker can complete or fail document processing without blocking request handlers.
- Failed OCR/LipiCore jobs can be retried.
- Existing synchronous demo behavior remains available while the UI migrates.
