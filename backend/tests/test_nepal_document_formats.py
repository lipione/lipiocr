from importlib import reload
from pathlib import Path
import asyncio

from app.models import CaseType, DocumentType, FinancialDocument
import app.services.templates as templates_module
from app.core.config import Settings
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
        "citizenship": {"name", "dob", "citizenship_number", "address", "father_mother_name"},
        "national_id": {"national_id_number", "full_name", "dob", "gender", "issue_date"},
        "passport": {"passport_number", "surname", "given_name", "nationality", "dob", "expiry_date", "mrz_line_1"},
        "driving_license": {"license_number", "full_name", "blood_group", "dob", "citizenship_number", "category"},
        "ipo_application": {"company_name", "application_number", "applicant_name", "applied_units", "amount", "boid"},
        "asba_application": {"bank_name", "applicant_name", "dp_id", "client_id", "account_number", "amount"},
    }

    for document_type, field_keys in expected_fields.items():
        assert document_type in templates
        configured = {field.key for field in templates[document_type].fields}
        assert field_keys.issubset(configured)


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
