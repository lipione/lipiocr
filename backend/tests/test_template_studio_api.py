from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_template_draft_upload_auto_maps_multiple_pages():
    response = client.post(
        "/api/admin/templates/drafts",
        data={"name": "Back Me ID", "document_type": "unknown"},
        files=[
            ("files", ("front.txt", b"Back Me ID Front\nApplicant Name: Hari Sharma\nMobile No: 9841000000", "text/plain")),
            ("files", ("back.txt", b"Back Me ID Back\nCitizenship No: 12-34-56\nAddress: Kathmandu", "text/plain")),
        ],
    )

    assert response.status_code == 201
    draft = response.json()["draft"]
    fields = {field["key"]: field for field in draft["fields"]}

    assert draft["name"] == "Back Me ID"
    assert draft["status"] == "draft"
    assert len(draft["pages"]) == 2
    assert fields["applicant_name"]["page_number"] == 1
    assert fields["mobile"]["page_number"] == 1
    assert fields["citizenship_number"]["page_number"] == 2
    assert fields["address_en"]["page_number"] == 2


def test_template_draft_uses_label_intelligence_for_blank_nepali_financial_form():
    response = client.post(
        "/api/admin/templates/drafts",
        data={"name": "NIC ASIA ASBA Blank", "document_type": "unknown"},
        files=[
            (
                "files",
                (
                    "blank-asba.txt",
                    "\n".join(
                        [
                            "NIC ASIA",
                            "हितग्राही खरिद दरखास्त फारम",
                            "DP ID",
                            "Client ID",
                            "Applicant's Full Name",
                            "Permanent Address (in English)",
                            "Mobile No",
                            "Email",
                            "Applicant Signature",
                        ]
                    ).encode("utf-8"),
                    "text/plain",
                ),
            ),
        ],
    )

    assert response.status_code == 201
    draft = response.json()["draft"]
    fields = {field["key"]: field for field in draft["fields"]}

    assert draft["document_type"] == "asba_application"
    assert draft["document_type_confidence"] >= 0.7
    assert draft["quality_score"] >= 0.65
    assert {"dp_id", "client_id", "full_name_en", "address_en", "mobile", "email", "signature"}.issubset(fields)
    assert fields["dp_id"]["detection_source"] == "label_intelligence"
    assert "DP ID" in fields["dp_id"]["detection_reason"]


def test_template_draft_can_be_adjusted_and_published_as_profile():
    upload = client.post(
        "/api/admin/templates/drafts",
        data={"name": "Loan Intake", "document_type": "unknown"},
        files=[
            ("files", ("loan.txt", b"Loan Intake Form\nRequested Amount - Rs. 500000", "text/plain")),
        ],
    )
    assert upload.status_code == 201
    draft = upload.json()["draft"]
    field = draft["fields"][0]

    update = client.patch(
        f"/api/admin/templates/drafts/{draft['id']}",
        json={
            "name": "Loan Intake v1",
            "fields": [
                {
                    **field,
                    "key": "loan_amount",
                    "label": "Loan Amount",
                    "type": "amount",
                    "required": True,
                    "bbox": [90, 120, 640, 170],
                }
            ],
        },
    )
    assert update.status_code == 200
    updated = update.json()["draft"]
    assert updated["fields"][0]["key"] == "loan_amount"
    assert updated["fields"][0]["bbox"] == [90, 120, 640, 170]

    publish = client.post(f"/api/admin/templates/drafts/{draft['id']}/publish")
    assert publish.status_code == 201
    body = publish.json()
    profile = body["profile"]

    assert profile["name"] == "Loan Intake v1"
    assert profile["status"] == "published"
    assert profile["fields"][0]["key"] == "loan_amount"
    assert body["template"]["field_count"] == 1
    assert any(item["id"] == profile["id"] for item in body["studio"]["profiles"])
