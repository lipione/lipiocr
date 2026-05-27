from app.models import CaseType, DocumentType, OcrBlock, OcrPage
from app.services.gemma import (
    GemmaExtractionResult,
    build_extraction_messages,
    parse_gemma_extraction,
)


def test_parse_gemma_extraction_removes_markdown_and_preserves_evidence():
    content = """```json
    {
      "document_type": "citizenship",
      "summary": "Nepali citizenship document",
      "fields": [
        {
          "key": "full_name",
          "label": "Full Name",
          "value": "Sita Sharma",
          "confidence": 0.92,
          "source_page": 1,
          "evidence_text": "Name: Sita Sharma",
          "bbox": [100, 120, 420, 160]
        }
      ],
      "findings": [
        {
          "severity": "warning",
          "code": "needs_review",
          "message": "Citizenship number is faint",
          "field_key": "citizenship_number"
        }
      ]
    }
    ```"""

    result = parse_gemma_extraction(content)

    assert isinstance(result, GemmaExtractionResult)
    assert result.document_type == DocumentType.citizenship
    assert result.fields[0].key == "full_name"
    assert result.fields[0].evidence.source_page == 1
    assert result.findings[0].code == "needs_review"


def test_build_extraction_messages_targets_nepal_kyc_and_json_only():
    page = OcrPage(
        page_number=1,
        width=1000,
        height=1400,
        blocks=[
            OcrBlock(
                text="Name: Sita Sharma",
                bbox=[100, 120, 420, 160],
                confidence=0.94,
                block_type="text",
            )
        ],
    )

    messages = build_extraction_messages(
        case_type=CaseType.individual_kyc,
        expected_document_type=DocumentType.unknown,
        pages=[page],
    )

    assert messages[0]["role"] == "system"
    assert "Nepal financial KYC" in messages[0]["content"]
    assert "JSON only" in messages[0]["content"]
    assert "Name: Sita Sharma" in messages[1]["content"][0]["text"]
