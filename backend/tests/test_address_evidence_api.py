from fastapi.testclient import TestClient

from app.main import app, settings


client = TestClient(app)
ADMIN_HEADERS = {"X-LipiOCR-API-Key": "admin-secret"}
MAKER_HEADERS = {"X-LipiOCR-API-Key": "maker-secret"}


def _configure_auth_and_store(tmp_path):
    original_enabled = settings.api_auth_enabled
    original_keys = settings.api_keys
    original_path = settings.address_evidence_path
    settings.api_auth_enabled = True
    settings.api_keys = "admin-secret:admin,maker-secret:maker"
    settings.address_evidence_path = str(tmp_path / "address_evidence.json")
    return original_enabled, original_keys, original_path


def _restore_auth_and_store(original):
    settings.api_auth_enabled, settings.api_keys, settings.address_evidence_path = original


def test_address_evidence_search_returns_reference_results():
    response = client.get("/api/reference/address-evidence?q=Samakushi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Samakushi"
    assert payload["results"]
    assert payload["results"][0]["name_en"] == "Samakhusi"


def test_address_evidence_search_rejects_invalid_limit():
    response = client.get("/api/reference/address-evidence?q=Samakushi&limit=-1")

    assert response.status_code == 400
    assert "limit must be between" in response.json()["detail"]


def test_address_evidence_resolve_returns_candidates():
    response = client.post(
        "/api/reference/address-evidence/resolve",
        json={"text": "Kathmadu Metropolitian ward 26 Samakushi", "target_field": "permanent_address"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"]
    assert payload["candidates"][0]["structured"]["district"] == "Kathmandu"


def test_address_evidence_create_and_delete_roundtrip(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        create = client.post(
            "/api/reference/address-evidence",
            headers=ADMIN_HEADERS,
            json={
                "tenant_id": "other-tenant",
                "visibility": "tenant_private",
                "kind": "area_or_tole",
                "district_name": "Kathmandu",
                "local_level_name": "Kathmandu Metropolitan City",
                "ward": "26",
                "name_en": "Naya Bazaar",
                "aliases_en": ["Nayabazar"],
                "source": "manual_seed",
            },
        )

        assert create.status_code == 201
        record = create.json()["record"]
        record_id = record["id"]
        assert record["tenant_id"] == "demo-institution"

        search = client.get("/api/reference/address-evidence?q=Nayabazar", headers=ADMIN_HEADERS)
        assert search.status_code == 200
        assert any(item["id"] == record_id for item in search.json()["results"])

        deleted = client.delete(f"/api/reference/address-evidence/{record_id}", headers=ADMIN_HEADERS)
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "disabled"
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_mutations_require_manage_templates(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        response = client.post(
            "/api/reference/address-evidence",
            headers=MAKER_HEADERS,
            json={"kind": "area_or_tole", "name_en": "Maker Area"},
        )

        assert response.status_code == 403
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_import_supports_records_list(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        response = client.post(
            "/api/reference/address-evidence/import",
            headers=ADMIN_HEADERS,
            json={
                "records": [
                    {
                        "tenant_id": "other-tenant",
                        "kind": "street_or_road",
                        "district_name": "Kathmandu",
                        "local_level_name": "Kathmandu Metropolitan City",
                        "ward": "26",
                        "name_en": "Tenant Road",
                        "aliases_en": ["Tenant Rd"],
                    }
                ]
            },
        )

        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert response.json()["records"][0]["tenant_id"] == "demo-institution"
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_patch_updates_accessible_record_without_tenant_impersonation(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        create = client.post(
            "/api/reference/address-evidence",
            headers=ADMIN_HEADERS,
            json={"kind": "area_or_tole", "name_en": "Patch Area", "aliases_en": ["Patch Old"]},
        )
        record_id = create.json()["record"]["id"]

        patched = client.patch(
            f"/api/reference/address-evidence/{record_id}",
            headers=ADMIN_HEADERS,
            json={"tenant_id": "other-tenant", "name_en": "Patched Area", "aliases_en": ["Patch New"]},
        )

        assert patched.status_code == 200
        assert patched.json()["record"]["name_en"] == "Patched Area"
        assert patched.json()["record"]["tenant_id"] == "demo-institution"
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_mutations_cannot_change_shared_reference_records(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        patched = client.patch(
            "/api/reference/address-evidence/addr_seed_samakhusi",
            headers=ADMIN_HEADERS,
            json={"name_en": "Mutated Shared Area"},
        )
        deleted = client.delete("/api/reference/address-evidence/addr_seed_samakhusi", headers=ADMIN_HEADERS)

        assert patched.status_code == 403
        assert deleted.status_code == 403
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_create_rejects_shared_reference_payload(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        response = client.post(
            "/api/reference/address-evidence",
            headers=ADMIN_HEADERS,
            json={"visibility": "shared_reference", "kind": "area_or_tole", "name_en": "Shared Impersonation"},
        )

        assert response.status_code == 403
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_create_rejects_unsupported_record_values(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        response = client.post(
            "/api/reference/address-evidence",
            headers=ADMIN_HEADERS,
            json={"visibility": "tenant_private", "kind": "planet", "name_en": "Mars"},
        )

        assert response.status_code == 400
        assert "Unsupported address evidence kind" in response.json()["detail"]
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_create_rejects_bad_confidence_weight(tmp_path):
    original = _configure_auth_and_store(tmp_path)
    try:
        response = client.post(
            "/api/reference/address-evidence",
            headers=ADMIN_HEADERS,
            json={"visibility": "tenant_private", "kind": "area_or_tole", "name_en": "Bad Weight", "confidence_weight": "high"},
        )

        assert response.status_code == 400
        assert "confidence_weight must be numeric" in response.json()["detail"]
    finally:
        _restore_auth_and_store(original)


def test_address_evidence_create_and_delete_roundtrip_without_auth():
    create = client.post(
        "/api/reference/address-evidence",
        json={
            "tenant_id": "demo-institution",
            "visibility": "tenant_private",
            "kind": "area_or_tole",
            "district_name": "Kathmandu",
            "local_level_name": "Kathmandu Metropolitan City",
            "ward": "26",
            "name_en": "Naya Bazaar",
            "aliases_en": ["Nayabazar"],
            "source": "manual_seed",
        },
    )

    assert create.status_code == 201
    record_id = create.json()["record"]["id"]

    search = client.get("/api/reference/address-evidence?q=Nayabazar")
    assert search.status_code == 200
    assert any(item["id"] == record_id for item in search.json()["results"])

    deleted = client.delete(f"/api/reference/address-evidence/{record_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "disabled"
