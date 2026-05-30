# LipiOCR Disaster Recovery Runbook

## Recovery Targets

- RPO: last successful database and object backup.
- RTO: institution-specific; default target is same business day for on-prem deployments.

## Backup Sources

- PostgreSQL dump from `deploy/scripts/backup.sh`.
- Uploaded documents and template artifacts from the storage volume or S3/MinIO bucket.
- `infra/.env` and TLS material from the institution secret vault.

## Restore Flow

1. Provision a clean host or namespace.
2. Restore `infra/.env` from the institution vault.
3. Run `deploy/scripts/restore.sh <backup-dir>`.
4. Start services.
5. Run `deploy/scripts/health-check.sh`.
6. Validate sample case preview, review, export, and audit reports.

## Evidence

Retain backup ID, restore operator, command logs, health-check output, and sample validation screenshots.
