from app.models import DocumentType, FinancialDocument, OcrBlock, OcrPage
from app.services.document_intelligence import analyze_document, apply_document_intelligence
from app.services.nepali_name_lexicon import NameLexicon


def test_nepali_only_lexicon_suggests_roman_ocr_correction():
    lexicon = NameLexicon.from_nepali_names(["राजेश कार्की", "सीता शर्मा", "किरण लामा"])

    candidates = lexicon.suggest("Rajesh Kaki", counterpart="राजेश कार्की", field_key="full_name_en")

    assert candidates
    assert candidates[0]["suggested_value"] == "Rajesh Karki"
    assert candidates[0]["candidate_tokens"][-1]["suggested_roman"] == "karki"
    assert "nepali_name_lexicon" in candidates[0]["sources"]
    assert "bilingual_pair" in candidates[0]["sources"]
    assert candidates[0]["confidence"] >= 0.90


def test_document_intelligence_exposes_name_correction_candidates():
    document = FinancialDocument(
        filename="name-correction.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=700,
                ocr_confidence=0.82,
                blocks=[
                    OcrBlock(text="नाम थर: राजेश कार्की", bbox=[60, 80, 460, 120], confidence=0.94, language="np"),
                    OcrBlock(text="Full Name: Rajesh Kaki", bbox=[60, 140, 460, 180], confidence=0.58, language="en"),
                ],
            )
        ],
        page_count=1,
    )

    analysis = analyze_document(document)
    candidate = analysis["name_candidates"][0]

    assert candidate["target_field"] == "full_name_en"
    assert candidate["original_ocr_value"] == "Rajesh Kaki"
    assert candidate["suggested_value"] == "Rajesh Karki"
    assert candidate["status"] == "suggested"


def test_apply_document_intelligence_attaches_name_candidates_to_review_field():
    document = FinancialDocument(
        filename="name-correction.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=700,
                ocr_confidence=0.82,
                blocks=[
                    OcrBlock(text="नाम थर: राजेश कार्की", bbox=[60, 80, 460, 120], confidence=0.94, language="np"),
                    OcrBlock(text="Full Name: Rajesh Kaki", bbox=[60, 140, 460, 180], confidence=0.58, language="en"),
                ],
            )
        ],
        page_count=1,
    )
    fields = []

    analysis = apply_document_intelligence(document, fields)
    fields_by_key = {field.key: field for field in fields}

    english_name = fields_by_key["full_name_en"]
    assert english_name.corrected_value == "Rajesh Karki"
    assert english_name.source_field_used == "full_name_np+name_lexicon"
    assert english_name.correction_candidates
    assert english_name.correction_candidates[0]["suggested_value"] == "Rajesh Karki"
    assert analysis["name_candidates"][0]["suggested_value"] == "Rajesh Karki"
