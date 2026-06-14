from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_platform_status_exposes_production_readiness_gaps():
    response = client.get("/api/platform/status")

    assert response.status_code == 200
    body = response.json()
    components = {component["key"]: component for component in body["components"]}

    assert body["country"] == "Nepal"
    assert body["deployment_target"] == "on_prem_or_private_cloud"
    assert {"ocr_pipeline", "gemma_brain", "persistence", "object_storage", "security", "integrations"}.issubset(
        components
    )
    assert components["ocr_pipeline"]["status"] in {"configured", "partial"}
    assert components["persistence"]["status"] in {"partial", "configured"}
    assert components["security"]["status"] in {"not_configured", "partial"}
    assert body["next_actions"]


def test_ocr_pipeline_profile_describes_real_provider_path():
    response = client.get("/api/ocr/pipeline")

    assert response.status_code == 200
    body = response.json()
    provider_keys = {provider["key"] for provider in body["providers"]}
    stage_keys = {stage["key"] for stage in body["preprocessing_stages"]}

    assert {"mock", "tesseract", "paddleocr", "gemma_vision"}.issubset(provider_keys)
    assert {"deskew", "denoise", "rotation_detection", "language_routing", "confidence_calibration"}.issubset(
        stage_keys
    )
    assert body["outputs"] == [
        "ocr_pages",
        "text_blocks",
        "field_candidates",
        "asset_regions",
        "bounding_boxes",
        "confidence_scores",
    ]


def test_operations_dashboard_tracks_lanes_and_bottlenecks():
    create = client.post(
        "/api/cases",
        json={
            "case_type": "individual_kyc",
            "applicant_name": "Ops Customer",
            "customer_ref": "OPS-1001",
            "institution_id": "demo-bank",
            "branch_code": "KTM-OPS",
        },
    )
    assert create.status_code == 201
    case = create.json()
    upload = client.post(
        f"/api/cases/{case['id']}/documents",
        data={"declared_document_type": "citizenship"},
        files={"file": ("citizenship.txt", b"Name: Ops Customer\nCitizenship No: 12-34-56", "text/plain")},
    )
    assert upload.status_code == 201

    response = client.get("/api/dashboard/operations")

    assert response.status_code == 200
    body = response.json()
    lanes = {lane["key"]: lane for lane in body["lanes"]}

    assert {"intake", "review", "verification", "exceptions", "export"}.issubset(lanes)
    assert lanes["review"]["count"] >= 1
    assert body["counts"]["total_cases"] >= 1
    assert body["bottlenecks"]
    assert "KTM-OPS" in body["branch_load"]


def test_template_studio_lists_enterprise_document_profiles():
    response = client.get("/api/admin/templates/studio")

    assert response.status_code == 200
    body = response.json()
    template_keys = {template["document_type"] for template in body["templates"]}

    assert "citizenship" in template_keys
    assert "account_opening" in template_keys
    assert body["extraction_modes"] == ["template_coordinates", "full_page_reasoning", "human_review"]
