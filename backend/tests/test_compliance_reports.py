from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.compliance.dr import backup_readiness_report
from app.compliance.reports import access_review_report, audit_integrity_report
from app.compliance.retention import retention_report
from app.main import app
from app.models import AuditEvent, CaseType, DocumentRecord, DocumentStatus, DocumentType, KycCase
from app.tenancy.models import Tenant, TenantSettings, TenantUser
from app.tenancy.service import tenant_registry


client = TestClient(app)


def test_access_review_report_lists_tenant_users():
    tenant_registry.upsert_tenant(
        Tenant(
            tenant_id="compliance-tenant",
            name="Compliance Tenant",
            users=[TenantUser(user_id="checker.one", role="checker")],
        )
    )

    report = access_review_report()

    assert report["report"] == "access_review"
    assert any(user["user_id"] == "checker.one" for user in report["users"])


def test_audit_integrity_and_retention_reports_are_actionable():
    case = KycCase(
        case_type=CaseType.individual_kyc,
        applicant_name="Old Case",
        institution_id="retention-tenant",
        created_at=datetime.utcnow() - timedelta(days=20),
        audit_events=[AuditEvent(action="case_created")],
    )
    tenant_registry.upsert_tenant(
        Tenant(
            tenant_id="retention-tenant",
            name="Retention Tenant",
            settings=TenantSettings(retention_days=7),
        )
    )
    document = DocumentRecord(
        filename="old.txt",
        document_type=DocumentType.unknown,
        status=DocumentStatus.review_required,
        overall_confidence=0.5,
        fields=[],
    )

    audit = audit_integrity_report([case])
    retention = retention_report([case], [document])

    assert audit["event_count"] == 1
    assert retention["status"] == "action_required"
    assert retention["expired_cases"][0]["case_id"] == case.id


def test_backup_readiness_and_compliance_api():
    readiness = backup_readiness_report(Path(".."))
    response = client.get("/api/compliance/reports")

    assert readiness["status"] == "ready"
    assert response.status_code == 200
    assert "access_review" in response.json()
    assert "backup" in response.json()
