from __future__ import annotations

from fastapi import APIRouter, Request

from app.app_context import repository, settings
from app.compliance.dr import backup_readiness_report
from app.compliance.reports import access_review_report, audit_integrity_report, export_delivery_report
from app.compliance.retention import retention_report
from app.services.security import require_permission


router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/reports")
def compliance_reports(http_request: Request):
    require_permission(settings, http_request, "view_audit")
    cases = repository.list_cases()
    documents = repository.list()
    return {
        "access_review": access_review_report(),
        "audit_integrity": audit_integrity_report(cases),
        "retention": retention_report(cases, documents),
        "backup": backup_readiness_report("."),
        "exports": export_delivery_report(),
    }
