# LipiOCR Incident Response Runbook

Use this runbook for production or pilot incidents affecting confidentiality, integrity, availability, review workflow, OCR/ICR processing, integrations, or tenant separation.

## Severity

- SEV-1: data exposure, authentication bypass, unavailable production service.
- SEV-2: OCR processing outage, integration delivery failure, degraded review workflow.
- SEV-3: isolated tenant issue or non-critical dashboard defect.

## First 30 Minutes

1. Assign incident commander and scribe.
2. Freeze deployment changes unless required for containment.
3. Identify affected tenants, branches, cases, documents, and integrations.
4. Preserve audit logs, API logs, worker logs, and reverse proxy logs.
5. Disable affected integration keys or operator accounts if access is suspected.
6. Stop automatic retries for failing integrations if they may duplicate downstream records.
7. Record the current Git commit, image tags, and environment version.

## Containment Options

- Disable compromised API key.
- Revoke operator sessions.
- Pause webhook/SFTP delivery.
- Disable a verification adapter.
- Put reverse proxy route behind institution VPN or maintenance page.
- Roll back to the last known-good image.
- Restore from backup only when data integrity requires it.

## Communication

Notify institution contacts with scope, timeline, current containment, and next update time. Do not share another tenant's data in a multi-tenant incident.

Minimum update fields:

- Incident severity.
- Start time and detection time.
- Affected tenants/branches/workflows.
- Current customer impact.
- Containment action taken.
- Next update time.

## Closure

Record root cause, corrective actions, customer impact, recovery time, evidence retained, and follow-up owner.

Required closure checks:

- Audit/compliance report reviewed.
- Affected API keys or sessions rotated.
- Failed integration deliveries reconciled.
- Any exported downstream data reconciled with the institution.
- Regression test or runbook update created for the failure mode.
