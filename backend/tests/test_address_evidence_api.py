from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_address_evidence_search_returns_reference_results():
    response = client.get("/api/reference/address-evidence?q=Samakushi")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Samakushi"
    assert payload["results"]
    assert payload["results"][0]["name_en"] == "Samakhusi"


def test_address_evidence_resolve_returns_candidates():
    response = client.post(
        "/api/reference/address-evidence/resolve",
        json={"text": "Kathmadu Metropolitian ward 26 Samakushi", "target_field": "permanent_address"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"]
    assert payload["candidates"][0]["structured"]["district"] == "Kathmandu"


def test_address_evidence_create_and_delete_roundtrip():
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
