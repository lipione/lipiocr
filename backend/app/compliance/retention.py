from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from app.models import DocumentRecord, KycCase
from app.tenancy.service import tenant_registry


def retention_report(cases: Iterable[KycCase], documents: Iterable[DocumentRecord]) -> dict[str, object]:
    tenant_retention = {tenant.tenant_id: tenant.settings.retention_days for tenant in tenant_registry.list_tenants()}
    expired_cases = []
    now = datetime.utcnow()
    for case in cases:
        retention_days = tenant_retention.get(case.institution_id, 2555)
        if case.created_at < now - timedelta(days=retention_days):
            expired_cases.append({"case_id": case.id, "tenant_id": case.institution_id, "age_days": (now - case.created_at).days})

    expired_documents = []
    for document in documents:
        if document.created_at < now - timedelta(days=2555):
            expired_documents.append({"document_id": document.id, "age_days": (now - document.created_at).days})

    return {
        "report": "retention",
        "expired_cases": expired_cases,
        "expired_documents": expired_documents,
        "policy_by_tenant": tenant_retention,
        "status": "action_required" if expired_cases or expired_documents else "within_policy",
    }
