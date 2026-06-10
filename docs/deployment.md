# LipiOCR Deployment Guide

LipiOCR supports three deployment shapes:

1. Local development.
2. On-prem/private-cloud Docker Compose.
3. Kubernetes/Helm skeleton for managed environments.

The first production target is on-prem/private deployment where documents remain inside the institution network.

## Local Development

```bash
make backend-install
make frontend-install
make backend-dev
make frontend-dev
```

Open `http://localhost:3000`.

## Docker Compose On-Prem

Compose stack location:

- `infra/docker-compose.yml`
- `infra/.env.example`
- `deploy/compose/README.md`

Fresh host flow:

```bash
cp infra/.env.example infra/.env
deploy/scripts/validate-env.sh infra/.env
make compose-build
make compose-up
deploy/scripts/health-check.sh http://localhost:8020
```

Default services:

| Service | Default |
| --- | --- |
| Frontend | `http://localhost:3020` |
| API | `http://localhost:8020` |
| Postgres | internal Docker network |
| Redis | internal Docker network |
| MinIO API | `127.0.0.1:9100` |
| MinIO Console | `127.0.0.1:9101` |

Before production:

- Replace all placeholder secrets in `infra/.env`.
- Set exact `LIPIOCR_CORS_ORIGINS`.
- Enable `LIPIOCR_API_AUTH_ENABLED=true`.
- Configure institution-approved OCR provider.
- Mount persistent paths for uploads, template stores, address evidence, name lexicon, and benchmark manifests.
- Keep MinIO and Postgres private.
- Put TLS and access control in front of the stack.

### PaddleOCR + Gemma Reasoning Deployment

For a deployment where PaddleOCR performs page OCR and a Gemma/OpenAI-compatible endpoint performs LipiCore text reasoning, configure:

```bash
LIPIOCR_INSTALL_OCR_EXTRAS=true
LIPIOCR_OCR_PROVIDER=paddle_gemma
LIPIOCR_PADDLE_LANG=en
LIPIOCR_PADDLE_MODEL_MOUNT=/data/lipivision

# Optional, after PaddleOCR trained models are exported to inference format:
LIPIOCR_PADDLE_DET_MODEL_DIR=
LIPIOCR_PADDLE_REC_MODEL_DIR=
LIPIOCR_PADDLE_CLS_MODEL_DIR=
LIPIOCR_PADDLE_REC_CHAR_DICT_PATH=/models/lipivision/paddle_rec/char_dict.txt

LIPIOCR_GEMMA_ENABLED=true
LIPIOCR_GEMMA_API_BASE=http://host.docker.internal:8002/v1
LIPIOCR_GEMMA_MODEL=gemma-4
LIPIOCR_GEMMA_REQUIRE_JSON=true
```

`paddle_gemma` selects the PaddleOCR provider for OCR. Gemma remains enabled separately as LipiCore reasoning over OCR evidence. Do not point `LIPIOCR_OCR_PROVIDER=gemma_vision` at a text-only Gemma model; that mode expects an image-capable chat endpoint.

If a fine-tuned Gemma LoRA is available, serve it behind the OpenAI-compatible endpoint first, then update `LIPIOCR_GEMMA_MODEL` to the served model name after `/v1/models` confirms it is live.

## Persistent Data

Production deployments must treat these as durable application data:

| Data | Typical location | Notes |
| --- | --- | --- |
| Uploaded documents | S3/MinIO bucket or mounted upload volume | Contains customer PII. Encrypt and back up. |
| Template stores | `LIPIOCR_TEMPLATE_STORE`, `LIPIOCR_TEMPLATE_PROFILE_STORE` | Includes approved custom templates and permanent-template revisions. |
| Address evidence | `LIPIOCR_ADDRESS_EVIDENCE_PATH` | Tenant-private road/tole/street evidence. Do not share across tenants unless approved. |
| Name lexicon | `LIPIOCR_NEPALI_NAME_LEXICON` | Generated from approved local data; raw CSV remains outside Git. |
| Benchmark manifest | `LIPIOCR_BENCHMARK_MANIFEST` | Approved accuracy dataset metadata and expected values. |
| Database | `DATABASE_URL` | Cases, audit events, users, jobs, integration receipts. |

## Remote Server Layout

The current remote deployment convention is:

```text
/data/lipiocr
```

When the repository has a configured remote sync target, use:

```bash
make remote-sync
```

Then on the server:

```bash
cd /data/lipiocr/infra
cp .env.example .env
../deploy/scripts/validate-env.sh .env
docker compose --env-file .env up -d --build
../deploy/scripts/health-check.sh http://localhost:8020
```

Do not commit server passwords, private keys, or live `.env` files.

## Subpath Hosting

For a public path such as:

```text
https://ai.silverlining.com.np/lipiocr
```

Frontend build variables:

```bash
NEXT_PUBLIC_BASE_PATH=/lipiocr
NEXT_PUBLIC_API_BASE_URL=auto
```

Backend CORS:

```bash
LIPIOCR_CORS_ORIGINS=https://ai.silverlining.com.np
```

Use `deploy/compose/nginx-lipiocr.conf` as the Nginx reference. The proxy must route:

- `/lipiocr` and Next.js static assets to the frontend.
- `/lipiocr/api/*` or equivalent API path to the backend.
- Websocket/HMR only for development, not production.

## Helm

Chart skeleton:

```text
deploy/helm/lipiocr
```

Render locally:

```bash
helm template lipiocr deploy/helm/lipiocr
```

Before cluster deployment, wire:

- Secret management for API keys, DB password, MinIO/S3 credentials, session secret, preview token secret.
- Persistent volume claims or managed Postgres/S3.
- Ingress TLS.
- Resource requests/limits for API, frontend, and OCR workers.
- Network policies between app, database, object storage, and OCR endpoint.

## Backups

Run from the host:

```bash
deploy/scripts/backup.sh /backup/lipiocr
```

The script captures:

- PostgreSQL dump when Compose service is available.
- Local uploaded object files when mounted locally.

Production teams should also snapshot:

- MinIO/S3 bucket.
- `infra/.env` from a secret vault.
- TLS material from the institution-approved vault.
- Template stores, address evidence store, name lexicon, benchmark manifest, and deployment manifests.

## Restore

Stop the affected stack first when restoring in place:

```bash
make compose-down
deploy/scripts/restore.sh /backup/lipiocr/<backup-id>
make compose-up
deploy/scripts/health-check.sh http://localhost:8020
```

After restore, validate:

- Login/auth.
- Case list.
- Document preview.
- Review/correction flow.
- Export profile.
- Audit/compliance report.
- Template studio pages and approved profiles.
- Address evidence search/resolve.
- Name correction suggestions on a known test sample.

## Upgrade And Rollback

Recommended upgrade flow:

1. Backup database and object storage.
2. Record current Git commit and image tags.
3. Pull or sync new repository bundle.
4. Run environment validation.
5. Build new images.
6. Start services.
7. Run health check and smoke test.
8. Keep previous images and backup until institution sign-off.

Rollback:

1. Stop current stack.
2. Restore previous image tags or previous repository commit.
3. Restore database only when schema/data migration requires it.
4. Start stack.
5. Run health check and smoke test.

## Air-Gapped Bundle

On a connected machine:

```bash
cd infra
docker compose --env-file .env pull
docker compose --env-file .env build
docker save -o lipiocr-offline-images.tar postgres:16 redis:7 minio/minio minio/mc
```

Transfer through the institution-approved media process:

- Image tarball.
- Repository bundle.
- Helm/Compose manifests.
- Checksums.
- Installation runbook.

## Health Checks

API:

```bash
deploy/scripts/health-check.sh http://localhost:8020
```

Manual checks:

```bash
curl http://localhost:8020/health
curl http://localhost:8020/api/platform/status
```

When auth is enabled, authenticated operational checks should use a scoped auditor/admin key.

## On-Prem And SaaS Differences

On-prem single-institution deployments usually set one `LIPIOCR_DEFAULT_TENANT_ID` and keep all services inside the institution network. SaaS/private-cloud deployments must additionally verify tenant isolation across cases, documents, object keys, template profiles, address evidence, jobs, exports, and audit reports.

Do not reuse API keys, session secrets, preview secrets, webhook secrets, or object-storage credentials between tenants or environments.
