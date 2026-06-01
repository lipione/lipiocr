# LipiOCR API Reference

The API is served by FastAPI. In development, OpenAPI is available at:

```text
http://localhost:8010/docs
```

## Authentication

Auth is controlled by `LIPIOCR_API_AUTH_ENABLED`.

When auth is enabled, use one of:

- Session cookie from `POST /api/auth/session`.
- API key header: `X-LipiOCR-API-Key: <key>`.
- Bearer token where session-token based flows are used.

Common local error:

```json
{"detail":"Missing API key"}
```

Fix it by creating a session, sending `X-LipiOCR-API-Key`, or disabling auth for local workflow development.

## Roles

| Role | Typical permissions |
| --- | --- |
| `maker` | Create cases, upload documents, classify, validate, verify. |
| `checker` | Review cases, approve/reject, export, generate review links. |
| `auditor` | Read audit, compliance, and reporting views. |
| `admin` | Tenant administration, integrations, custom templates, and operational controls. |
| `super_admin` | Platform administration plus permanent Nepal identity template revision. |

## Health And Platform

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check for API availability. |
| `GET` | `/api/platform/status` | Production readiness and platform state. |
| `GET` | `/api/ocr/pipeline` | OCR provider and pipeline posture. |
| `GET` | `/api/dashboard/operations` | Dashboard operational metrics. |

## Auth

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/session` | Create local/operator session cookie. |
| `GET` | `/api/auth/me` | Return current principal. |
| `POST` | `/api/auth/logout` | Revoke current session. |

## Case Workflow

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/cases` | Create individual KYC, business KYB, loan, or document-digitization case. |
| `GET` | `/api/cases` | List cases visible to the current principal. |
| `GET` | `/api/cases/{case_id}` | Fetch case details with documents and review state. |
| `POST` | `/api/cases/{case_id}/documents` | Upload and process applicant-linked document. |
| `POST` | `/api/cases/{case_id}/documents/{document_id}/reanalyze` | Re-run analysis for a linked document. |
| `POST` | `/api/cases/{case_id}/documents/{document_id}/replace` | Replace a linked document file while preserving version history. |
| `GET` | `/api/cases/{case_id}/intelligence` | Get LipiCore intelligence, document signals, and recommendations. |
| `POST` | `/api/cases/{case_id}/split-preview` | Preview packet/page splitting. |
| `POST` | `/api/cases/{case_id}/classify` | Classify case/document packet. |
| `POST` | `/api/cases/{case_id}/validate` | Run validation rules and confidence routing. |
| `PATCH` | `/api/cases/{case_id}/review` | Submit review decision and corrected fields. |
| `GET` | `/api/cases/{case_id}/export` | Export case JSON. |
| `GET` | `/api/cases/{case_id}/export-profile/{profile_key}` | Export case for a configured profile such as CBS/LOS. |

Case document uploads accept images, PDFs, and text fixtures permitted by upload policy. PDF and multipage uploads are expanded where supported by the current processing path. Reanalysis preserves the case/document identity and replaces extracted outputs with a new audit event.

## Standalone Documents

Standalone documents are for packet digitization or documents not attached to an applicant application.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/documents/upload` | Upload and process standalone document. |
| `GET` | `/api/documents` | List standalone documents. |
| `GET` | `/api/documents/{document_id}` | Fetch document details. |
| `POST` | `/api/documents/{document_id}/reanalyze` | Re-run document analysis. |
| `POST` | `/api/documents/{document_id}/replace` | Replace file and preserve version history. |
| `POST` | `/api/documents/{document_id}/archive` | Archive document. |
| `POST` | `/api/documents/{document_id}/link-application` | Link standalone document to an applicant/case. |
| `PATCH` | `/api/documents/{document_id}/review` | Submit review corrections or decision. |
| `GET` | `/api/documents/{document_id}/export` | Export document JSON. |

Use standalone documents for archive digitization, historical KYC cleanup, or a file that is not yet tied to an applicant. Link it later with `/api/documents/{document_id}/link-application` when the applicant or case becomes known.

## Review

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/review/queue` | Maker-checker queue overview. |
| `GET` | `/api/review/workbench/{case_id}` | Review workbench payload for a case. |
| `POST` | `/api/cases/{case_id}/assign` | Assign a reviewer/operator. |
| `POST` | `/api/cases/{case_id}/comments` | Add review comment. |
| `POST` | `/api/cases/{case_id}/rework` | Request rework. |

## Verification

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/verification/adapters` | List registry/AML/liveness/tamper adapters and statuses. |
| `POST` | `/api/verification/adapters/{adapter_key}/configure` | Configure adapter metadata. |
| `POST` | `/api/cases/{case_id}/verification/run` | Run configured verification checks. |
| `POST` | `/api/cases/{case_id}/verification/{adapter_key}/run` | Run one adapter. |

Adapters without credentials must return explicit `not_configured` or sandbox status.

## Nepal Reference Data

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/reference/nepal-locations?q={query}&limit={n}` | Search the Nepal administrative registry: province, district, local level, and local level type. |
| `POST` | `/api/reference/nepal-locations/resolve` | Resolve free-text Nepali/English address text into province, district, municipality/gaunpalika, ward, confidence, and warnings. |
| `GET` | `/api/reference/address-evidence?q={query}` | Search approved address evidence records for area, tole, road, and street aliases. |
| `POST` | `/api/reference/address-evidence/resolve` | Resolve free-text OCR address text into scored, auditable address candidates. |
| `POST` | `/api/reference/address-evidence` | Create a tenant-scoped address evidence record. |
| `POST` | `/api/reference/address-evidence/import` | Import address evidence records from a `records` list. |
| `PATCH` | `/api/reference/address-evidence/{id}` | Update address evidence metadata or aliases. |
| `DELETE` | `/api/reference/address-evidence/{id}` | Disable an incorrect address evidence record. |

The location resolver is used by document intelligence to fill canonical address fields and flag district/local-level mismatches before export.

Address evidence records are tenant-private by default. The API accepts approved road, street, tole, and area aliases. Full customer home addresses should not be imported as shared evidence.

Minimal address evidence payload:

```json
{
  "district_name": "Kathmandu",
  "local_level_name": "Kathmandu Metropolitan City",
  "ward": "26",
  "kind": "area_or_tole",
  "name_en": "Samakhusi",
  "aliases_en": ["Samakushi", "Samakhusi Tole"],
  "visibility": "tenant_private"
}
```

Nepali name correction candidates are returned inside document intelligence and review-field payloads when the name lexicon or bilingual field pair supports a suggestion. There is no separate public mutation API for the name lexicon; build and mount it through deployment configuration.

## Templates

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/templates` | List runtime extraction templates. |
| `GET` | `/api/admin/templates/studio` | Fetch template studio state. |
| `POST` | `/api/admin/templates/studio` | Create/update studio payload. |
| `POST` | `/api/admin/templates/drafts` | Create template draft. |
| `PATCH` | `/api/admin/templates/drafts/{draft_id}` | Update draft fields, boxes, labels, rules. |
| `POST` | `/api/admin/templates/drafts/{draft_id}/publish` | Publish draft to profile. |
| `GET` | `/api/admin/templates/profiles` | List tenant-scoped template profiles. |
| `POST` | `/api/admin/templates/profiles/{profile_id}/approve` | Approve a profile. |
| `POST` | `/api/admin/templates/profiles/{profile_id}/rollback` | Roll back to an earlier version. |
| `GET` | `/api/admin/templates/profiles/{profile_id}/export` | Export profile JSON. |
| `POST` | `/api/admin/templates/profiles/import` | Import profile JSON. |
| `POST` | `/api/admin/templates/profiles/{profile_id}/test` | Test profile against field data. |

`POST /api/admin/templates/drafts` accepts multipart template images/PDFs and creates a draft with pages, OCR blocks, suggested fields, and quality checks. Tenant admins can manage custom institution templates. Permanent identity templates for citizenship, National ID, passport, and driving license require `super_admin` permission to overwrite.

## Integrations

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/integrations/profiles` | List integration modes and export profile metadata. |
| `GET` | `/api/integrations/operations` | List configured webhooks, SFTP batches, retry queue, delivery receipts. |
| `POST` | `/api/integrations/webhook/test` | Build signed webhook test payload. |
| `POST` | `/api/integrations/webhooks/configure` | Register webhook config metadata. |
| `POST` | `/api/integrations/webhooks/deliver` | Create idempotent webhook delivery receipt. |
| `POST` | `/api/integrations/sftp/batch` | Queue SFTP batch delivery receipt. |
| `POST` | `/api/integrations/retry/{event_id}` | Retry failed integration event. |
| `POST` | `/api/cases/{case_id}/embedded-review-link` | Create signed embedded review link. |

Webhook deliveries include:

- `X-LipiOCR-Event`
- `X-LipiOCR-Idempotency-Key`
- `X-LipiOCR-Signature`

## Analytics And Compliance

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/analytics/accuracy` | Accuracy, correction, confidence, and benchmark analytics. |
| `GET` | `/api/analytics/benchmark` | Export the active OCR benchmark report with document, language, handwriting, field, and confidence breakdowns. |
| `POST` | `/api/analytics/benchmark/samples` | Upsert an approved benchmark sample into the active benchmark manifest. |
| `POST` | `/api/analytics/corrections` | Record reviewer correction event. |
| `GET` | `/api/compliance/reports` | Access review, audit integrity, retention, backup, and export reports. |

## Administration

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/tenant` | Legacy tenant policy/control profile. |
| `GET` | `/api/admin/rbac` | Role and permission posture. |
| `GET` | `/api/admin/audit-integrity` | Audit hash-chain summary. |
| `GET` | `/api/admin/tenants` | List tenants in tenant registry. |
| `POST` | `/api/admin/tenants` | Create or update tenant. |
| `PATCH` | `/api/admin/tenants/{tenant_id}/settings` | Update tenant settings. |
| `POST` | `/api/admin/tenants/{tenant_id}/users` | Add/update tenant user. |

## Jobs

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/jobs` | List document jobs. |
| `GET` | `/api/jobs/{job_id}` | Get job status. |
| `POST` | `/api/jobs/{job_id}/retry` | Retry failed job. |
| `POST` | `/api/jobs/run-next` | Run the next queued job in current process. |

## Upload Preview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/uploads/{stored_name}` | Fetch stored upload preview with signed token or read permission. |

Signed image previews use `LIPIOCR_PREVIEW_TOKEN_SECRET` and `LIPIOCR_PREVIEW_TOKEN_TTL_SECONDS`.
