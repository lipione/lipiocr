from fastapi.testclient import TestClient

from app.app_context import settings
from app.main import app
from app.models import DocumentType, TemplateField
import app.services.templates as template_registry


client = TestClient(app)


def _case_with_document() -> dict:
    create = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Completion Customer",
            "customer_ref": "COMP-1001",
            "institution_id": "demo-bank",
            "branch_code": "KTM-COMP",
        },
    )
    assert create.status_code == 201
    case = create.json()
    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={"file": ("citizenship.txt", b"Name: Completion Customer\nCitizenship No: 98-76-54", "text/plain")},
    )
    assert upload.status_code == 201
    return upload.json()


def test_reviewer_workbench_assignment_comments_and_rework():
    case = _case_with_document()

    assign = client.post(
        f"/api/cases/{case['id']}/assign",
        json={"reviewer": "checker.two", "queue": "high_value_kyc", "priority": "high"},
    )
    assert assign.status_code == 200
    assert assign.json()["assignment"]["reviewer"] == "checker.two"

    comment = client.post(
        f"/api/cases/{case['id']}/comments",
        json={"author": "checker.two", "message": "Need clearer citizenship number crop.", "field_key": "citizenship_number"},
    )
    assert comment.status_code == 201

    rework = client.post(
        f"/api/cases/{case['id']}/rework",
        json={"requester": "checker.two", "reason": "Citizenship number must be rechecked.", "fields": ["citizenship_number"]},
    )
    assert rework.status_code == 200
    assert rework.json()["status"] == "review_required"

    workbench = client.get(f"/api/review/workbench/{case['id']}")
    assert workbench.status_code == 200
    body = workbench.json()
    assert body["assignment"]["reviewer"] == "checker.two"
    assert body["comments"][0]["message"] == "Need clearer citizenship number crop."
    assert body["rework_requests"][0]["reason"] == "Citizenship number must be rechecked."
    assert body["evidence_crops"]


def test_template_studio_can_upsert_document_template_and_rules():
    response = client.post(
        "/api/admin/templates/studio",
        json={
            "document_type": "bank_statement",
            "name": "Bank Statement",
            "fields": [
                {"key": "account_number", "label": "Account Number", "required": True, "bbox": [100, 120, 520, 170]},
                {"key": "statement_period", "label": "Statement Period", "required": True, "bbox": [100, 180, 650, 230]},
            ],
            "validation_rules": [{"field_key": "account_number", "rule": "required", "severity": "error"}],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["template"]["document_type"] == "bank_statement"
    assert body["template"]["field_count"] == 2
    assert body["validation_rules"][0]["field_key"] == "account_number"

    studio = client.get("/api/admin/templates/studio").json()
    bank_statement = next(item for item in studio["templates"] if item["document_type"] == "bank_statement")
    assert bank_statement["status"] == "configured"
    assert bank_statement["field_count"] == 2


def test_only_super_admin_api_key_can_override_permanent_templates():
    original_enabled = settings.api_auth_enabled
    original_keys = settings.api_keys
    before_template = template_registry.get_template(DocumentType.passport)
    before_rules = template_registry.list_validation_rules()["passport"]
    payload = {
        "document_type": "passport",
        "name": "Super Admin Passport Revision",
        "fields": [
            {
                "key": "passport_number",
                "label": "Passport Number",
                "required": True,
                "bbox": [220, 500, 450, 545],
            }
        ],
        "validation_rules": [{"field_key": "passport_number", "rule": "required", "severity": "error"}],
    }

    try:
        settings.api_auth_enabled = True
        settings.api_keys = "tenant-admin:admin,system-secret:system,root-secret:super_admin"

        admin_response = client.post(
            "/api/admin/templates/studio",
            headers={"X-LipiOCR-API-Key": "tenant-admin"},
            json=payload,
        )
        system_response = client.post(
            "/api/admin/templates/studio",
            headers={"X-LipiOCR-API-Key": "system-secret"},
            json=payload,
        )
        super_response = client.post(
            "/api/admin/templates/studio",
            headers={"X-LipiOCR-API-Key": "root-secret"},
            json=payload,
        )

        assert admin_response.status_code == 409
        assert system_response.status_code == 409
        assert super_response.status_code == 201
        assert super_response.json()["template"]["locked"] is True
        assert super_response.json()["template"]["source"] == "system"
    finally:
        template_registry.upsert_template(
            document_type=DocumentType.passport,
            name=before_template.name,
            fields=[
                TemplateField(key=field.key, label=field.label, required=field.required, bbox=field.bbox)
                for field in before_template.fields
            ],
            validation_rules=before_rules,
            allow_system_override=True,
        )
        settings.api_auth_enabled = original_enabled
        settings.api_keys = original_keys


def test_integration_operations_configure_batch_retry_and_dead_letter():
    config = client.post(
        "/api/integrations/webhooks/configure",
        json={"key": "cbs_core", "url": "https://cbs.example.local/hooks/kyc", "events": ["case.approved"]},
    )
    assert config.status_code == 201
    assert config.json()["webhook"]["status"] == "configured"

    batch = client.post(
        "/api/integrations/sftp/batch",
        json={"profile_key": "cbs_standard", "target": "sftp://core-bank.example/outbound", "case_ids": ["case_missing"]},
    )
    assert batch.status_code == 202
    assert batch.json()["status"] == "queued"

    ops = client.get("/api/integrations/operations")
    assert ops.status_code == 200
    body = ops.json()
    assert body["webhooks"][0]["key"] == "cbs_core"
    assert body["retry_queue"]
    event_id = body["retry_queue"][0]["event_id"]

    retry = client.post(f"/api/integrations/retry/{event_id}")
    assert retry.status_code == 200
    assert retry.json()["event"]["status"] == "retry_scheduled"


def test_verification_adapter_registry_configuration_and_case_run():
    registry = client.get("/api/verification/adapters")
    assert registry.status_code == 200
    adapters = {adapter["key"]: adapter for adapter in registry.json()["adapters"]}
    assert {"national_id_registry", "pan_registry", "aml_screening", "face_liveness"}.issubset(adapters)

    configure = client.post(
        "/api/verification/adapters/pan_registry/configure",
        json={"mode": "sandbox", "endpoint": "https://ird.example.local/pan", "enabled": True},
    )
    assert configure.status_code == 200
    assert configure.json()["adapter"]["status"] == "configured"

    case = _case_with_document()
    run = client.post(f"/api/cases/{case['id']}/verification/pan_registry/run")
    assert run.status_code == 200
    assert run.json()["check"]["key"] == "pan_registry"
    assert run.json()["check"]["status"] in {"passed", "needs_review"}


def test_accuracy_analytics_records_reviewer_corrections():
    case = _case_with_document()
    correction = client.post(
        "/api/analytics/corrections",
        json={
            "case_id": case["id"],
            "field_key": "citizenship_number",
            "old_value": "98-76-54",
            "new_value": "98-76-5400",
            "corrected_by": "checker.two",
            "document_type": "citizenship",
        },
    )
    assert correction.status_code == 201

    analytics = client.get("/api/analytics/accuracy")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["correction_count"] >= 1
    assert body["field_accuracy"]["citizenship_number"]["corrections"] >= 1
    assert "citizenship" in body["document_type_performance"]


def test_standalone_upload_returns_nepal_document_intelligence_payload():
    response = client.post(
        "/api/documents/upload",
        data={"document_type": "unknown"},
        files={
            "file": (
                "old-citizenship.txt",
                "\n".join(
                    [
                        "नेपाल सरकार",
                        "जिल्ला प्रशासन कार्यालय काठमाडौँ",
                        "नेपाली नागरिकताको प्रमाणपत्र",
                        "नाम थर: सीता शर्मा",
                        "Name: Sita Sharma",
                        "ना.प्र.नं.: 27-01-78-12345",
                        "फोटो",
                        "दायाँ औंठा छाप",
                        "हस्ताक्षर",
                    ]
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document_type"] == "citizenship"
    assert body["document_variant"] == "citizenship_old_district_certificate"
    assert body["document_sections"]
    assert body["intelligence"]["document_variant"]["key"] == "citizenship_old_district_certificate"
    assert body["intelligence"]["document_sections"][0]["side"] == "front"
    assert len(body["evidence_ledger"]) >= 9
    assert {asset["asset_type"] for asset in body["assets"]}.issuperset({"photo", "fingerprint", "signature"})
    full_name = next(record for record in body["intelligence"]["entity_records"] if record["entity_key"] == "person.full_name")
    assert full_name["original_ne"] == "सीता शर्मा"
    assert full_name["original_en"] == "Sita Sharma"


def test_accuracy_analytics_exposes_correction_memory_by_variant_and_handwriting():
    case = _case_with_document()
    correction = client.post(
        "/api/analytics/corrections",
        json={
            "case_id": case["id"],
            "field_key": "full_name_np",
            "old_value": "सित शर्मा",
            "new_value": "सीता शर्मा",
            "corrected_by": "checker.two",
            "document_type": "citizenship",
            "document_variant": "citizenship_old_district_certificate",
            "block_type": "handwriting",
        },
    )
    assert correction.status_code == 201

    analytics = client.get("/api/analytics/accuracy")
    assert analytics.status_code == 200
    memory = analytics.json()["correction_memory"]
    assert memory["variant_memory"]["citizenship_old_district_certificate"]["corrections"] >= 1
    assert memory["field_memory"]["full_name_np"]["corrections"] >= 1
    assert memory["handwriting_memory"]["corrections"] >= 1


def test_accuracy_benchmark_api_exposes_field_language_and_handwriting_breakdowns():
    benchmark = client.get("/api/analytics/benchmark")

    assert benchmark.status_code == 200
    body = benchmark.json()
    assert "by_field" in body
    assert "by_language" in body
    assert "handwriting" in body
    assert "confidence_buckets" in body
