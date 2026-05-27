from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_citizenship_document_creates_reviewable_record():
    response = client.post(
        "/api/documents/upload",
        data={"document_type": "citizenship"},
        files={"file": ("citizenship-sample.txt", b"demo file", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    fields = {field["key"]: field for field in body["fields"]}

    assert body["document_type"] == "citizenship"
    assert body["status"] == "review_required"
    assert body["overall_confidence"] == 0.91
    assert fields["name"]["value"] == "Sita Sharma"
    assert fields["citizenship_number"]["validation_status"] == "valid"
    assert body["audit_events"][0]["action"] == "document_uploaded"
    assert body["audit_events"][-1]["action"] == "ocr_completed"


def test_reviewer_can_correct_fields_approve_and_export_json():
    upload = client.post(
        "/api/documents/upload",
        data={"document_type": "account_opening"},
        files={"file": ("account-form.txt", b"demo file", "text/plain")},
    )
    document_id = upload.json()["id"]

    review = client.patch(
        f"/api/documents/{document_id}/review",
        json={
            "reviewer": "pilot.officer",
            "field_updates": {
                "mobile": "9841000000",
                "email": "sita.sharma@example.com",
            },
            "decision": "approve",
            "note": "Verified against source form.",
        },
    )

    assert review.status_code == 200
    reviewed = review.json()
    reviewed_fields = {field["key"]: field for field in reviewed["fields"]}

    assert reviewed["status"] == "approved"
    assert reviewed_fields["mobile"]["value"] == "9841000000"
    assert reviewed_fields["mobile"]["confidence"] == 1.0
    assert reviewed["audit_events"][-1]["action"] == "review_approved"

    exported = client.get(f"/api/documents/{document_id}/export").json()

    assert exported["document_id"] == document_id
    assert exported["status"] == "approved"
    assert exported["fields"]["mobile"] == "9841000000"
    assert exported["review"]["reviewer"] == "pilot.officer"
