# LipiOCR Production Security Checklist

- API auth is enabled.
- Operator access uses institution SSO/OIDC/SAML or approved session adapter.
- Integration API keys are stored in a vault and rotated.
- `LIPIOCR_PREVIEW_TOKEN_SECRET` is unique per deployment.
- TLS terminates at an institution-approved reverse proxy.
- MinIO/S3 is private and not exposed publicly.
- PostgreSQL is private and backed up.
- Tenant isolation tests pass before SaaS release.
- Audit integrity reports are reviewed.
- Retention policy is configured per tenant.
- Disaster recovery restore has been tested.
