# LipiOCR On-Prem Compose Pack

This pack is for institution-owned deployments where data stays inside the bank, cooperative, insurer, lender, or financial institution network.

Read this together with [Deployment](../../docs/deployment.md) and [Configuration](../../docs/configuration.md).

## Fresh VM Flow

1. Install Docker Engine and Docker Compose.
2. Copy the repository to `/data/lipiocr` or another institution-approved application directory.
3. Create `infra/.env` from `infra/.env.example`.
4. Replace all placeholder secrets in `infra/.env`.
5. Run `deploy/scripts/validate-env.sh infra/.env`.
6. Mount or provision durable paths for uploads, template stores, address evidence, name lexicon, and benchmark manifests.
7. Start services with `cd infra && docker compose --env-file .env up -d --build`.
8. Run `deploy/scripts/health-check.sh http://localhost:8020`.

## Services

| Service | Purpose | Default exposure |
| --- | --- | --- |
| `api` | FastAPI backend | `LIPIOCR_API_PORT`, default `8020` |
| `frontend` | Next.js workspace | `LIPIOCR_FRONTEND_PORT`, default `3020` |
| `postgres` | Production-shaped repository | internal Docker network |
| `redis` | Queue/cache dependency | internal Docker network |
| `minio` | S3-compatible object storage | bound to `127.0.0.1` by default |
| `minio-init` | Bucket bootstrap | one-shot helper |

## Required Secrets

Generate unique values before production:

```bash
openssl rand -hex 32
```

Replace:

- `LIPIOCR_API_KEYS`
- `LIPIOCR_SESSION_SECRET`
- `LIPIOCR_PREVIEW_TOKEN_SECRET`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- webhook secrets used by receiving systems

Do not expose MinIO or Postgres publicly.

## Durable Data

Keep these outside ephemeral containers:

- Uploaded documents in MinIO/S3 or a mounted upload volume.
- Template stores from `LIPIOCR_TEMPLATE_STORE` and `LIPIOCR_TEMPLATE_PROFILE_STORE`.
- Address evidence from `LIPIOCR_ADDRESS_EVIDENCE_PATH`.
- Nepali name lexicon from `LIPIOCR_NEPALI_NAME_LEXICON`.
- Accuracy benchmark manifest from `LIPIOCR_BENCHMARK_MANIFEST`.

Raw KYC samples, raw name datasets, and customer address data must not be copied into the repository bundle.

## Backups

Use `deploy/scripts/backup.sh /backup/lipiocr` from the host. It exports Postgres and captures uploaded object files when local volumes are mounted.

Also retain:

- `infra/.env` from a secret vault.
- TLS material from the institution vault.
- Object-storage snapshots if MinIO/S3 is externalized.
- Template stores, address evidence, name lexicon, and benchmark manifests.
- Git commit or image tags deployed.

## Restore

Use `deploy/scripts/restore.sh /backup/lipiocr/<backup-id>` on a stopped stack, then start services and run the health check.

Smoke test after restore:

1. Login or authenticated API request.
2. Case list.
3. Document preview.
4. Review correction.
5. Export profile.
6. Compliance report.

## Reverse Proxy

For subpath hosting such as `/lipiocr`, use `deploy/compose/nginx-lipiocr.conf` as a reference.

Required frontend build/runtime values:

```bash
NEXT_PUBLIC_BASE_PATH=/lipiocr
NEXT_PUBLIC_API_BASE_URL=auto
```

Backend CORS must include the public origin:

```bash
LIPIOCR_CORS_ORIGINS=https://ai.silverlining.com.np
```

## Offline Bundle

For air-gapped institutions, pre-pull images on a connected machine and export them:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env pull
docker save -o lipiocr-offline-images.tar postgres:16 redis:7 minio/minio minio/mc
```

Transfer the tarball and repository bundle through the institution-approved media-control process.

Include checksums and a copy of the exact `infra/.env` key names without secret values.
