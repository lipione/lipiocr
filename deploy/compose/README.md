# LipiOCR On-Prem Compose Pack

This pack is for institution-owned deployments where data stays inside the bank, cooperative, insurer, lender, or financial institution network.

## Fresh VM Flow

1. Install Docker Engine and Docker Compose.
2. Copy the repository to `/opt/lipiocr`.
3. Create `infra/.env` from `infra/.env.example`.
4. Run `deploy/scripts/validate-env.sh infra/.env`.
5. Start services with `cd infra && docker compose --env-file .env up -d --build`.
6. Run `deploy/scripts/health-check.sh http://localhost:8020`.

## Backups

Use `deploy/scripts/backup.sh /backup/lipiocr` from the host. It exports Postgres and captures uploaded object files when local volumes are mounted.

## Restore

Use `deploy/scripts/restore.sh /backup/lipiocr/<backup-id>` on a stopped stack, then start services and run the health check.

## Offline Bundle

For air-gapped institutions, pre-pull images on a connected machine and export them:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env pull
docker save -o lipiocr-offline-images.tar postgres:16 redis:7 minio/minio minio/mc
```

Transfer the tarball and repository bundle through the institution-approved media-control process.
