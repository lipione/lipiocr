from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_individual_case() -> dict:
    response = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Sita Sharma",
            "customer_ref": "CBS-1001",
            "institution_id": "demo-bank",
            "branch_code": "KTM-001",
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload_citizenship(case_id: str) -> dict:
    response = client.post(
        f"/api/cases/{case_id}/documents",
        data={"declared_document_type": "citizenship"},
        files={
            "file": (
                "citizenship.txt",
                b"Government of Nepal\nName: Sita Sharma\nCitizenship No: 27-01-78-12345\nDistrict: Kathmandu",
                "text/plain",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def test_kyc_intelligence_returns_readiness_checklist_and_gaps():
    case = _create_individual_case()
    _upload_citizenship(case["id"])

    response = client.get(f"/api/cases/{case['id']}/intelligence")

    assert response.status_code == 200
    body = response.json()
    checklist = {item["key"]: item for item in body["checklist"]}

    assert body["case_id"] == case["id"]
    assert body["country"] == "Nepal"
    assert body["readiness_score"] < 100
    assert checklist["citizenship"]["satisfied"] is True
    assert checklist["pan"]["satisfied"] is False
    assert checklist["photo_or_signature"]["satisfied"] is False
    assert "review" in body["recommended_action"]


def test_split_classify_and_validate_case_packet():
    case = _create_individual_case()
    _upload_citizenship(case["id"])

    split = client.post(f"/api/cases/{case['id']}/split-preview")
    assert split.status_code == 200
    segments = split.json()["segments"]
    assert segments[0]["document_type"] == "citizenship"
    assert segments[0]["page_start"] == 1
    assert segments[0]["confidence"] >= 0.75

    classify = client.post(f"/api/cases/{case['id']}/classify")
    assert classify.status_code == 200
    classifications = classify.json()["classifications"]
    assert classifications[0]["predicted_type"] == "citizenship"
    assert classifications[0]["action"] in {"kept", "updated"}

    validate = client.post(f"/api/cases/{case['id']}/validate")
    assert validate.status_code == 200
    validation = validate.json()
    codes = {finding["code"] for finding in validation["findings"]}

    assert validation["case_id"] == case["id"]
    assert "required_document_missing" in codes
    assert "ready_for_auto_approval" not in codes
    assert validation["summary"]["blocking_issue_count"] >= 1
