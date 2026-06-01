# LipiOCR Production Security Checklist

Use this checklist before any production or institution pilot go-live.

## Auth And Access

- `LIPIOCR_API_AUTH_ENABLED=true`.
- Operator access uses institution SSO/OIDC/SAML or an approved session adapter.
- API keys are role-scoped and never shared between maker, checker, auditor, and admin users.
- API keys are stored in a vault and rotated on a defined schedule.
- `LIPIOCR_SESSION_SECRET` is unique per deployment.
- `LIPIOCR_PREVIEW_TOKEN_SECRET` is unique per deployment.
- Session TTL matches institution policy.
- Admin access requires institution-approved approval path.
- `super_admin` access is separately approved, logged, and limited to platform operations such as permanent identity template revision.

## Network

- TLS terminates at an institution-approved reverse proxy.
- Backend API is not directly exposed without the reverse proxy/security layer.
- PostgreSQL is private.
- Redis is private.
- MinIO/S3 is private and not publicly listable.
- OCR/LipiCore endpoint is reachable only from approved hosts.
- CORS is restricted to exact production origins.

## Data Protection

- Uploaded documents are stored in private storage.
- Backups are encrypted or stored in an institution-approved protected location.
- Real sample documents are not committed to Git.
- Raw name datasets, customer address books, reviewer-corrected full home addresses, and benchmark images are not committed to Git.
- Logs do not include raw API keys, passwords, or full document payloads.
- Retention policy is configured per tenant or institution.
- Object keys are tenant-scoped for SaaS/private-cloud mode.
- Address evidence promoted to shared reference data contains only approved non-personal road, street, tole, or area aliases.

## Application Controls

- Tenant isolation tests pass before SaaS release.
- Upload size, MIME type, and extension policies are configured.
- External registry, AML, liveness, PAN/VAT, CBS, LOS, and DMS adapters show explicit configured/not-configured states.
- Reviewer corrections preserve original OCR values and audit reasons.
- Name and address correction candidates preserve original values, sources, confidence, and reviewer decision.
- Permanent identity templates cannot be overwritten by tenant admins.
- Webhooks are signed and idempotent.
- SFTP batches produce delivery receipts.

## Operations

- Audit integrity reports are reviewed.
- Access review report is reviewed.
- Backup readiness report is reviewed.
- Disaster recovery restore has been tested.
- Restore includes template stores, address evidence, name lexicon, benchmark manifest, and uploaded documents.
- Incident response contacts and escalation path are documented.
- Production deployment commit/image tags are recorded.
- `make test` or equivalent CI gate passes before release.
