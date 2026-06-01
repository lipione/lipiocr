from app.models import AuditEvent, CaseType, DocumentType, FinancialDocument, KycCase, OcrBlock, OcrPage
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


def _old_citizenship_document() -> FinancialDocument:
    return FinancialDocument(
        filename="old-citizenship.jpg",
        declared_document_type=DocumentType.unknown,
        document_type=DocumentType.unknown,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=650,
                ocr_confidence=0.86,
                blocks=[
                    OcrBlock(text="नेपाल सरकार", bbox=[80, 40, 280, 80], confidence=0.92, language="ne"),
                    OcrBlock(text="जिल्ला प्रशासन कार्यालय काठमाडौँ", bbox=[320, 72, 720, 110], confidence=0.89, language="ne"),
                    OcrBlock(text="नेपाली नागरिकताको प्रमाणपत्र", bbox=[310, 118, 730, 156], confidence=0.88, language="ne"),
                    OcrBlock(text="नाम थर: सीता शर्मा", bbox=[260, 180, 620, 220], confidence=0.62, language="ne"),
                    OcrBlock(text="Name: Sita Sharma", bbox=[260, 224, 620, 264], confidence=0.95, language="en"),
                    OcrBlock(text="ना.प्र.नं.: 27-01-78-12345", bbox=[70, 160, 320, 198], confidence=0.87, language="mixed"),
                    OcrBlock(text="फोटो", bbox=[40, 260, 250, 520], confidence=0.80, block_type="photo", language="ne"),
                    OcrBlock(
                        text="दायाँ औंठा छाप",
                        bbox=[780, 70, 930, 190],
                        confidence=0.78,
                        block_type="fingerprint",
                        language="ne",
                    ),
                    OcrBlock(text="हस्ताक्षर", bbox=[760, 520, 930, 590], confidence=0.84, block_type="signature", language="ne"),
                ],
            )
        ],
        page_count=1,
    )


def _combined_citizenship_front_back_document() -> FinancialDocument:
    return FinancialDocument(
        filename="citizenship-front-back-copy.jpg",
        declared_document_type=DocumentType.unknown,
        document_type=DocumentType.unknown,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.84,
                blocks=[
                    OcrBlock(text="नेपाली नागरिकताको प्रमाणपत्र", bbox=[90, 90, 860, 130], confidence=0.88, language="ne"),
                    OcrBlock(text="नाम थर: सीता शर्मा", bbox=[120, 180, 720, 220], confidence=0.82, language="ne"),
                    OcrBlock(text="ना.प्र.नं.: 27-01-78-12345", bbox=[120, 240, 520, 280], confidence=0.84, language="mixed"),
                    OcrBlock(text="फोटो", bbox=[760, 165, 930, 350], confidence=0.78, block_type="photo", language="ne"),
                    OcrBlock(text="बाबुको नाम: हरि शर्मा", bbox=[110, 790, 700, 830], confidence=0.81, language="ne"),
                    OcrBlock(text="आमाको नाम: माया शर्मा", bbox=[110, 850, 700, 890], confidence=0.80, language="ne"),
                    OcrBlock(text="स्थायी वासस्थान: काठमाण्डौ", bbox=[110, 910, 760, 950], confidence=0.79, language="ne"),
                    OcrBlock(text="जारी मिति: २०६७/०२/०१", bbox=[110, 970, 620, 1010], confidence=0.78, language="ne"),
                    OcrBlock(text="हस्ताक्षर", bbox=[760, 1030, 930, 1120], confidence=0.82, block_type="signature", language="ne"),
                ],
            )
        ],
        page_count=1,
    )


def _combined_national_id_front_back_document() -> FinancialDocument:
    return FinancialDocument(
        filename="national-id-front-back-copy.jpg",
        declared_document_type=DocumentType.unknown,
        document_type=DocumentType.unknown,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=1400,
                ocr_confidence=0.86,
                blocks=[
                    OcrBlock(text="Government of Nepal National Identity Card", bbox=[90, 80, 820, 122], confidence=0.91, language="en"),
                    OcrBlock(text="National ID Number: 023-456-2130", bbox=[120, 170, 760, 210], confidence=0.86, language="en"),
                    OcrBlock(text="Given Name: Bhagawati Kumari", bbox=[120, 230, 760, 270], confidence=0.85, language="en"),
                    OcrBlock(text="Date of Birth: 1978-02-05", bbox=[120, 290, 640, 330], confidence=0.84, language="en"),
                    OcrBlock(text="Photo", bbox=[760, 150, 930, 390], confidence=0.76, block_type="photo", language="en"),
                    OcrBlock(text="Father's Name: Bishnu Prasad", bbox=[110, 790, 760, 830], confidence=0.82, language="en"),
                    OcrBlock(text="Mother's Name: Sarita Kumari", bbox=[110, 850, 760, 890], confidence=0.81, language="en"),
                    OcrBlock(text="Permanent Address: Pokhara", bbox=[110, 910, 760, 950], confidence=0.80, language="en"),
                    OcrBlock(text="Date of Issue: 2017-01-01", bbox=[110, 970, 620, 1010], confidence=0.79, language="en"),
                ],
            )
        ],
        page_count=1,
    )


def _new_citizenship_front_back_document() -> FinancialDocument:
    return FinancialDocument(
        filename="new-citizenship-front-back.jpg",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=[
            OcrPage(
                page_number=1,
                width=1500,
                height=1000,
                ocr_confidence=0.88,
                blocks=[
                    OcrBlock(text="नेपाल सरकार गृह मन्त्रालय जिल्ला प्रशासन कार्यालय काठमाडौँ", bbox=[420, 40, 1100, 110], confidence=0.93, language="ne"),
                    OcrBlock(text="नेपाली नागरिकताको प्रमाणपत्र", bbox=[520, 120, 1000, 160], confidence=0.92, language="ne"),
                    OcrBlock(text="ना.प्र.नं.: २७-०१-७५-१२७५१", bbox=[60, 185, 420, 225], confidence=0.89, language="mixed"),
                    OcrBlock(text="नाम थर: जेश घले", bbox=[500, 240, 800, 280], confidence=0.90, language="ne"),
                    OcrBlock(text="लिङ्ग: पुरुष", bbox=[1120, 240, 1320, 280], confidence=0.88, language="ne"),
                    OcrBlock(text="जन्म स्थान: जिल्ला: काठमाडौं म.न.पा.: काठमाडौं वडा नं.: २६", bbox=[500, 300, 1320, 345], confidence=0.86, language="ne"),
                    OcrBlock(text="स्थायी वासस्थान: जिल्ला: काठमाडौं म.न.पा.: काठमाडौं वडा नं.: २६", bbox=[500, 375, 1320, 420], confidence=0.85, language="ne"),
                    OcrBlock(text="जन्म मिति: साल: २०५९ महिना: ०७ गते: १७", bbox=[500, 455, 1120, 500], confidence=0.86, language="ne"),
                    OcrBlock(text="बाबुको नाम थर: राजेश घले", bbox=[500, 520, 900, 565], confidence=0.86, language="ne"),
                    OcrBlock(text="आमाको नाम थर: सोनु घले", bbox=[500, 590, 900, 635], confidence=0.84, language="ne"),
                    OcrBlock(text="ना.कि.: वंशज", bbox=[1120, 590, 1320, 635], confidence=0.83, language="ne"),
                    OcrBlock(text="फोटो", bbox=[70, 300, 360, 620], confidence=0.80, block_type="photo", language="ne"),
                    OcrBlock(text="हस्ताक्षर", bbox=[90, 650, 380, 720], confidence=0.78, block_type="signature", language="ne"),
                ],
            ),
            OcrPage(
                page_number=2,
                width=1500,
                height=1000,
                ocr_confidence=0.88,
                blocks=[
                    OcrBlock(text="Government of Nepal has issued this Citizenship Certificate with following details.", bbox=[70, 45, 1320, 85], confidence=0.94, language="en"),
                    OcrBlock(text="Citizenship Certificate No.: 27-01-75-12751", bbox=[70, 110, 560, 150], confidence=0.93, language="en"),
                    OcrBlock(text="Full Name.: JESH GHALE", bbox=[70, 170, 540, 210], confidence=0.93, language="en"),
                    OcrBlock(text="Sex: Male", bbox=[1160, 110, 1320, 150], confidence=0.91, language="en"),
                    OcrBlock(text="Date of Birth (AD): Year:2002 Month:NOV Day:03", bbox=[70, 230, 980, 270], confidence=0.92, language="en"),
                    OcrBlock(text="Birth Place: District: Kathmandu Metropolitan : Kathmandu Ward No.:26", bbox=[70, 300, 1260, 340], confidence=0.90, language="en"),
                    OcrBlock(text="Permanent Address: District: Kathmandu Metropolitan : Kathmandu Ward No.:26", bbox=[70, 390, 1260, 430], confidence=0.90, language="en"),
                    OcrBlock(text="नागरिकता किसिम: वंशज", bbox=[80, 500, 420, 540], confidence=0.86, language="ne"),
                    OcrBlock(text="जारी मिति: २०७५-१०-०९", bbox=[920, 640, 1280, 680], confidence=0.84, language="ne"),
                    OcrBlock(text="प्रमाण पत्र जारी गर्ने अधिकारीको नाम थर: गंगा बहादुर भुजेल", bbox=[760, 700, 1320, 740], confidence=0.82, language="ne"),
                    OcrBlock(text="दर्जा: प्रशासकीय अधिकृत", bbox=[760, 750, 1160, 790], confidence=0.82, language="ne"),
                    OcrBlock(text="दायाँ औंठा छाप", bbox=[60, 600, 360, 870], confidence=0.80, block_type="fingerprint", language="ne"),
                    OcrBlock(text="बायाँ औंठा छाप", bbox=[420, 600, 720, 870], confidence=0.80, block_type="fingerprint", language="ne"),
                ],
            ),
        ],
        page_count=2,
    )


def test_nepal_intelligence_detects_variant_assets_ledger_and_entity_records():
    analysis = analyze_document(_old_citizenship_document())

    assert analysis["document_variant"]["key"] == "citizenship_old_district_certificate"
    assert analysis["document_variant"]["document_type"] == "citizenship"
    assert analysis["document_variant"]["confidence"] >= 0.80
    assert len(analysis["evidence_ledger"]) == 9

    ledger_asset_types = {entry["asset_type"] for entry in analysis["evidence_ledger"] if entry.get("asset_type")}
    assert {"photo", "fingerprint", "signature"}.issubset(ledger_asset_types)

    asset_types = {asset["asset_type"] for asset in analysis["assets"]}
    assert {"photo", "fingerprint", "signature"}.issubset(asset_types)

    full_name = next(record for record in analysis["entity_records"] if record["entity_key"] == "person.full_name")
    assert full_name["original_ne"] == "सीता शर्मा"
    assert full_name["original_en"] == "Sita Sharma"
    assert full_name["normalized_ne"] == "sita sharma"
    assert full_name["normalized_en"] == "sita sharma"
    assert full_name["status"] == "paired"


def test_combined_citizenship_photocopy_detects_front_and_back_sections_on_one_page():
    analysis = analyze_document(_combined_citizenship_front_back_document())

    sections = analysis["document_sections"]
    assert [section["side"] for section in sections] == ["front", "back"]
    assert {section["page_number"] for section in sections} == {1}

    ledger_by_text = {entry["text"]: entry for entry in analysis["evidence_ledger"]}
    assert ledger_by_text["नाम थर: सीता शर्मा"]["section_side"] == "front"
    assert ledger_by_text["बाबुको नाम: हरि शर्मा"]["section_side"] == "back"
    assert ledger_by_text["स्थायी वासस्थान: काठमाण्डौ"]["section_side"] == "back"

    fields_by_key = {field["key"]: field for field in analysis["detected_fields"]}
    assert fields_by_key["full_name_np"]["section_side"] == "front"
    assert fields_by_key["father_name_np"]["section_side"] == "back"
    assert fields_by_key["mother_name_np"]["section_side"] == "back"
    assert fields_by_key["address_np"]["section_side"] == "back"


def test_combined_national_id_photocopy_detects_front_and_back_sections_on_one_page():
    analysis = analyze_document(_combined_national_id_front_back_document())

    assert analysis["document_type"] == "national_id"
    assert [section["side"] for section in analysis["document_sections"]] == ["front", "back"]
    fields_by_key = {field["key"]: field for field in analysis["detected_fields"]}
    assert fields_by_key["national_id_number"]["section_side"] == "front"
    assert fields_by_key["father_name_en"]["section_side"] == "back"
    assert fields_by_key["address_en"]["section_side"] == "back"


def test_citizenship_front_back_extracts_full_catalog_and_assets():
    analysis = analyze_document(_new_citizenship_front_back_document())

    assert analysis["document_type"] == "citizenship"
    assert [section["side"] for section in analysis["document_sections"]] == ["front", "back"]

    canonical = analysis["canonical_fields"]
    assert canonical["citizenship_number"] == "27-01-75-12751"
    assert canonical["name_ne"] == "जेश घले"
    assert canonical["name_en"] == "JESH GHALE"
    assert canonical["gender"] == "Male"
    assert canonical["dob_bs"] == "2059-07-17"
    assert canonical["dob_ad"] == "2002-11-03"
    assert canonical["birth_place_district"] == "Kathmandu"
    assert canonical["birth_place_municipality"] == "Kathmandu"
    assert canonical["birth_place_ward"] == "26"
    assert canonical["permanent_address_district"] == "Kathmandu"
    assert canonical["permanent_address_municipality"] == "Kathmandu"
    assert canonical["permanent_address_ward"] == "26"
    assert canonical["father_name_ne"] == "राजेश घले"
    assert canonical["mother_name_ne"] == "सोनु घले"
    assert canonical["citizenship_type"] == "वंशज"
    assert canonical["issue_date_bs"] == "2075-10-09"
    assert canonical["issuing_office"] == "जिल्ला प्रशासन कार्यालय काठमाडौँ"
    assert canonical["issuing_authority_name"] == "गंगा बहादुर भुजेल"
    assert canonical["issuing_authority_designation"] == "प्रशासकीय अधिकृत"

    asset_types = [asset["asset_type"] for asset in analysis["assets"]]
    assert "photo" in asset_types
    assert asset_types.count("fingerprint") == 2
    assert "signature" in asset_types


def test_citizenship_field_candidates_normalize_to_canonical_keys():
    document = _document(
        "\n".join(
            [
                "नेपाल सरकार",
                "नेपाली नागरिकताको प्रमाणपत्र",
                "Citizen Id: २७-०१-७५-१२७५१",
                "Date Of Birth: साल: २०५९ महिना: ०७ गते: १७",
                "Birth Place: District: Kathmandu Metropolitan : Kathmandu Ward No.:26",
                "Permanent Address: District: Kathmandu Metropolitan : Kathmandu Ward No.:26",
                "Issuing Authority: जिल्ला प्रशासन कार्यालय काठमाडौँ",
                "Citizenship Type: वंशज",
            ]
        ),
        declared=DocumentType.citizenship,
    )

    canonical = analyze_document(document)["canonical_fields"]

    assert canonical["citizenship_number"] == "27-01-75-12751"
    assert canonical["dob_bs"] == "2059-07-17"
    assert canonical["birth_place_district"] == "Kathmandu"
    assert canonical["permanent_address_ward"] == "26"
    assert canonical["issuing_office"] == "जिल्ला प्रशासन कार्यालय काठमाडौँ"
    assert canonical["citizenship_type"] == "वंशज"


def test_apply_document_intelligence_attaches_nepal_metadata_to_document():
    document = _old_citizenship_document()
    fields = []

    analysis = apply_document_intelligence(document, fields)

    assert document.document_type == DocumentType.citizenship
    assert document.document_variant == "citizenship_old_district_certificate"
    assert document.assets
    assert document.evidence_ledger
    assert document.document_sections
    assert document.intelligence["document_variant"]["key"] == analysis["document_variant"]["key"]
    assert any(entry.mapped_field_key == "full_name_np" for entry in document.evidence_ledger)


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


def test_correction_memory_groups_by_variant_field_and_handwriting():
    from app.services.document_intelligence import build_correction_memory

    case = KycCase(case_type=CaseType.individual_kyc, applicant_name="Sita Sharma")
    case.documents.append(_old_citizenship_document())
    case.audit_events.append(
        AuditEvent(
            action="field_correction_recorded",
            actor="checker.one",
            note="full_name_np corrected",
            metadata={
                "field_key": "full_name_np",
                "old_value": "सित शर्मा",
                "new_value": "सीता शर्मा",
                "document_type": "citizenship",
                "document_variant": "citizenship_old_district_certificate",
                "block_type": "handwriting",
            },
        )
    )

    memory = build_correction_memory([case])

    assert memory["correction_count"] == 1
    assert memory["field_memory"]["full_name_np"]["corrections"] == 1
    assert memory["variant_memory"]["citizenship_old_district_certificate"]["corrections"] == 1
    assert memory["handwriting_memory"]["corrections"] == 1
    assert memory["recommendations"]
