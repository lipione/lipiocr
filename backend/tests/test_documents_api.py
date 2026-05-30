from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_citizenship_document_creates_reviewable_record():
    response = client.post(
        "/api/documents/upload",
        data={"document_type": "citizenship"},
        files={
            "file": (
                "citizenship-sample.txt",
                b"Government of Nepal\nName: Sita Sharma\nCitizenship No: 27-01-78-12345",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    fields = {field["key"]: field for field in body["fields"]}

    assert body["document_type"] == "citizenship"
    assert body["status"] == "review_required"
    assert body["overall_confidence"] == 0.86
    assert fields["full_name"]["value"] == "Sita Sharma"
    assert fields["citizenship_number"]["validation_status"] == "valid"
    assert body["pages"][0]["blocks"][0]["text"] == "Government of Nepal"
    assert body["audit_events"][0]["action"] == "document_uploaded"
    assert body["audit_events"][-1]["action"] == "document_processed"


def test_upload_unknown_standalone_document_extracts_generic_fields():
    response = client.post(
        "/api/documents/upload",
        data={"declared_document_type": "unknown"},
        files={
            "file": (
                "archive-form.txt",
                b"Cooperative Member Update Request\nCustomer Code: CUST-7788\nBranch: Pokhara Lakeside\nAccount Purpose: Remittance and savings",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    fields = {field["key"]: field for field in body["fields"]}

    assert body["document_type"] == "unknown"
    assert fields["customer_code"]["value"] == "CUST-7788"
    assert fields["branch"]["value"] == "Pokhara Lakeside"
    assert fields["account_purpose"]["source"] == "generic_field_extraction"


def test_reviewer_can_correct_fields_approve_and_export_json():
    upload = client.post(
        "/api/documents/upload",
        data={"document_type": "account_opening"},
        files={
            "file": (
                "account-form.txt",
                b"Account Opening Form\nCustomer Name: Sita Sharma\nMobile: 98410O0000\nEmail: sita.sharma at example.com",
                "text/plain",
            )
        },
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


def test_reviewer_can_add_missing_standalone_field_before_template_save():
    upload = client.post(
        "/api/documents/upload",
        data={"declared_document_type": "unknown"},
        files={
            "file": (
                "loan-note.txt",
                b"Loan Request\nApplicant Name: Hari Sharma",
                "text/plain",
            )
        },
    )
    document_id = upload.json()["id"]

    review = client.patch(
        f"/api/documents/{document_id}/review",
        json={
            "reviewer": "template.officer",
            "field_updates": {
                "requested_amount": "Rs. 500000",
            },
            "decision": "save",
            "note": "Mapped missing amount from source document.",
        },
    )

    assert review.status_code == 200
    reviewed_fields = {field["key"]: field for field in review.json()["fields"]}

    assert reviewed_fields["requested_amount"]["value"] == "Rs. 500000"
    assert reviewed_fields["requested_amount"]["source"] == "reviewer_entry"
    assert reviewed_fields["requested_amount"]["confidence"] == 1.0


def test_standalone_document_can_be_reanalyzed_replaced_and_archived():
    upload = client.post(
        "/api/documents/upload",
        data={"declared_document_type": "unknown"},
        files={
            "file": (
                "general-notice.txt",
                b"General Notice\nReference No: REF-001\nBranch: Butwal",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201
    uploaded = upload.json()
    document_id = uploaded["id"]
    assert uploaded["version_history"][0]["action"] == "uploaded"

    reanalyze = client.post(f"/api/documents/{document_id}/reanalyze")
    assert reanalyze.status_code == 200
    reanalyzed = reanalyze.json()
    assert reanalyzed["id"] == document_id
    assert reanalyzed["audit_events"][-1]["action"] == "document_reanalyzed"
    assert reanalyzed["version_history"][-1]["version"] == 2
    assert reanalyzed["version_history"][-1]["action"] == "reanalyzed"

    replace = client.post(
        f"/api/documents/{document_id}/replace",
        data={"declared_document_type": "unknown"},
        files={
            "file": (
                "updated-notice.txt",
                b"Updated Notice\nReference No: REF-002\nBranch: Dharan",
                "text/plain",
            )
        },
    )
    assert replace.status_code == 200
    replaced = replace.json()
    replaced_fields = {field["key"]: field for field in replaced["fields"]}

    assert replaced["id"] == document_id
    assert replaced["filename"] == "updated-notice.txt"
    assert replaced_fields["reference_no"]["value"] == "REF-002"
    assert replaced_fields["branch"]["value"] == "Dharan"
    assert replaced["audit_events"][-1]["action"] == "document_replaced"
    assert replaced["version_history"][-1]["version"] == 3
    assert replaced["version_history"][-1]["filename"] == "updated-notice.txt"

    archived = client.post(f"/api/documents/{document_id}/archive", json={"note": "Duplicate upload"})

    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["audit_events"][-1]["action"] == "document_archived"


def test_library_document_can_be_copied_and_moved_to_application():
    case_response = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Library Target",
            "customer_ref": "LIB-APP-001",
        },
    )
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    upload = client.post(
        "/api/documents/upload",
        data={"declared_document_type": "unknown"},
        files={
            "file": (
                "branch-note.txt",
                b"Branch Note\nCustomer Code: C-901\nBranch: Lalitpur",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    copied = client.post(
        f"/api/documents/{document_id}/link-application",
        json={"case_id": case_id, "mode": "copy"},
    )
    assert copied.status_code == 200
    copied_body = copied.json()
    copied_case = copied_body["case"]
    copied_document = copied_body["document"]

    assert copied_body["mode"] == "copy"
    assert copied_case["status"] == "review_required"
    assert copied_case["documents"][-1]["id"] == document_id
    assert any(field["document_id"] == document_id and field["key"] == "customer_code" for field in copied_case["extracted_fields"])
    assert copied_document["status"] != "archived"
    assert copied_document["audit_events"][-1]["action"] == "document_linked_to_application"

    moved = client.post(
        f"/api/documents/{document_id}/link-application",
        json={"case_id": case_id, "mode": "move"},
    )
    assert moved.status_code == 200
    moved_body = moved.json()

    assert moved_body["mode"] == "move"
    assert moved_body["document"]["status"] == "archived"
    assert moved_body["document"]["version_history"][-1]["action"] == "moved_to_application"
    assert len([document for document in moved_body["case"]["documents"] if document["id"] == document_id]) == 1
