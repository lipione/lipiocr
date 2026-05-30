# LipiOCR Disaster Recovery Runbook

Use this runbook when recovering an on-prem/private-cloud LipiOCR deployment after host failure, data corruption, accidental deletion, or failed upgrade.

## Recovery Targets

- RPO: last successful database and object backup.
- RTO: institution-specific; default target is same business day for on-prem deployments.

The institution owner must approve final RPO/RTO values before go-live.

## Backup Sources

- PostgreSQL dump from `deploy/scripts/backup.sh`.
- Uploaded documents and template artifacts from the storage volume or S3/MinIO bucket.
- `infra/.env` and TLS material from the institution secret vault.
- Git commit SHA or image tags from the last known-good deployment.
- Reverse proxy and firewall configuration.

## Restore Flow

1. Provision a clean host or namespace.
2. Restore `infra/.env` from the institution vault.
3. Restore repository bundle or container images for the selected version.
4. Run `deploy/scripts/restore.sh <backup-dir>`.
5. Start services.
6. Run `deploy/scripts/health-check.sh`.
7. Validate sample case preview, review, export, and audit reports.
8. Confirm reverse proxy route and TLS certificate.
9. Confirm no cross-tenant data exposure in SaaS/private-cloud mode.

## Validation Checklist

- `/health` responds.
- Operator session or API-key auth works.
- Case list opens.
- Document image preview opens through signed token or authorized request.
- OCR/extraction data is visible.
- Reviewer correction can be saved.
- Export profile can be generated.
- Compliance report can be generated.
- Backup restored timestamp is recorded.

## Evidence

Retain backup ID, restore operator, Git commit or image tag, command logs, health-check output, validation screenshots, and institution sign-off.
