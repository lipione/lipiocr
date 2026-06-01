# LipiOCR Configuration Reference

Configuration is environment-variable driven. Do not commit real `.env` files.

## Files

| File | Purpose |
| --- | --- |
| `backend/.env.example` | Local backend defaults and knobs. |
| `frontend/.env.example` | Local frontend API/base-path values. |
| `infra/.env.example` | Docker Compose production-shaped defaults. |
| `deploy/helm/lipiocr/values.yaml` | Helm chart defaults. |

## Backend Variables

| Variable | Local default | Production guidance |
| --- | --- | --- |
| `LIPIOCR_ENVIRONMENT` | `development` | Use `production` for deployed environments. |
| `LIPIOCR_CORS_ORIGINS` | `http://localhost:3000` | Set exact frontend origins, comma-separated. |
| `LIPIOCR_UPLOAD_DIR` | `storage/uploads` | Use mounted volume or object storage. |
| `LIPIOCR_REPOSITORY_BACKEND` | `auto` | Use `sql` with `DATABASE_URL`. |
| `DATABASE_URL` | empty | PostgreSQL connection string. |
| `LIPIOCR_ASYNC_JOBS_ENABLED` | `false` | Enable when worker orchestration is active. |
| `LIPIOCR_STORAGE_BACKEND` | `auto` | Use `s3` with MinIO/S3. |
| `S3_ENDPOINT_URL` | empty | MinIO/S3 endpoint. |
| `S3_BUCKET` | `lipiocr-documents` | Tenant-safe private bucket. |
| `AWS_ACCESS_KEY_ID` | empty | Store in vault or orchestrator secret. |
| `AWS_SECRET_ACCESS_KEY` | empty | Store in vault or orchestrator secret. |
| `AWS_REGION` | `us-east-1` | Set to institution/cloud region. |
| `LIPIOCR_OCR_PROVIDER` | `mock` | Use `gemma_vision`, `paddleocr`, or `tesseract` when configured. |
| `LIPIOCR_GEMMA_ENABLED` | `false` | Enable only when endpoint is reachable. |
| `LIPIOCR_GEMMA_API_BASE` | `http://127.0.0.1:8003/v1` | OpenAI-compatible vLLM endpoint. |
| `LIPIOCR_GEMMA_MODEL` | `gemma-4-26b-4bit` | Institution-approved deployed model name. |
| `LIPIOCR_GEMMA_TIMEOUT_SECONDS` | `45` | Increase for full-page vision extraction. |
| `LIPIOCR_GEMMA_MAX_TOKENS` | `1200` | Increase for large forms and packets. |
| `LIPIOCR_GEMMA_RETRIES` | `2` | Keep bounded to avoid blocking queues. |
| `LIPIOCR_GEMMA_REQUIRE_JSON` | `true` | Keep true for structured extraction. |
| `LIPIOCR_API_AUTH_ENABLED` | `false` | Must be `true` in production. |
| `LIPIOCR_API_KEYS` | empty | Format `key:role,key2:role2`; use vault-managed keys. |
| `LIPIOCR_SESSION_SECRET` | derived fallback | Must be unique random secret in production. |
| `LIPIOCR_SESSION_TTL_SECONDS` | `43200` | Tune to institution policy. |
| `LIPIOCR_SESSION_COOKIE_NAME` | `lipiocr_session` | Change only if cookie collision exists. |
| `LIPIOCR_DEFAULT_TENANT_ID` | `demo-institution` | Set to tenant slug for on-prem single institution. |
| `LIPIOCR_MAX_UPLOAD_BYTES` | `26214400` | Set by institution document-size policy. |
| `LIPIOCR_ALLOWED_UPLOAD_MIME_TYPES` | common images, PDF, text | Restrict to required document types in production. |
| `LIPIOCR_ALLOWED_UPLOAD_EXTENSIONS` | common images, PDF, text | Restrict alongside MIME types. |
| `LIPIOCR_PREVIEW_TOKEN_SECRET` | derived fallback | Must be unique random secret in production. |
| `LIPIOCR_PREVIEW_TOKEN_TTL_SECONDS` | `900` | Short TTL is safer. |
| `LIPIOCR_NEPALI_NAME_LEXICON` | `storage/name-lexicon/nepali_name_lexicon.json` | Optional compact Nepali name lexicon generated from an approved local CSV. Used for reviewer-safe name correction suggestions. |
| `LIPIOCR_ADDRESS_EVIDENCE_PATH` | `storage/address-evidence/address_evidence.json` | Local JSON store for tenant-approved address evidence. Use a mounted path for on-prem deployments. |
| `LIPIOCR_TEMPLATE_STORE` | empty | Optional JSON store for runtime templates. |
| `LIPIOCR_TEMPLATE_PROFILE_STORE` | empty | Optional JSON store for template profiles. |
| `LIPIOCR_LOAD_TEMPLATE_STORE` | empty | Set `true` to load template stores on startup. |
| `LIPIOCR_WEBHOOK_SECRET` | demo fallback | Must be tenant/integration-specific in production. |
| `LIPIOCR_PUBLIC_APP_BASE_URL` | `http://localhost:3000` | Public base URL used for review links. |
| `LIPIOCR_BENCHMARK_MANIFEST` | empty | Optional JSON manifest path for approved OCR benchmark samples. Defaults to the local benchmark store or test fixture. |

## Frontend Variables

| Variable | Local default | Production guidance |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8010` | External API URL, or `auto` for same-host reverse proxy. |
| `NEXT_PUBLIC_API_PORT` | `13001` in code fallback | Set when `auto` needs explicit API port resolution. |
| `NEXT_PUBLIC_BASE_PATH` | empty | Use `/lipiocr` for subpath deployments. |

For `https://ai.silverlining.com.np/lipiocr`, set:

```bash
NEXT_PUBLIC_BASE_PATH=/lipiocr
NEXT_PUBLIC_API_BASE_URL=auto
```

The reverse proxy must route API calls to the backend and frontend assets under the same base path.

## Secret Generation

Use unique values per environment:

```bash
openssl rand -hex 32
```

Generate at least:

- Maker/checker/admin API keys.
- `LIPIOCR_SESSION_SECRET`.
- `LIPIOCR_PREVIEW_TOKEN_SECRET`.
- `POSTGRES_PASSWORD`.
- `MINIO_ROOT_PASSWORD`.
- Webhook secrets per receiving system.

## Auth Key Format

```bash
LIPIOCR_API_KEYS=<maker-key>:maker,<checker-key>:checker,<auditor-key>:auditor,<admin-key>:admin,<super-admin-key>:super_admin
```

Never share production admin or super-admin keys in chat, screenshots, tickets, or committed docs.

## Local Profiles

Fast UI/backend development:

```bash
LIPIOCR_REPOSITORY_BACKEND=memory
LIPIOCR_STORAGE_BACKEND=local
LIPIOCR_OCR_PROVIDER=mock
LIPIOCR_GEMMA_ENABLED=false
LIPIOCR_API_AUTH_ENABLED=false
```

Production-shaped local compose:

```bash
LIPIOCR_REPOSITORY_BACKEND=sql
LIPIOCR_STORAGE_BACKEND=s3
LIPIOCR_OCR_PROVIDER=gemma_vision
LIPIOCR_API_AUTH_ENABLED=true
```

## Upload Policy

Default accepted extensions:

```text
.avif,.bmp,.gif,.jpeg,.jpg,.pdf,.png,.tif,.tiff,.txt,.webp
```

Default accepted MIME types:

```text
application/pdf,image/avif,image/bmp,image/gif,image/jpeg,image/png,image/tiff,image/webp,text/plain
```

Production institutions should remove any type they do not explicitly accept.
