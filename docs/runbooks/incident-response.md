# LipiOCR Incident Response Runbook

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

## Communication

Notify institution contacts with scope, timeline, current containment, and next update time. Do not share another tenant's data in a multi-tenant incident.

## Closure

Record root cause, corrective actions, customer impact, recovery time, and evidence retained.
