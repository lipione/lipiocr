from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def test_demo_extract_endpoint_returns_labeled_bilingual_fields_without_api_key():
    response = client.post(
        "/api/demo/extract",
        files={
            "file": (
                "citizenship-demo.txt",
                "ना.प्र.नं.: २७-०१-७५-१२७५१\nनाम थर: जेश घले\nFull Name: Jesh Ghale\nजन्म मिति: २०५९-०७-१७".encode(
                    "utf-8"
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    fields = {field["key"]: field for field in body["fields"]}

    assert body["document_type"] == "citizenship"
    assert fields["citizenship_number"]["normalized_value"] == "27-01-75-12751"
    assert fields["full_name_np"]["value_en"] == "Jesh Ghale"
    assert fields["full_name_en"]["value_ne"] == "जेश घले"
    assert "document_understanding" in body


def test_demo_extract_pages_returns_page_results_and_visual_assets(tmp_path):
    image_path = tmp_path / "citizenship-page.jpg"
    Image.new("RGB", (1200, 800), "white").save(image_path)

    response = client.post(
        "/api/demo/extract-pages",
        data={"prefer_lipicore": "false"},
        files=[
            (
                "files",
                (
                    "citizenship-page-1.txt",
                    "नेपाली नागरिकताको प्रमाणपत्र\nना.प्र.नं.: २४८/३६१६३\nनाम थर: राजेश घले".encode("utf-8"),
                    "text/plain",
                ),
            ),
            ("files", ("citizenship-page-2.jpg", image_path.read_bytes(), "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert len(body["pages"]) == 2
    assert body["pages"][0]["page_number"] == 1
    assert body["pages"][1]["page_number"] == 2
    assert "fields" in body
    assert isinstance(body["visual_assets"], list)
