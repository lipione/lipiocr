from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_advanced_verification_returns_provider_status_and_next_steps():
    create = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Sita Sharma",
            "customer_ref": "CBS-VERIFY-1",
            "institution_id": "demo-bank",
            "branch_code": "BRT-003",
        },
    )
    assert create.status_code == 201
    case = create.json()
    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={
            "file": (
                "packet.txt",
                b"Name: Sita Sharma\nCitizenship No: 27-01-78-12345\nPhoto attached\nSignature present",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201

    response = client.post(f"/api/cases/{case['id']}/verification/run")

    assert response.status_code == 200
    body = response.json()
    checks = {check["key"]: check for check in body["checks"]}

    expected = {
        "national_id_registry",
        "pan_registry",
        "aml_screening",
        "face_liveness",
        "document_tamper",
        "signature_presence",
        "duplicate_case",
    }
    assert body["case_id"] == case["id"]
    assert expected.issubset(checks)
    assert checks["national_id_registry"]["status"] == "not_configured"
    assert checks["aml_screening"]["status"] == "not_configured"
    assert checks["signature_presence"]["status"] in {"passed", "needs_review"}
    assert body["next_steps"]
