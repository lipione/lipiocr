from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_routes_remain_available_after_router_split():
    assert client.get("/health").json()["status"] == "ok"
    public_ai = client.get("/api/ai/health").json()
    assert public_ai["provider"] == "LipiCore"
    assert public_ai["model"] == "LipiCore"


def test_integration_manifest_remains_public_after_router_split():
    response = client.get("/api/integrations/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "LipiOCR Enterprise"
    assert "rest_api" in body["modes"]
