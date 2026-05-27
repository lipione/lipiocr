from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_case_upload_document_and_export_evidence_backed_fields():
    create = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Sita Sharma",
            "customer_ref": "CBS-1001",
            "institution_id": "demo-bank",
            "branch_code": "KTM-001",
        },
    )

    assert create.status_code == 201
    case = create.json()
    assert case["status"] == "created"
    assert case["applicant_name"] == "Sita Sharma"
    assert case["integration_ref"] == "CBS-1001"

    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={"file": ("citizenship.txt", b"Name: Sita Sharma\nCitizenship No: 27-01-78-12345", "text/plain")},
    )

    assert upload.status_code == 201
    updated = upload.json()
    document = updated["documents"][0]
    fields = {field["key"]: field for field in updated["extracted_fields"]}

    assert document["document_type"] == "citizenship"
    assert document["pages"][0]["blocks"][0]["bbox"]
    assert fields["full_name"]["value"] == "Sita Sharma"
    assert fields["full_name"]["evidence"]["source_page"] == 1
    assert fields["full_name"]["extracted_by"] in {"gemma-4-26b-4bit", "deterministic-fallback"}
    assert updated["status"] == "review_required"
    assert updated["audit_events"][-1]["action"] == "document_processed"

    review = client.patch(
        f"/api/cases/{case['id']}/review",
        json={
            "reviewer": "checker.one",
            "decision": "approve",
            "field_updates": {"mobile": "9841000000"},
            "note": "Verified with source document.",
        },
    )

    assert review.status_code == 200
    approved = review.json()
    assert approved["status"] == "approved"
    assert approved["review"]["reviewer"] == "checker.one"

    export = client.get(f"/api/cases/{case['id']}/export")
    assert export.status_code == 200
    payload = export.json()
    assert payload["case_id"] == case["id"]
    assert payload["integration_ref"] == "CBS-1001"
    assert payload["fields"]["mobile"] == "9841000000"
    assert payload["evidence"]["full_name"]["source_page"] == 1


def test_ai_health_and_integration_manifest_are_enterprise_ready():
    ai = client.get("/api/ai/health").json()
    manifest = client.get("/api/integrations/manifest").json()

    assert ai["model"] == "gemma-4-26b-4bit"
    assert ai["provider"] == "vllm-openai-compatible"
    assert "rest_api" in manifest["modes"]
    assert "webhooks" in manifest["modes"]
    assert "sftp" in manifest["modes"]
