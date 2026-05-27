from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _case_with_reviewed_mobile() -> dict:
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
    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={"file": ("citizenship.txt", b"Name: Sita Sharma\nCitizenship No: 27-01-78-12345", "text/plain")},
    )
    assert upload.status_code == 201
    review = client.patch(
        f"/api/cases/{case['id']}/review",
        json={
            "reviewer": "checker.one",
            "decision": "approve",
            "field_updates": {"mobile": "9841000000"},
            "note": "Approved for export test.",
        },
    )
    assert review.status_code == 200
    return review.json()


def test_integration_profiles_are_enterprise_ready():
    response = client.get("/api/integrations/profiles")

    assert response.status_code == 200
    body = response.json()
    profile_keys = {profile["key"] for profile in body["profiles"]}

    assert {"manual_export", "rest_api", "webhooks", "sftp", "embedded_review"}.issubset(profile_keys)
    assert body["country"] == "Nepal"
    assert body["security"]["webhook_signature"] == "HMAC-SHA256"


def test_webhook_embedded_link_and_export_profiles_are_stable():
    case = _case_with_reviewed_mobile()

    webhook = client.post(
        "/api/integrations/webhook/test",
        json={"case_id": case["id"], "event": "case.approved"},
    )
    assert webhook.status_code == 200
    webhook_body = webhook.json()
    assert webhook_body["signature"].startswith("sha256=")
    assert webhook_body["payload"]["event"] == "case.approved"
    assert webhook_body["payload"]["case_id"] == case["id"]

    link = client.post(f"/api/cases/{case['id']}/embedded-review-link")
    assert link.status_code == 200
    link_body = link.json()
    assert link_body["case_id"] == case["id"]
    assert "/review/" in link_body["url"]
    assert link_body["token"]

    export = client.get(f"/api/cases/{case['id']}/export-profile/cbs_standard")
    assert export.status_code == 200
    export_body = export.json()
    assert export_body["profile_key"] == "cbs_standard"
    assert export_body["payload"]["customer"]["reference"] == "CBS-1001"
    assert export_body["payload"]["customer"]["mobile"] == "9841000000"
