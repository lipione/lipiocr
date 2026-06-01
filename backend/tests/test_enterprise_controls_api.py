from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_tenant_rbac_and_audit_controls_are_exposed():
    tenant = client.get("/api/admin/tenant")
    rbac = client.get("/api/admin/rbac")
    audit = client.get("/api/admin/audit-integrity")

    assert tenant.status_code == 200
    assert rbac.status_code == 200
    assert audit.status_code == 200

    tenant_body = tenant.json()
    roles = {role["key"]: role for role in rbac.json()["roles"]}
    audit_body = audit.json()

    assert tenant_body["country"] == "Nepal"
    assert "KYC" in tenant_body["enabled_workflows"]
    assert {"maker", "checker", "auditor", "admin", "super_admin"}.issubset(roles)
    assert "approve_case" in roles["checker"]["permissions"]
    assert "manage_system_templates" in roles["super_admin"]["permissions"]
    assert audit_body["chain_status"] in {"clean", "no_events"}
    assert "events_checked" in audit_body


def test_review_queue_summary_tracks_review_required_cases():
    create = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Queue Customer",
            "customer_ref": "CBS-QUEUE-1",
            "institution_id": "demo-bank",
            "branch_code": "PKR-002",
        },
    )
    assert create.status_code == 201
    case = create.json()
    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={"file": ("citizenship.txt", b"Name: Queue Customer\nCitizenship No: 11-22-33", "text/plain")},
    )
    assert upload.status_code == 201

    queue = client.get("/api/review/queue")

    assert queue.status_code == 200
    body = queue.json()
    assert body["counts"]["review_required"] >= 1
    assert any(item["case_id"] == case["id"] for item in body["items"])
    assert body["sla"]["maker_checker_required"] is True
