from app.models import CaseType, DocumentType, FinancialDocument, KycCase, OcrBlock, OcrPage
from app.services.document_intelligence import analyze_document, apply_document_intelligence, compare_person_names
from app.services.kyc_intelligence import build_case_intelligence


def _document(text: str, declared: DocumentType = DocumentType.unknown) -> FinancialDocument:
    blocks = [
        OcrBlock(
            text=line,
            bbox=[80, 100 + index * 40, 920, 130 + index * 40],
            confidence=0.88,
            language="mixed",
        )
        for index, line in enumerate(text.splitlines())
        if line.strip()
    ]
    return FinancialDocument(
        filename="kyc-packet.txt",
        declared_document_type=declared,
        document_type=declared,
        pages=[OcrPage(page_number=1, width=1000, height=1400, blocks=blocks, ocr_confidence=0.88)],
        page_count=1,
    )


def test_analyze_document_detects_type_and_canonical_bilingual_fields():
    document = _document(
        "\n".join(
            [
                "नेपाल सरकार",
                "नेपाली नागरिकताको प्रमाणपत्र",
                "नाम थर: सीता शर्मा",
                "Name: Sita Sharma",
                "जन्म मिति: २०४९/०१/०१",
                "ना.प्र.नं.: 27-01-78-12345",
                "ठेगाना: काठमाण्डौ",
            ]
        )
    )

    analysis = analyze_document(document)

    assert analysis["document_type"] == "citizenship"
    assert analysis["confidence"] >= 0.85
    assert analysis["canonical_fields"]["full_name_np"] == "सीता शर्मा"
    assert analysis["canonical_fields"]["full_name_en"] == "Sita Sharma"
    assert analysis["canonical_fields"]["dob_bs"] == "2049-01-01"
    assert analysis["canonical_fields"]["dob_ad"] == "1992-04-13"
    assert analysis["canonical_fields"]["citizenship_number"] == "27-01-78-12345"
    assert analysis["language_pairs"][0]["canonical_key"] == "full_name"
    assert analysis["cross_checks"][0]["status"] == "needs_review"


def test_apply_document_intelligence_upserts_fields_and_sets_unknown_document_type():
    document = _document(
        "\n".join(
            [
                "Government of Nepal",
                "नेपाली नागरिकताको प्रमाणपत्र",
                "नाम थर: सीता शर्मा",
                "Name: Sita Sharma",
                "जन्म मिति: २०४९/०१/०१",
                "ना.प्र.नं.: 27-01-78-12345",
            ]
        )
    )
    fields = []

    analysis = apply_document_intelligence(document, fields)
    fields_by_key = {field.key: field for field in fields}

    assert document.document_type == DocumentType.citizenship
    assert analysis["document_type"] == "citizenship"
    assert fields_by_key["full_name_np"].value == "सीता शर्मा"
    assert fields_by_key["full_name_en"].value == "Sita Sharma"
    assert fields_by_key["dob_bs"].value == "2049-01-01"
    assert fields_by_key["dob_ad"].value == "1992-04-13"
    assert fields_by_key["citizenship_number"].value == "27-01-78-12345"
    assert fields_by_key["full_name_np"].source == "document_intelligence"
    assert fields_by_key["dob_ad"].extracted_by == "LipiCore"


def test_document_intelligence_uses_value_script_for_bilingual_applicant_labels():
    document = _document(
        "\n".join(
            [
                "NIC ASIA",
                "हितोपत्र खरिद सार्वजनिक निष्कासन दरखास्त फारम",
                "Applicant Name Np: रुद्रमान इसुवा",
                "Applicant Name En: Rudra Man Isuwa",
            ]
        )
    )

    analysis = analyze_document(document)

    assert analysis["document_type"] == "asba_application"
    assert analysis["canonical_fields"]["full_name_np"] == "रुद्रमान इसुवा"
    assert analysis["canonical_fields"]["full_name_en"] == "Rudra Man Isuwa"


def test_analyze_document_returns_normalization_and_confidence_repair_audit():
    document = FinancialDocument(
        filename="citizenship-bilingual.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.83,
                blocks=[
                    OcrBlock(
                        text="नाम थर: रुद्रमान इसुवा",
                        bbox=[80, 100, 920, 130],
                        confidence=0.62,
                        language="ne",
                    ),
                    OcrBlock(
                        text="Name: Rudra Man Isuwa",
                        bbox=[80, 150, 920, 180],
                        confidence=0.94,
                        language="en",
                    ),
                ],
            )
        ],
        page_count=1,
    )

    analysis = analyze_document(document)

    assert analysis["canonical_fields"]["name_ne"] == "रुद्रमान इसुवा"
    assert analysis["canonical_fields"]["name_en"] == "Rudra Man Isuwa"
    assert analysis["normalizations"]["name_ne"]["original_value"] == "रुद्रमान इसुवा"
    assert analysis["normalizations"]["name_ne"]["normalized_value"] == "rudra man isuwa"
    assert analysis["normalizations"]["name_en"]["normalized_value"] == "rudra man isuwa"

    repair = analysis["confidence_repairs"][0]
    assert repair["target_field"] == "full_name_np"
    assert repair["original_ocr_value"] == "रुद्रमान इसुवा"
    assert repair["corrected_value"] == "Rudra Man Isuwa"
    assert repair["source_field_used"] == "full_name_en"
    assert repair["original_confidence"] == 0.67
    assert repair["confidence"] > repair["original_confidence"]
    assert "not overwritten" in repair["audit_reason"].lower()


def test_compare_person_names_transliterates_general_nepali_names():
    comparison = compare_person_names("किरण लामा", "Kiran Lama")

    assert comparison["status"] == "same_person_likely"
    assert comparison["confidence"] >= 0.90
    assert comparison["left_normalized"]
    assert comparison["right_normalized"] == "kiran lama"


def test_apply_document_intelligence_attaches_reviewer_safe_bilingual_correction_metadata():
    document = FinancialDocument(
        filename="bilingual-name.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.80,
                blocks=[
                    OcrBlock(
                        text="नाम थर: किरण लामा",
                        bbox=[80, 100, 920, 130],
                        confidence=0.55,
                        language="ne",
                    ),
                    OcrBlock(
                        text="Name: Kiran Lama",
                        bbox=[80, 150, 920, 180],
                        confidence=0.94,
                        language="en",
                    ),
                ],
            )
        ],
        page_count=1,
    )
    fields = []

    analysis = apply_document_intelligence(document, fields)
    fields_by_key = {field.key: field for field in fields}
    nepali_field = fields_by_key["full_name_np"]

    assert analysis["language_pairs"][0]["status"] == "matched"
    assert analysis["confidence_repairs"][0]["target_field"] == "full_name_np"
    assert nepali_field.value == "किरण लामा"
    assert nepali_field.original_ocr_value == "किरण लामा"
    assert nepali_field.corrected_value == "Kiran Lama"
    assert nepali_field.source_field_used == "full_name_en"
    assert nepali_field.correction_confidence and nepali_field.correction_confidence > 0.85
    assert "reviewer confirmation" in (nepali_field.audit_reason or "").lower()


def test_confidence_repair_does_not_suggest_when_bilingual_names_conflict():
    document = FinancialDocument(
        filename="conflicting-bilingual-name.txt",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.80,
                blocks=[
                    OcrBlock(
                        text="नाम थर: किरण लामा",
                        bbox=[80, 100, 920, 130],
                        confidence=0.55,
                        language="ne",
                    ),
                    OcrBlock(
                        text="Name: Maya Sharma",
                        bbox=[80, 150, 920, 180],
                        confidence=0.94,
                        language="en",
                    ),
                ],
            )
        ],
        page_count=1,
    )

    analysis = analyze_document(document)

    assert analysis["language_pairs"][0]["status"] == "needs_review"
    assert analysis["confidence_repairs"] == []


def test_case_intelligence_reconciles_spelling_variants_across_documents():
    citizenship = _document(
        "\n".join(
            [
                "नेपाली नागरिकताको प्रमाणपत्र",
                "Name: Rudra Man Isuwa",
                "Citizenship No: 27-01-78-12345",
            ]
        ),
        declared=DocumentType.citizenship,
    )
    citizenship.filename = "citizenship.txt"
    bank_form = _document(
        "\n".join(
            [
                "हितोपत्र खरिद सार्वजनिक निष्कासन दरखास्त फारम",
                "Applicant Name: Rudra M. Isuwa",
                "DP ID: 13013700",
            ]
        ),
        declared=DocumentType.asba_application,
    )
    bank_form.filename = "asba.txt"
    case = KycCase(case_type=CaseType.individual_kyc, applicant_name="Rudra Man Isuwa")
    case.documents.extend([citizenship, bank_form])

    intelligence = build_case_intelligence(case)

    reconciliation = intelligence["entity_reconciliation"][0]
    assert reconciliation["status"] == "same_person_likely"
    assert reconciliation["left_value"] == "Rudra Man Isuwa"
    assert reconciliation["right_value"] == "Rudra M. Isuwa"
    assert reconciliation["confidence"] >= 0.88
    assert "middle initial" in reconciliation["reason"].lower()
