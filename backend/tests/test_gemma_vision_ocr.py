from app.core.config import Settings
from app.models import DocumentType
from app.services.ocr import GemmaVisionOcrProvider, get_ocr_provider, parse_gemma_ocr_content


def test_parse_gemma_ocr_content_preserves_nepali_handwriting_metadata():
    content = """```json
    {
      "lines": [
        {
          "text": "हस्तलिखित नाम: सीता शर्मा",
          "confidence": 0.62,
          "script": "handwriting",
          "language": "nep",
          "bbox": [110, 300, 780, 350]
        },
        {
          "text": "Citizenship No: 27-01-78-12345",
          "confidence": 0.91,
          "script": "printed",
          "language": "eng"
        }
      ]
    }
    ```"""

    observations = parse_gemma_ocr_content(content)

    assert observations[0]["text"] == "हस्तलिखित नाम: सीता शर्मा"
    assert observations[0]["block_type"] == "handwriting"
    assert observations[0]["language"] == "nep"
    assert observations[0]["bbox"] == [110, 300, 780, 350]
    assert observations[1]["block_type"] == "text"


def test_parse_gemma_ocr_content_falls_back_to_multiline_text():
    observations = parse_gemma_ocr_content('{"text": "नेपाल सरकार\\nनाम थर: सीता शर्मा"}')

    assert [observation["text"] for observation in observations] == ["नेपाल सरकार", "नाम थर: सीता शर्मा"]
    assert all(observation["field_key"] == "raw_text" for observation in observations)


def test_parse_gemma_ocr_content_preserves_structured_field_candidates():
    content = """{
      "document_type": "asba_application",
      "lines": [{"text": "NIC ASIA", "confidence": 0.91, "script": "printed"}],
      "fields": [
        {
          "key": "applicant_name",
          "value": "Rudra Man Isuwa",
          "confidence": 0.82,
          "script": "handwriting",
          "language": "eng",
          "bbox": [132, 254, 380, 278]
        },
        {
          "key": "client_id",
          "value": "00546982",
          "confidence": 0.88,
          "script": "handwriting",
          "language": "eng"
        }
      ]
    }"""

    observations = parse_gemma_ocr_content(content)

    field_observations = [observation for observation in observations if observation["field_key"] != "raw_text"]
    assert field_observations[0]["field_key"] == "applicant_name"
    assert field_observations[0]["text"] == "Rudra Man Isuwa"
    assert field_observations[0]["block_type"] == "handwriting"
    assert field_observations[0]["bbox"] == [132, 254, 380, 278]
    assert field_observations[1]["field_key"] == "client_id"
    assert field_observations[1]["text"] == "00546982"


def test_parse_gemma_ocr_content_salvages_lines_from_truncated_json():
    content = '{"lines":[{"text":"नेपाल सरकार","confidence":0.88},{"text":"नाम थर: सीता शर्मा","confidence":0.82},{"text":"unterminated'

    observations = parse_gemma_ocr_content(content)

    assert [observation["text"] for observation in observations] == ["नेपाल सरकार", "नाम थर: सीता शर्मा"]
    assert observations[0]["confidence"] == 0.45
    assert observations[0]["field_key"] == "raw_text"


def test_get_ocr_provider_supports_remote_gemma_vision():
    provider = get_ocr_provider(
        "gemma_vision",
        settings=Settings(
            gemma_enabled=True,
            gemma_api_base="http://127.0.0.1:8003/v1",
            gemma_model="gemma-4-26b-4bit",
        ),
    )

    assert isinstance(provider, GemmaVisionOcrProvider)
    assert provider.name == "gemma_vision"
    assert provider.settings.gemma_model == "gemma-4-26b-4bit"


def test_gemma_vision_provider_builds_multimodal_request(tmp_path):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"lines":[{"text":"हस्तलिखित रकम: ५०००","confidence":0.66,"script":"handwriting","language":"nep"}]}'
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self):
            self.payload = None

        def post(self, url, json):
            self.url = url
            self.payload = json
            return FakeResponse()

    image = tmp_path / "asba.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0")
    http_client = FakeClient()
    provider = GemmaVisionOcrProvider(
        Settings(gemma_api_base="http://gemma.local/v1", gemma_model="gemma-4-26b-4bit"),
        http_client=http_client,
    )

    observations = provider.read(image, DocumentType.asba_application)

    assert http_client.url == "http://gemma.local/v1/chat/completions"
    assert http_client.payload["model"] == "gemma-4-26b-4bit"
    assert http_client.payload["messages"][0]["content"][1]["type"] == "image_url"
    assert "fields:[{key,value,confidence,script,language,bbox}]" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "applicant_name" in http_client.payload["messages"][0]["content"][0]["text"]
    assert http_client.payload["max_tokens"] >= 6000
    assert observations[0]["text"] == "हस्तलिखित रकम: ५०००"
    assert observations[0]["block_type"] == "handwriting"
