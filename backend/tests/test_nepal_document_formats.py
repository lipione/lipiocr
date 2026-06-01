from importlib import reload
from pathlib import Path
import asyncio

from app.models import CaseType, DocumentType, FinancialDocument, TemplateField
import app.services.templates as templates_module
from app.core.config import Settings, get_settings
from app.services.enterprise_extraction import build_pages_from_upload, fallback_extraction, process_enterprise_document
from app.services.gemma import GemmaReasoningClient
from app.services.ocr import MockOcrProvider


def _fallback_from_text(text: str):
    pages = build_pages_from_upload(text.encode("utf-8"), "sample.txt")
    document = FinancialDocument(
        filename="sample.txt",
        declared_document_type=DocumentType.unknown,
        document_type=DocumentType.unknown,
        pages=pages,
        page_count=len(pages),
    )
    return fallback_extraction(
        case_type=CaseType.document_digitization,
        declared_document_type=DocumentType.unknown,
        document=document,
    )


def _fields(result):
    return {field.key: field.value for field in result.fields}


def test_nepal_sample_document_templates_are_configured():
    template_registry = reload(templates_module)
    templates = {template.document_type.value: template for template in template_registry.list_templates()}

    expected_fields = {
        "citizenship": {"name_ne", "name_en", "dob_bs", "dob_ad", "citizenship_number", "permanent_address_ne", "father_name_ne"},
        "national_id": {"national_id_number", "full_name_ne", "full_name_en", "dob_bs", "dob_ad", "gender", "issue_date"},
        "passport": {"passport_number", "surname", "given_name", "nationality", "dob", "expiry_date", "mrz_line_1"},
        "driving_license": {"license_number", "full_name", "blood_group", "dob", "citizenship_number", "category"},
        "ipo_application": {"company_name", "application_number", "applicant_name", "applied_units", "amount", "boid"},
        "asba_application": {"bank_name", "applicant_name", "dp_id", "client_id", "account_number", "amount"},
    }

    for document_type, field_keys in expected_fields.items():
        assert document_type in templates
        configured = {field.key for field in templates[document_type].fields}
        assert field_keys.issubset(configured)


def test_nepal_identity_templates_are_permanent_system_templates():
    template_registry = reload(templates_module)

    assert template_registry.is_system_template(DocumentType.citizenship)
    assert template_registry.is_system_template(DocumentType.passport)
    assert template_registry.is_system_template(DocumentType.national_id)
    assert template_registry.is_system_template(DocumentType.driving_license)

    rules = template_registry.list_validation_rules()
    for document_type in ("citizenship", "passport", "national_id", "driving_license"):
        assert any(rule["rule"] == "required" for rule in rules[document_type])


def test_template_studio_persists_custom_templates_when_store_enabled(tmp_path, monkeypatch):
    store_path = tmp_path / "template-studio.json"
    monkeypatch.setenv("LIPIOCR_TEMPLATE_STORE", str(store_path))
    monkeypatch.setenv("LIPIOCR_LOAD_TEMPLATE_STORE", "true")
    get_settings.cache_clear()
    template_registry = reload(templates_module)

    template_registry.upsert_template(
        document_type=DocumentType.unknown,
        name="Loan Request Template",
        fields=[
            TemplateField(key="requested_amount", label="Requested Amount", required=False, bbox=[80, 100, 920, 134])
        ],
        validation_rules=[{"field_key": "requested_amount", "rule": "currency", "severity": "warning"}],
    )
    reloaded_registry = reload(template_registry)
    templates = {template.document_type.value: template for template in reloaded_registry.list_templates()}

    assert store_path.exists()
    assert templates["unknown"].name == "Loan Request Template"
    assert templates["unknown"].fields[0].key == "requested_amount"
    assert reloaded_registry.list_validation_rules()["unknown"][0]["field_key"] == "requested_amount"

    monkeypatch.delenv("LIPIOCR_TEMPLATE_STORE")
    monkeypatch.delenv("LIPIOCR_LOAD_TEMPLATE_STORE")
    get_settings.cache_clear()
    reload(reloaded_registry)


def test_permanent_identity_templates_cannot_be_overwritten():
    template_registry = reload(templates_module)
    before = template_registry.get_template(DocumentType.passport)

    try:
        template_registry.upsert_template(
            document_type=DocumentType.passport,
            name="Bad Passport Override",
            fields=[TemplateField(key="bad", label="Bad", required=False, bbox=[1, 2, 3, 4])],
            validation_rules=[],
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Permanent passport template was overwritten")

    after = template_registry.get_template(DocumentType.passport)
    assert after.name == before.name
    assert {field.key for field in after.fields} == {field.key for field in before.fields}


def test_full_page_fallback_extracts_nepal_identity_documents():
    national_id = _fallback_from_text(
        "Government of Nepal\n"
        "National Identity Card\n"
        "National ID No: 023-456-2130\n"
        "Name: Bhagawati Kumari\n"
        "Sex: F\n"
        "Date of Birth: 1978-02-05\n"
        "Date of Issue: 01-01-2017"
    )
    national_id_fields = _fields(national_id)

    assert national_id.document_type.value == "national_id"
    assert national_id_fields["national_id_number"] == "023-456-2130"
    assert national_id_fields["full_name"] == "Bhagawati Kumari"

    passport = _fallback_from_text(
        "NEPAL Passport\n"
        "Passport No: 05232944\n"
        "Surname: Ghimire\n"
        "Given Name: Ram\n"
        "Nationality: Nepalese\n"
        "Date of Birth: 1964-03-17\n"
        "Date of Expiry: 2021-04-16\n"
        "P<NPLGHIMIRE<<RAM<<<<<<<<<<<<<<<<<<<<<<<<"
    )
    passport_fields = _fields(passport)

    assert passport.document_type.value == "passport"
    assert passport_fields["passport_number"] == "05232944"
    assert passport_fields["surname"] == "Ghimire"
    assert passport_fields["mrz_line_1"].startswith("P<NPL")

    driving_license = _fallback_from_text(
        "Government of Nepal\n"
        "Driving License\n"
        "D.L.No.: 03-06-00354234\n"
        "Name: Kiran Lama\n"
        "B.G.: AB+\n"
        "D.O.B.: 1993-11-10\n"
        "Citizenship No.: 251059/6599\n"
        "Category: A"
    )
    license_fields = _fields(driving_license)

    assert driving_license.document_type.value == "driving_license"
    assert license_fields["license_number"] == "03-06-00354234"
    assert license_fields["category"] == "A"


def test_full_page_fallback_extracts_nepal_ipo_and_asba_forms():
    ipo = _fallback_from_text(
        "Kisan Micro Finance Bittiya Sanstha Ltd\n"
        "Share Application Form\n"
        "Application No: 011908\n"
        "Applicant Name: Ashish Singh\n"
        "No. of Share Applied: 500\n"
        "Amount Deposited: 50000\n"
        "BOID: 13013700007004469\n"
        "Bank Name: Nepal Bank Limited"
    )
    ipo_fields = _fields(ipo)

    assert ipo.document_type.value == "ipo_application"
    assert ipo_fields["company_name"] == "Kisan Micro Finance Bittiya Sanstha Ltd"
    assert ipo_fields["application_number"] == "011908"
    assert ipo_fields["boid"] == "13013700007004469"

    asba = _fallback_from_text(
        "NMB Bank Limited\n"
        "हितोपत्र खरिद सार्वजनिक निष्कासन दरखास्त फारम\n"
        "DP ID: 13013700\n"
        "Client ID: 00151978\n"
        "Applicant Name: Rudra Man Isuwa\n"
        "Bank Account No: 007004469105\n"
        "Applied Units: 400\n"
        "Amount: 40000"
    )
    asba_fields = _fields(asba)

    assert asba.document_type.value == "asba_application"
    assert asba_fields["bank_name"] == "NMB Bank Limited"
    assert asba_fields["dp_id"] == "13013700"
    assert asba_fields["client_id"] == "00151978"
    assert asba_fields["account_number"] == "007004469105"


def test_binary_sample_upload_preserves_mock_ocr_field_labels(tmp_path: Path):
    source_path = tmp_path / "license.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    async def run():
        return await process_enterprise_document(
            case_type=CaseType.document_digitization,
            filename="license.jpg",
            content=source_path.read_bytes(),
            declared_document_type=DocumentType.driving_license,
            gemma_client=GemmaReasoningClient(Settings(gemma_enabled=False)),
            source_path=source_path,
            ocr_provider=MockOcrProvider(),
        )

    document, fields, _findings = asyncio.run(run())
    extracted = {field.key: field.value for field in fields}

    assert document.document_type == DocumentType.driving_license
    assert extracted["license_number"] == "03-06-00354234"
    assert extracted["full_name"] == "Kiran Lama"
    assert extracted["category"] == "A"


def test_fallback_retains_unmapped_nepali_ocr_lines_for_reviewer_mapping():
    result = _fallback_from_text(
        "नेपाल सरकार\n"
        "नेपाली नागरिकताको प्रमाणपत्र\n"
        "ना.प्र.नं.: 27-01-78-12345\n"
        "नाम थर: सीता शर्मा\n"
        "स्थायी वासस्थान: काठमाडौं-१०\n"
        "जन्म मिति: २०४९-०१-०१\n"
        "बाबुको नाम थर: हरि शर्मा\n"
        "वडा नं.: १०"
    )

    raw_fields = [field for field in result.fields if field.source == "full_page_ocr"]
    raw_values = {field.value for field in raw_fields}
    raw_evidence = {field.evidence.evidence_text for field in raw_fields}

    assert result.document_type == DocumentType.citizenship
    assert "स्थायी वासस्थान: काठमाडौं-१०" in raw_values
    assert "जन्म मिति: २०४९-०१-०१" in raw_values
    assert "वडा नं.: १०" in raw_evidence
    assert all(not field.required for field in raw_fields)


def test_unknown_document_promotes_generic_label_value_fields_for_review():
    result = _fallback_from_text(
        "Cooperative Member Update Request\n"
        "Customer Code: CUST-7788\n"
        "Branch: Pokhara Lakeside\n"
        "Account Purpose: Remittance and savings\n"
        "Risk Category: Medium\n"
        "Officer Note: Verify income source manually"
    )
    fields = {field.key: field for field in result.fields}

    assert result.document_type == DocumentType.unknown
    assert fields["customer_code"].value == "CUST-7788"
    assert fields["branch"].value == "Pokhara Lakeside"
    assert fields["account_purpose"].value == "Remittance and savings"
    assert fields["risk_category"].value == "Medium"
    assert fields["officer_note"].value == "Verify income source manually"
    assert fields["customer_code"].source == "generic_field_extraction"
    assert fields["customer_code"].required is False


def test_unknown_document_promotes_separator_and_known_prefix_fields_for_review():
    result = _fallback_from_text(
        "Loan Request Form\n"
        "Applicant Name ........ Hari Sharma\n"
        "Mobile No 9841000000\n"
        "Requested Amount - Rs. 500000\n"
        "नाम थर हरि शर्मा\n"
        "जन्म मिति २०५०/०१/०२"
    )
    fields = {field.key: field for field in result.fields}

    assert result.document_type == DocumentType.unknown
    assert fields["applicant_name"].value == "Hari Sharma"
    assert fields["mobile"].value == "9841000000"
    assert fields["requested_amount"].value == "Rs. 500000"
    assert fields["full_name_np"].value == "हरि शर्मा"
    assert fields["dob_bs"].value == "2050/01/02"


def test_binary_raw_text_ocr_is_split_into_reviewable_lines(tmp_path: Path):
    from app.services.ocr import OcrObservation

    class MultilineProvider:
        name = "multiline"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(
                    field_key="raw_text",
                    text="नेपाल सरकार\nनाम थर: सीता शर्मा\nठेगाना: काठमाडौं-१०",
                    confidence=0.73,
                )
            ]

    source_path = tmp_path / "citizenship.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    pages = build_pages_from_upload(
        source_path.read_bytes(),
        "citizenship.jpg",
        ocr_provider=MultilineProvider(),
        source_path=source_path,
        document_type=DocumentType.citizenship,
    )

    assert [block.text for block in pages[0].blocks] == [
        "नेपाल सरकार",
        "नाम थर: सीता शर्मा",
        "ठेगाना: काठमाडौं-१०",
    ]


def test_binary_structured_ocr_candidates_are_not_treated_as_printed_labels(tmp_path: Path):
    from app.services.ocr import OcrObservation

    class CandidateProvider:
        name = "candidate"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(
                    field_key="dp_id",
                    text="011908",
                    confidence=0.97,
                    block_type="text",
                    language="eng",
                    bbox=[750, 400, 850, 420],
                )
            ]

    source_path = tmp_path / "ipo.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    pages = build_pages_from_upload(
        source_path.read_bytes(),
        "ipo.jpg",
        ocr_provider=CandidateProvider(),
        source_path=source_path,
        document_type=DocumentType.ipo_application,
    )

    assert pages[0].blocks[0].text == "Dp Id: 011908"
    assert pages[0].blocks[0].block_type == "field_candidate"


def test_binary_ocr_preserves_handwriting_blocks_for_review(tmp_path: Path):
    from app.services.ocr import OcrObservation

    class HandwritingProvider:
        name = "handwriting"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(
                    field_key="raw_text",
                    text="हस्तलिखित नाम: सीता शर्मा",
                    confidence=0.61,
                    block_type="handwriting",
                    language="nep",
                    bbox=[120, 420, 760, 470],
                )
            ]

    source_path = tmp_path / "handwritten-citizenship.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")
    pages = build_pages_from_upload(
        source_path.read_bytes(),
        "handwritten-citizenship.jpg",
        ocr_provider=HandwritingProvider(),
        source_path=source_path,
        document_type=DocumentType.citizenship,
    )
    document = FinancialDocument(
        filename="handwritten-citizenship.jpg",
        declared_document_type=DocumentType.citizenship,
        document_type=DocumentType.citizenship,
        pages=pages,
        page_count=len(pages),
    )

    result = fallback_extraction(
        case_type=CaseType.individual_kyc,
        declared_document_type=DocumentType.citizenship,
        document=document,
    )

    assert pages[0].blocks[0].block_type == "handwriting"
    assert pages[0].blocks[0].language == "nep"
    handwriting_fields = [field for field in result.fields if field.source == "handwriting_ocr"]
    assert handwriting_fields[0].value == "हस्तलिखित नाम: सीता शर्मा"
    assert handwriting_fields[0].bbox == [120, 420, 760, 470]


def test_process_document_keeps_handwriting_ocr_when_gemma_returns_structured_fields(tmp_path: Path):
    from app.models import ExtractedField
    from app.services.gemma import GemmaExtractionResult
    from app.services.ocr import OcrObservation

    class HandwritingProvider:
        name = "handwriting"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(
                    field_key="raw_text",
                    text="हस्तलिखित रकम: ५०००",
                    confidence=0.64,
                    block_type="handwriting",
                    language="nep",
                    bbox=[100, 300, 700, 350],
                )
            ]

    class StructuredGemma:
        settings = Settings(gemma_enabled=True, gemma_model="gemma-4-26b-4bit")

        async def extract(self, *, case_type: CaseType, expected_document_type: DocumentType, pages):
            return GemmaExtractionResult(
                document_type=DocumentType.asba_application,
                summary="Structured Gemma fields only",
                fields=[
                    ExtractedField(
                        key="amount",
                        label="Amount",
                        value="5000",
                        confidence=0.82,
                        source="gemma_reasoning",
                    )
                ],
                findings=[],
            )

    source_path = tmp_path / "asba-handwriting.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    async def run():
        return await process_enterprise_document(
            case_type=CaseType.individual_kyc,
            filename="asba-handwriting.jpg",
            content=source_path.read_bytes(),
            declared_document_type=DocumentType.asba_application,
            gemma_client=StructuredGemma(),
            source_path=source_path,
            ocr_provider=HandwritingProvider(),
        )

    _document, fields, _findings = asyncio.run(run())

    assert any(field.key == "amount" and field.source == "gemma_reasoning" for field in fields)
    handwriting_fields = [field for field in fields if field.source == "handwriting_ocr"]
    assert handwriting_fields[0].value == "हस्तलिखित रकम: ५०००"


def test_process_document_indexes_lipicore_citizenship_fields_into_intelligence(tmp_path: Path):
    from app.models import ExtractedField
    from app.services.gemma import GemmaExtractionResult
    from app.services.ocr import OcrObservation

    class MinimalProvider:
        name = "minimal"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(
                    field_key="raw_text",
                    text="नेपाल सरकार\nनेपाली नागरिकताको प्रमाणपत्र",
                    confidence=0.80,
                    block_type="text",
                    language="nep",
                    bbox=[80, 80, 900, 140],
                )
            ]

    class StructuredCitizenshipGemma:
        settings = Settings(gemma_enabled=True, gemma_model="gemma-4-26b-4bit")

        async def extract(self, *, case_type: CaseType, expected_document_type: DocumentType, pages):
            return GemmaExtractionResult(
                document_type=DocumentType.citizenship,
                summary="Structured citizenship fields",
                fields=[
                    ExtractedField(key="citizen_id", label="ना.प्र.नं.", value="२७-०१-७५-१२७५१", confidence=0.92),
                    ExtractedField(key="date_of_birth", label="जन्म मिति", value="साल: २०५९ महिना: ०७ गते: १७", confidence=0.86),
                    ExtractedField(
                        key="permanent_address",
                        label="Permanent Address",
                        value="District: Kathmandu Metropolitan : Kathmandu Ward No.:26",
                        confidence=0.86,
                    ),
                ],
                findings=[],
            )

    source_path = tmp_path / "citizenship.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    async def run():
        return await process_enterprise_document(
            case_type=CaseType.individual_kyc,
            filename="citizenship.jpg",
            content=source_path.read_bytes(),
            declared_document_type=DocumentType.citizenship,
            gemma_client=StructuredCitizenshipGemma(),
            source_path=source_path,
            ocr_provider=MinimalProvider(),
        )

    document, fields, _findings = asyncio.run(run())
    fields_by_key = {field.key: field for field in fields}

    assert fields_by_key["citizenship_number"].value == "27-01-75-12751"
    assert fields_by_key["dob_bs"].value == "2059-07-17"
    assert fields_by_key["permanent_address_ward"].value == "26"
    assert document.intelligence["canonical_fields"]["permanent_address_district"] == "Kathmandu"


def test_noisy_nic_asia_asba_ocr_recovers_core_fields(tmp_path: Path):
    from app.services.ocr import OcrObservation

    class NoisyNicAsbaProvider:
        name = "noisy_nic_asba"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(field_key="raw_text", text="NIC ASIA", confidence=0.45),
                OcrObservation(field_key="raw_text", text="1729", confidence=0.45),
                OcrObservation(field_key="raw_text", text="क्युमुलेटिभ - ६", confidence=0.45),
                OcrObservation(
                    field_key="raw_text",
                    text="दिपिनो सर्दि (सार्वजनिक शिक्षकान) दरसार्त फारम",
                    confidence=0.45,
                ),
            ]

    source_path = tmp_path / "NIC-BANK-714x1024.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    async def run():
        return await process_enterprise_document(
            case_type=CaseType.individual_kyc,
            filename=source_path.name,
            content=source_path.read_bytes(),
            declared_document_type=DocumentType.unknown,
            gemma_client=GemmaReasoningClient(Settings(gemma_enabled=False)),
            source_path=source_path,
            ocr_provider=NoisyNicAsbaProvider(),
        )

    document, fields, _findings = asyncio.run(run())
    extracted = {field.key: field.value for field in fields}

    assert document.document_type == DocumentType.asba_application
    assert extracted.get("applicant_name") != "Rudra Man Isuwa"
    assert extracted.get("client_id") != "00546982"
    assert extracted.get("mobile") != "9808525464"
    assert extracted.get("email") != "rudraman@gmail.com"
    assert extracted.get("amount") != "35600"


def test_nic_asia_asba_uses_observed_values_instead_of_demo_recovery(tmp_path: Path):
    from app.services.ocr import OcrObservation

    class ConflictingNicAsbaProvider:
        name = "conflicting_nic_asba"

        def read(self, file_path: Path, document_type: DocumentType):
            return [
                OcrObservation(field_key="raw_text", text="NIC ASIA", confidence=0.99),
                OcrObservation(field_key="raw_text", text="दिपितो सर्बिक दरखास्त फारम", confidence=0.99),
                OcrObservation(field_key="applicant_name", text="Np: कृष्णमान ट्वुवा", confidence=0.96),
                OcrObservation(field_key="dp_id", text="13013700", confidence=0.99),
                OcrObservation(field_key="client_id", text="146942086", confidence=0.99),
                OcrObservation(field_key="boid", text="0056982", confidence=0.99),
                OcrObservation(field_key="mobile", text="9805825464", confidence=0.94),
                OcrObservation(field_key="amount", text="9280", confidence=0.97),
                OcrObservation(field_key="applied_units", text="22300", confidence=0.97),
            ]

    source_path = tmp_path / "NIC-BANK-714x1024.jpg"
    source_path.write_bytes(b"\xff\xd8\xff\xe0")

    async def run():
        return await process_enterprise_document(
            case_type=CaseType.individual_kyc,
            filename=source_path.name,
            content=source_path.read_bytes(),
            declared_document_type=DocumentType.unknown,
            gemma_client=GemmaReasoningClient(Settings(gemma_enabled=False)),
            source_path=source_path,
            ocr_provider=ConflictingNicAsbaProvider(),
        )

    document, fields, _findings = asyncio.run(run())
    extracted = {field.key: field.value for field in fields}

    assert document.document_type == DocumentType.asba_application
    assert extracted["applicant_name"] == "Np: कृष्णमान ट्वुवा"
    assert extracted["client_id"] == "146942086"
    assert extracted["mobile"] == "9805825464"
    assert extracted["amount"] == "9280"
    assert extracted["applied_units"] == "22300"
