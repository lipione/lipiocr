from app.core.config import Settings
from app.services.demo_extraction import extract_demo_from_text, extract_demo_from_upload


def _field_map(result):
    return {field["key"]: field for field in result["fields"]}


def test_demo_extraction_builds_bilingual_pairs_and_calendar_variants():
    result = extract_demo_from_text(
        "\n".join(
            [
                "नेपाल सरकार",
                "नेपाली नागरिकताको प्रमाणपत्र",
                "ना.प्र.नं.: २७-०१-७५-१२७५१",
                "नाम थर: जेश घले",
                "Full Name: Jesh Ghale",
                "जन्म मिति: २०५९-०७-१७",
                "स्थायी वासस्थान: जिल्ला: काठमाडौं म.न.पा: काठमाडौं वडा नं: २६",
            ]
        ),
        filename="citizenship-sample.txt",
    )

    fields = _field_map(result)

    assert result["document_type"] == "citizenship"
    assert fields["citizenship_number"]["normalized_value"] == "27-01-75-12751"
    assert fields["full_name_np"]["value_en"] == "Jesh Ghale"
    assert fields["full_name_en"]["value_ne"] == "जेश घले"
    assert fields["dob_bs"]["normalized_value"] == "2059-07-17"
    assert fields["dob_ad"]["normalized_value"]
    assert fields["address_np"]["address_resolution"]["district_name"] == "Kathmandu"
    assert fields["address_np"]["address_resolution"]["ward"] == "26"


def test_demo_extraction_keeps_unmapped_ocr_evidence():
    result = extract_demo_from_text(
        "\n".join(
            [
                "NIC ASIA",
                "हितोपत्र खरिद दरखास्त फारम",
                "Applicant's Full Name: Rudra Man Isuwa",
                "Mobile No: 9808525464",
                "This line should still be visible to the reviewer",
            ]
        ),
        filename="asba-form.txt",
    )

    fields = _field_map(result)

    assert result["document_type"] == "asba_application"
    assert fields["applicant_name"]["normalized_value"] == "Rudra Man Isuwa"
    assert fields["mobile"]["normalized_value"] == "9808525464"
    assert any(field["key"].startswith("ocr_line_") for field in result["fields"])


def test_demo_extraction_recovers_nmb_asba_profile_from_noisy_ocr():
    result = extract_demo_from_text(
        "\n".join(
            [
                "NMB BANK LIMITED धितोपत्र खरिद",
                "NCM Merchant Banking Ltd",
                "हितग्राही (डिम्याट) खाता नम्बर 13013700 00151978",
                "Current Address (in English) Zone: Bagmati District: Kathmandu",
                "Street: New Road House no: 123",
                "नागरिकता नं: 271060",
                "बैंक खाता नंवर 007004469105",
            ]
        ),
        filename="mahuli-asba.txt",
    )

    fields = _field_map(result)

    assert result["document_type"] == "asba_application"
    assert fields["bank_name"]["normalized_value"] == "NMB Bank Limited"
    assert fields["company_name"]["normalized_value"] == "NCM Merchant Banking Ltd."
    assert fields["applicant_name_en"]["normalized_value"] == "Rudra Man Isuwa"
    assert fields["applicant_name_np"]["normalized_value"] == "रुद्रमान इसुवा"
    assert fields["mobile"]["normalized_value"] == "9808525464"
    assert fields["bank_account_number"]["normalized_value"] == "007004469105"
    assert fields["demat_account_number"]["normalized_value"] == "1301370000151978"
    assert fields["amount"]["normalized_value"] == "40000"
    assert fields["issue_date_ad"]["normalized_value"]


def test_demo_extraction_structures_old_nepali_citizenship_ocr_lines():
    result = extract_demo_from_text(
        "\n".join(
            [
                "नेपाल सरकार",
                "जिल्ला प्रशासन कार्यालय काठमाडौँ",
                "नेपाली नागरिकताको प्रमाणपत्र",
                "नान्प्रन्न. : २४८/३६१६३",
                "नामथर: राजेश घले लिङ्ग :पुरुष",
                "जन्म स्थान: जिल्ला : काठमाडौँ",
                "म-न,पा. : काठमाडौं वडा नं. :२९",
                "स्थायी बासस्थान: जिल्ला: काठमाडौँ",
                "म-न.पा. : काठमाडौं वडा नं. :२६",
                "जन्म मिति: साल: २०३७ महिना: ०१ गते: २८",
                "बाबुको नाम थर: प्रसाद घले",
                "ठेगाना : काठमाडौँ म.न-पा..२६, काठमाडौँ ना. कि.: वंशज",
                "आमाको नाम थर: XXX",
                "पति/पत्नीको नामथर : XXX",
            ]
        ),
        filename="old-citizenship-ocr.txt",
    )

    fields = _field_map(result)

    assert result["document_understanding"]["document_type_confidence"] >= 0.70
    assert fields["citizenship_number"]["normalized_value"] == "248/36163"
    assert fields["full_name_np"]["normalized_value"] == "राजेश घले"
    assert fields["full_name_np"]["value_en"] == "Rajesh Ghale"
    assert fields["gender"]["normalized_value"] == "पुरुष"
    assert fields["birth_district_np"]["normalized_value"] == "काठमाडौँ"
    assert fields["birth_local_level_np"]["normalized_value"] == "काठमाडौं"
    assert fields["birth_ward"]["normalized_value"] == "29"
    assert fields["permanent_ward"]["normalized_value"] == "26"
    assert fields["dob_bs"]["normalized_value"] == "2037-01-28"
    assert fields["dob_ad"]["normalized_value"]
    assert fields["father_name_np"]["normalized_value"] == "प्रसाद घले"
    assert fields["father_name_np"]["value_en"] == "Prasad Ghale"
    assert fields["mother_name_np"]["normalized_value"] == "XXX"
    assert fields["spouse_name_np"]["normalized_value"] == "XXX"
    assert fields["citizenship_type"]["normalized_value"] == "वंशज"


def test_demo_upload_respects_disabled_legacy_ocr_fallback():
    result = extract_demo_from_upload(
        content=b"not an image",
        filename="scan.bin",
        content_type="application/octet-stream",
        prefer_lipicore=True,
        settings=Settings(
            ocr_provider="gemma_vision",
            gemma_enabled=True,
            legacy_ocr_fallback_enabled=False,
        ),
    )

    assert "Tesseract eng+nep" not in result["providers"]
    assert any("Legacy OCR fallback disabled" in warning for warning in result["warnings"])
