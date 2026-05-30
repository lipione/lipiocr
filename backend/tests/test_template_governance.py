from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _profile_payload(name: str = "Governed Citizenship"):
    return {
        "format": "lipiocr.template-profile.v1",
        "profile": {
            "name": name,
            "document_type": "citizenship",
            "version": 1,
            "status": "published",
            "tenant_id": "demo-institution",
            "approval_status": "pending",
            "pages": [],
            "fields": [
                {
                    "key": "citizenship_number",
                    "label": "Citizenship Number",
                    "page_number": 1,
                    "bbox": [80, 100, 420, 140],
                    "type": "text",
                    "required": True,
                    "language_hint": "mixed",
                    "validation_rule": "valid",
                    "extraction_hint": "Citizenship No",
                    "confidence": 0.91,
                }
            ],
        },
    }


def test_template_profile_can_be_imported_approved_tested_exported_and_rolled_back():
    imported = client.post("/api/admin/templates/profiles/import", json=_profile_payload())
    assert imported.status_code == 201
    profile = imported.json()["profile"]

    approved = client.post(f"/api/admin/templates/profiles/{profile['id']}/approve", json={"actor": "admin.one"})
    assert approved.status_code == 200
    assert approved.json()["profile"]["approval_status"] == "approved"
    assert approved.json()["profile"]["approved_by"] == "admin.one"

    test_run = client.post(
        f"/api/admin/templates/profiles/{profile['id']}/test",
        json={"fields": [{"key": "citizenship_number", "value": "27-01-78-12345"}]},
    )
    assert test_run.status_code == 200
    assert test_run.json()["result"]["status"] == "pass"
    assert test_run.json()["result"]["required_coverage"] == 1.0

    exported = client.get(f"/api/admin/templates/profiles/{profile['id']}/export")
    assert exported.status_code == 200
    assert exported.json()["format"] == "lipiocr.template-profile.v1"

    rollback = client.post(f"/api/admin/templates/profiles/{profile['id']}/rollback", json={"target_version": 1})
    assert rollback.status_code == 200
    assert rollback.json()["profile"]["version"] == 2
    assert rollback.json()["profile"]["rollback_of"] == 1


def test_template_profiles_are_tenant_scoped_to_current_operator_context():
    imported = client.post("/api/admin/templates/profiles/import", json=_profile_payload("Tenant Scoped Template"))
    assert imported.status_code == 201

    listed = client.get("/api/admin/templates/profiles")
    assert listed.status_code == 200
    assert all(profile["tenant_id"] == "demo-institution" for profile in listed.json()["profiles"])
