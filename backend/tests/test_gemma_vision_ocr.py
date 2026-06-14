import httpx
from PIL import Image

from app.core.config import Settings
from app.models import DocumentType
from app.services.ocr import (
    GemmaVisionOcrProvider,
    PaddleOcrProvider,
    get_ocr_provider,
    observations_from_tesseract_data,
    parse_gemma_ocr_content,
)


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


def test_parse_gemma_ocr_content_preserves_identity_document_asset_regions():
    content = """{
      "document_type": "citizenship",
      "lines": [{"text": "नेपाली नागरिकताको प्रमाणपत्र", "confidence": 0.91}],
      "asset_regions": [
        {"type": "photo", "label": "Applicant photo", "confidence": 0.84, "bbox": [70, 300, 360, 620]},
        {"asset_type": "fingerprint", "label": "Right thumbprint", "confidence": 0.80, "bbox": [60, 600, 360, 870]},
        {"asset_type": "signature", "label": "Holder signature", "confidence": 0.77, "bbox": [90, 650, 380, 720]}
      ]
    }"""

    observations = parse_gemma_ocr_content(content)

    asset_observations = [observation for observation in observations if observation["block_type"] in {"photo", "fingerprint", "signature"}]
    assert [observation["block_type"] for observation in asset_observations] == ["photo", "fingerprint", "signature"]
    assert asset_observations[0]["field_key"] == "raw_text"
    assert asset_observations[0]["text"] == "Applicant photo"
    assert asset_observations[1]["bbox"] == [60, 600, 360, 870]


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
            gemma_model="lipione-gemma4-12b",
        ),
    )

    assert isinstance(provider, GemmaVisionOcrProvider)
    assert provider.name == "gemma_vision"
    assert provider.settings.gemma_model == "lipione-gemma4-12b"


def test_get_ocr_provider_supports_paddle_gemma_alias_with_configured_language():
    provider = get_ocr_provider(
        "paddle_gemma",
        settings=Settings(
            ocr_provider="paddle_gemma",
            paddle_lang="en",
            gemma_enabled=True,
            gemma_api_base="http://127.0.0.1:8002/v1",
            gemma_model="gemma-4",
        ),
    )

    assert isinstance(provider, PaddleOcrProvider)
    assert provider.name == "paddleocr"
    assert provider.settings.paddle_lang == "en"
    assert provider.settings.gemma_model == "gemma-4"


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
    assert "asset_regions" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "bbox coordinates must use [left, top, right, bottom]" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "Do not paraphrase visible text" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "LipiCore Vision 12B OCR/ICR" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "strict OCR engine" in http_client.payload["messages"][0]["content"][0]["text"]
    assert "applicant_name" in http_client.payload["messages"][0]["content"][0]["text"]
    assert http_client.payload["max_tokens"] == 1200
    assert observations[0]["text"] == "हस्तलिखित रकम: ५०००"
    assert observations[0]["block_type"] == "handwriting"


def test_gemma_vision_provider_normalizes_transposed_page_coordinates(tmp_path):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"lines":['
                                '{"text":"Applicant Name","confidence":0.92,"bbox":[360,50,370,130]},'
                                '{"text":"ASHISH SINGH","confidence":0.91,"bbox":[490,150,505,300]}'
                                '],'
                                '"fields":['
                                '{"key":"applicant_name","value":"ASHISH SINGH","confidence":0.91,'
                                '"bbox":[490,150,505,300]}'
                                "]} "
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def post(self, url, json):
            return FakeResponse()

    image = tmp_path / "ipo.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0")
    provider = GemmaVisionOcrProvider(
        Settings(gemma_api_base="http://gemma.local/v1", gemma_model="gemma-4-26b-4bit"),
        http_client=FakeClient(),
    )

    observations = provider.read(image, DocumentType.ipo_application)

    assert observations[0]["bbox"] == [50, 360, 130, 370]
    assert observations[1]["bbox"] == [150, 490, 300, 505]
    assert observations[2]["bbox"] == [150, 490, 300, 505]


def test_gemma_vision_provider_tiles_large_page_after_timeout(tmp_path):
    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    class FakeClient:
        def __init__(self):
            self.calls = []

        def post(self, url, json):
            self.calls.append(json)
            if len(self.calls) == 1:
                raise httpx.ReadTimeout("timed out")
            tile_number = len(self.calls) - 1
            top = 10
            return FakeResponse(
                '{"lines":[{"text":"Tile %s text","confidence":0.81,"bbox":[20,%s,320,%s]}],'
                '"fields":[{"key":"full_name_np","value":"राजेश घले","confidence":0.82,"bbox":[40,%s,360,%s]}]}'
                % (tile_number, top, top + 24, top + 34, top + 58)
            )

    image = tmp_path / "citizenship.jpg"
    Image.new("RGB", (900, 1800), "white").save(image)
    http_client = FakeClient()
    provider = GemmaVisionOcrProvider(
        Settings(
            gemma_api_base="http://gemma.local/v1",
            gemma_model="lipione-gemma4-12b",
            gemma_vision_tile_count=3,
            gemma_vision_tile_overlap_px=50,
        ),
        http_client=http_client,
    )

    observations = provider.read(image, DocumentType.citizenship)

    assert len(http_client.calls) == 4
    assert [observation["text"] for observation in observations if observation["field_key"] == "raw_text"] == [
        "Tile 1 text",
        "Tile 2 text",
        "Tile 3 text",
    ]
    assert observations[0]["bbox"] == [20, 10, 320, 34]
    assert observations[2]["bbox"] == [20, 560, 320, 584]
    assert observations[4]["bbox"] == [20, 1160, 320, 1184]
    assert observations[1]["field_key"] == "full_name_np"
    assert "vertical page region 1 of 3" in http_client.calls[1]["messages"][0]["content"][0]["text"]


def test_gemma_vision_provider_tiles_large_page_when_full_page_is_too_sparse(tmp_path):
    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    class FakeClient:
        def __init__(self):
            self.calls = 0

        def post(self, url, json):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse('{"lines":[{"text":"NMB BANK LIMITED","confidence":0.80,"bbox":[20,20,260,50]}]}')
            return FakeResponse(
                '{"lines":[{"text":"Applicant Name: Rudra Man Isuwa","confidence":0.85,"bbox":[30,30,520,58]},'
                '{"text":"Mobile: 9808525464","confidence":0.87,"bbox":[30,80,330,108]}]}'
            )

    image = tmp_path / "asba.jpg"
    Image.new("RGB", (1158, 1600), "white").save(image)
    provider = GemmaVisionOcrProvider(
        Settings(
            gemma_api_base="http://gemma.local/v1",
            gemma_model="lipione-gemma4-12b",
            gemma_vision_tile_count=2,
            gemma_vision_tile_min_lines=4,
        ),
        http_client=FakeClient(),
    )

    observations = provider.read(image, DocumentType.asba_application)

    assert [observation["text"] for observation in observations] == [
        "Applicant Name: Rudra Man Isuwa",
        "Mobile: 9808525464",
        "Applicant Name: Rudra Man Isuwa",
        "Mobile: 9808525464",
    ]
    assert observations[2]["bbox"] == [30, 734, 520, 762]


def test_observations_from_tesseract_data_groups_words_into_line_boxes():
    data = {
        "page_num": [1, 1, 1, 1],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
        "text": ["Applicant", "Name", "Mobile", "No"],
        "conf": ["92", "88", "90", "-1"],
        "left": [10, 110, 10, 80],
        "top": [20, 21, 60, 60],
        "width": [90, 60, 60, 25],
        "height": [18, 18, 18, 18],
    }

    observations = observations_from_tesseract_data(data, page_width=714, page_height=1024)

    assert len(observations) == 2
    assert observations[0]["text"] == "Applicant Name"
    assert observations[0]["bbox"] == [10, 20, 170, 39]
    assert observations[0]["confidence"] == 0.9
    assert observations[0]["page_width"] == 714
    assert observations[0]["page_height"] == 1024
    assert observations[1]["text"] == "Mobile No"
    assert observations[1]["bbox"] == [10, 60, 105, 78]
