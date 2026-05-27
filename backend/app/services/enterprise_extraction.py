import re
from pathlib import Path
from typing import Iterable, List, Optional

from app.models import (
    CaseType,
    DocumentStatus,
    DocumentType,
    EvidenceRef,
    ExtractedField,
    FinancialDocument,
    OcrBlock,
    OcrPage,
    ValidationFinding,
    ValidationStatus,
)
from app.services.gemma import GemmaExtractionResult, GemmaReasoningClient
from app.services.validation import validate_field


def _pages_from_text_lines(lines: List[tuple[str, float]], filename: str) -> List[OcrPage]:
    if not lines:
        lines = [(f"Uploaded scanned document: {filename}. Full OCR pending for binary page image.", 0.40)]

    blocks: List[OcrBlock] = []
    for index, (line, confidence) in enumerate(lines, start=1):
        y1 = 100 + (index - 1) * 48
        blocks.append(
            OcrBlock(
                text=line,
                bbox=[80, y1, 920, y1 + 34],
                confidence=round(float(confidence), 2),
                block_type="text",
            )
        )

    confidence = round(sum(block.confidence for block in blocks) / len(blocks), 2)
    return [OcrPage(page_number=1, width=1000, height=1400, blocks=blocks, ocr_confidence=confidence)]


def build_pages_from_upload(
    content: bytes,
    filename: str,
    *,
    ocr_provider=None,
    source_path: Optional[Path] = None,
    document_type: DocumentType = DocumentType.unknown,
) -> List[OcrPage]:
    try:
        text = content.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""

    if text:
        lines = [(line.strip(), 0.88 if index == 0 else 0.82) for index, line in enumerate(text.splitlines()) if line.strip()]
        return _pages_from_text_lines(lines, filename)

    if ocr_provider is not None and source_path is not None:
        observations = ocr_provider.read(source_path, document_type)
        lines = []
        for observation in observations:
            text_value = str(observation.get("text") or "").strip()
            if not text_value:
                continue
            field_key = str(observation.get("field_key") or "").strip()
            if field_key and field_key != "raw_text":
                label = field_key.replace("_", " ").title()
                text_value = f"{label}: {text_value}"
            lines.append((text_value, float(observation.get("confidence") or 0.50)))
        if lines:
            return _pages_from_text_lines(lines, filename)

    return _pages_from_text_lines([], filename)


def _all_text(pages: Iterable[OcrPage]) -> str:
    return "\n".join(block.text for page in pages for block in page.blocks)


def _first_bbox(pages: List[OcrPage]) -> List[int]:
    if pages and pages[0].blocks:
        return pages[0].blocks[0].bbox
    return [80, 100, 920, 134]


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip(":-|,;"))


def _match_value(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return _clean_value(match.group(1))
    return ""


def _evidence_line(text: str, value: str, fallback: str) -> str:
    if not value:
        return fallback
    normalized_value = value.lower()
    for line in text.splitlines():
        if normalized_value in line.lower():
            return line.strip()
    return fallback


def _first_matching_line(text: str, *keywords: str) -> str:
    for line in text.splitlines():
        clean = _clean_value(line)
        lower = clean.lower()
        if clean and any(keyword.lower() in lower for keyword in keywords):
            return clean
    return ""


def _infer_document_type(text: str, declared_document_type: DocumentType) -> DocumentType:
    if declared_document_type != DocumentType.unknown:
        return declared_document_type

    lower = text.lower()
    signals: list[tuple[DocumentType, tuple[str, ...]]] = [
        (
            DocumentType.asba_application,
            (
                "asba",
                "c-asba",
                "हितोपत्र खरिद",
                "हितोपत्र खरीद",
                "dp id",
                "client id",
                "boid",
                "demat",
                "nic asia",
                "nmb bank",
            ),
        ),
        (
            DocumentType.ipo_application,
            (
                "share application",
                "ipo application",
                "application no",
                "share applied",
                "capital market",
                "kisan micro finance",
            ),
        ),
        (DocumentType.national_id, ("national identity", "national id", "identity card", "परिचयपत्र")),
        (DocumentType.passport, ("passport", "p<npl", "mrp", "travel document")),
        (DocumentType.driving_license, ("driving license", "driving licence", "d.l.no", "license office")),
        (DocumentType.citizenship, ("citizenship", "citizenship no", "नागरिकताको", "ना.प्र")),
        (DocumentType.pan, ("pan", "permanent account number")),
        (DocumentType.cheque, ("cheque", "check no", "payee", "account payee")),
        (DocumentType.company_registration, ("company registration", "office of company registrar")),
    ]

    scored = [
        (document_type, sum(1 for keyword in keywords if keyword in lower))
        for document_type, keywords in signals
    ]
    predicted, score = max(scored, key=lambda item: item[1])
    return predicted if score else DocumentType.unknown


def _field(
    *,
    key: str,
    label: str,
    value: str,
    confidence: float,
    evidence_text: str,
    bbox: List[int],
    document_id: str,
    required: bool = True,
) -> ExtractedField:
    validation = validate_field(key, value, "enterprise_kyc")
    return ExtractedField(
        key=key,
        label=label,
        value=value,
        confidence=confidence,
        required=required,
        source="deterministic_fallback",
        validation_status=ValidationStatus(validation["status"]),
        validation_message=validation["message"],
        bbox=bbox,
        evidence=EvidenceRef(
            document_id=document_id,
            source_page=1,
            bbox=bbox,
            evidence_text=evidence_text,
        ),
        extracted_by="deterministic-fallback",
        document_id=document_id,
    )


FieldSpec = tuple[str, str, tuple[str, ...], bool]


FIELD_SPECS: dict[DocumentType, tuple[FieldSpec, ...]] = {
    DocumentType.citizenship: (
        ("full_name", "Full Name", (r"^\s*(?:Name|नाम(?:\s*थर)?)\s*[:\-]?\s*([^\n]+)",), True),
        (
            "citizenship_number",
            "Citizenship Number",
            (r"^\s*(?:Citizenship\s*(?:No|Number)|Ctz\.?\s*No|ना\.?\s*प्र\.?\s*नं\.?)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",),
            True,
        ),
        ("dob", "Date of Birth", (r"^\s*(?:Date of Birth|DOB|D\.O\.B\.|जन्म मिति)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), True),
        ("address", "Address", (r"^\s*(?:Address|Permanent Address|ठेगाना)\s*[:\-]?\s*([^\n]+)",), True),
        ("father_mother_name", "Father/Mother Name", (r"^\s*(?:Father/Mother Name|Father Name|Mother Name|बाबु|आमा)\s*[:\-]?\s*([^\n]+)",), False),
    ),
    DocumentType.national_id: (
        (
            "national_id_number",
            "National ID Number",
            (r"^\s*(?:National ID No|National ID Number|NIN|ID No)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",),
            True,
        ),
        ("full_name", "Full Name", (r"^\s*(?:Name|Full Name|Given Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("gender", "Gender", (r"^\s*(?:Sex|Gender)\s*[:\-]?\s*([A-Za-z]+)",), True),
        ("dob", "Date of Birth", (r"^\s*(?:Date of Birth|DOB)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), True),
        ("issue_date", "Date of Issue", (r"^\s*(?:Date of Issue|Issue Date)\s*[:.\-]*\s*([0-9]{2,4}[-\/][0-9]{2}[-\/][0-9]{2,4})",), False),
        ("mother_name", "Mother Name", (r"^\s*(?:Mother's Name|Mother Name)\s*[:\-]?\s*([^\n]+)",), False),
        ("father_name", "Father Name", (r"^\s*(?:Father's Name|Father Name)\s*[:\-]?\s*([^\n]+)",), False),
    ),
    DocumentType.passport: (
        ("passport_number", "Passport Number", (r"^\s*(?:Passport No|Passport Number)\s*[:#.\-]*\s*([A-Za-z0-9]+)",), True),
        ("surname", "Surname", (r"^\s*(?:Surname|Family Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("given_name", "Given Name", (r"^\s*(?:Given Name|Given Names)\s*[:\-]?\s*([^\n]+)",), True),
        ("nationality", "Nationality", (r"^\s*(?:Nationality)\s*[:\-]?\s*([^\n]+)",), True),
        ("dob", "Date of Birth", (r"^\s*(?:Date of Birth|DOB)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), True),
        ("issue_date", "Date of Issue", (r"^\s*(?:Date of Issue|Issue Date)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), False),
        ("expiry_date", "Date of Expiry", (r"^\s*(?:Date of Expiry|Expiry Date)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), True),
        ("citizenship_number", "Citizenship Number", (r"^\s*(?:Citizenship No|Citizenship Number)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), False),
        ("mrz_line_1", "MRZ Line 1", (r"^\s*(P<[A-Z0-9<]+)",), True),
        ("mrz_line_2", "MRZ Line 2", (r"^\s*([A-Z0-9<]{30,})$",), False),
    ),
    DocumentType.driving_license: (
        ("license_number", "License Number", (r"^\s*(?:D\.?\s*L\.?\s*No\.?|DL No|License No|License Number)\s*[:.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("full_name", "Full Name", (r"^\s*(?:Name|Full Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("blood_group", "Blood Group", (r"^\s*(?:B\.?\s*G\.?|Blood Group)\s*[:.\-]*\s*([A-Za-z0-9+\-]+)",), False),
        ("address", "Address", (r"^\s*(?:Address)\s*[:\-]?\s*([^\n]+)",), True),
        ("dob", "Date of Birth", (r"^\s*(?:D\.?\s*O\.?\s*B\.?|DOB|Date of Birth)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), True),
        ("issue_date", "Date of Issue", (r"^\s*(?:D\.?\s*O\.?\s*I\.?|Date of Issue|Issue Date)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), False),
        ("expiry_date", "Date of Expiry", (r"^\s*(?:D\.?\s*O\.?\s*E\.?|Date of Expiry|Expiry Date)\s*[:.\-]*\s*([0-9]{4}[-\/][0-9]{2}[-\/][0-9]{2})",), False),
        ("citizenship_number", "Citizenship Number", (r"^\s*(?:Citizenship No|Citizenship Number)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("category", "Category", (r"^\s*(?:Category)\s*[:\-]?\s*([A-Za-z0-9]+)",), True),
        ("phone", "Phone Number", (r"^\s*(?:Phone No|Phone Number)\s*[:.\-]*\s*(9[0-9]{9})",), False),
    ),
    DocumentType.ipo_application: (
        ("application_number", "Application Number", (r"^\s*(?:Application No|Form No|Serial No)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("applicant_name", "Applicant Name", (r"^\s*(?:Applicant Name|Applicant's Name|Applicant's Full Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("applied_units", "Applied Units", (r"^\s*(?:No\.?\s*of\s*Share\s*Applied|Applied Units|Kitta)\s*[:.\-]*\s*([0-9]+)",), True),
        ("amount", "Amount", (r"^\s*(?:Amount Deposited|Amount|Total Amount)\s*[:.\-]*\s*(?:Rs\.?\s*)?([0-9]+(?:\.[0-9]{1,2})?)",), True),
        ("boid", "BOID", (r"^\s*(?:BOID|BO ID|Demat No|Beneficiary ID)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("bank_name", "Bank Name", (r"^\s*(?:Bank Name)\s*[:\-]?\s*([^\n]+)",), False),
        ("account_number", "Bank Account Number", (r"^\s*(?:Account No|Bank Account No|Account Number)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), False),
        ("mobile", "Mobile Number", (r"^\s*(?:Mobile|Mobile No|Contact No)\s*[:.\-]*\s*(9[0-9]{9})",), False),
        ("father_name", "Father Name", (r"^\s*(?:Father's Name|Father Name)\s*[:\-]?\s*([^\n]+)",), False),
        ("grandfather_name", "Grandfather Name", (r"^\s*(?:Grandfather's Name|Grandfather Name)\s*[:\-]?\s*([^\n]+)",), False),
    ),
    DocumentType.asba_application: (
        ("bank_name", "Bank Name", (r"^\s*(?:Bank Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("applicant_name", "Applicant Name", (r"^\s*(?:Applicant Name|Applicant's Name|Applicant's Full Name)\s*[:\-]?\s*([^\n]+)",), True),
        ("dp_id", "DP ID", (r"^\s*(?:DP ID|Depository Participant ID)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("client_id", "Client ID", (r"^\s*(?:Client ID|Client No)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("account_number", "Bank Account Number", (r"^\s*(?:Bank Account No|Account No|Account Number)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), True),
        ("amount", "Amount", (r"^\s*(?:Amount Deposited|Amount|Total Amount)\s*[:.\-]*\s*(?:Rs\.?\s*)?([0-9]+(?:\.[0-9]{1,2})?)",), True),
        ("applied_units", "Applied Units", (r"^\s*(?:Applied Units|No\.?\s*of\s*Share\s*Applied|Kitta)\s*[:.\-]*\s*([0-9]+)",), True),
        ("company_name", "Issue Manager / Company", (r"^\s*(?:Company Name|Issue Manager|Issue)\s*[:\-]?\s*([^\n]+)",), False),
        ("boid", "BOID", (r"^\s*(?:BOID|BO ID|Demat No|Beneficiary ID)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), False),
        ("mobile", "Mobile Number", (r"^\s*(?:Mobile|Mobile No|Contact No)\s*[:.\-]*\s*(9[0-9]{9})",), False),
        ("email", "Email", (r"^\s*(?:Email|E-mail)\s*[:.\-]*\s*([^@\s]+@[^@\s]+\.[^@\s]+)",), False),
        ("citizenship_number", "Citizenship Number", (r"^\s*(?:Citizenship No|Citizenship Number)\s*[:#.\-]*\s*([A-Za-z0-9\-\/]+)",), False),
    ),
}


def _add_detected_fields(
    *,
    fields: List[ExtractedField],
    document_type: DocumentType,
    text: str,
    bbox: List[int],
    document_id: str,
) -> None:
    for key, label, patterns, required in FIELD_SPECS.get(document_type, ()):
        value = _match_value(text, patterns)
        if value:
            fields.append(
                _field(
                    key=key,
                    label=label,
                    value=value,
                    confidence=0.86 if required else 0.78,
                    evidence_text=_evidence_line(text, value, label),
                    bbox=bbox,
                    document_id=document_id,
                    required=required,
                )
            )

    if document_type == DocumentType.ipo_application and not any(field.key == "company_name" for field in fields):
        company = _first_matching_line(text, "limited", "ltd", "sanstha", "finance")
        if company:
            fields.append(
                _field(
                    key="company_name",
                    label="Company Name",
                    value=company,
                    confidence=0.82,
                    evidence_text=company,
                    bbox=bbox,
                    document_id=document_id,
                )
            )

    if document_type == DocumentType.asba_application and not any(field.key == "bank_name" for field in fields):
        bank = _first_matching_line(text, "bank")
        if bank:
            fields.append(
                _field(
                    key="bank_name",
                    label="Bank Name",
                    value=bank,
                    confidence=0.84,
                    evidence_text=bank,
                    bbox=bbox,
                    document_id=document_id,
                )
            )


def fallback_extraction(
    *,
    case_type: CaseType,
    declared_document_type: DocumentType,
    document: FinancialDocument,
) -> GemmaExtractionResult:
    text = _all_text(document.pages)
    bbox = _first_bbox(document.pages)
    inferred_type = _infer_document_type(text, declared_document_type)
    fields: List[ExtractedField] = []

    _add_detected_fields(
        fields=fields,
        document_type=inferred_type,
        text=text,
        bbox=bbox,
        document_id=document.id,
    )

    has_full_name = any(field.key in {"full_name", "applicant_name"} and field.value for field in fields)
    if case_type == CaseType.individual_kyc and not has_full_name:
        fields.append(
            _field(
                key="full_name",
                label="Full Name",
                value="",
                confidence=0.20,
                evidence_text="Name not confidently detected",
                bbox=bbox,
                document_id=document.id,
            )
        )

    findings = [
        ValidationFinding(
            severity="warning",
            code="human_review_required",
            message="AI extraction requires maker-checker review before export.",
            document_id=document.id,
        )
    ]
    return GemmaExtractionResult(
        document_type=inferred_type,
        summary=f"Processed {inferred_type.value} for Nepal financial KYC.",
        fields=fields,
        findings=findings,
    )


async def process_enterprise_document(
    *,
    case_type: CaseType,
    filename: str,
    content: bytes,
    declared_document_type: DocumentType,
    gemma_client: GemmaReasoningClient,
    source_path: Optional[Path] = None,
    ocr_provider=None,
) -> tuple[FinancialDocument, List[ExtractedField], List[ValidationFinding]]:
    document = FinancialDocument(
        filename=filename,
        declared_document_type=declared_document_type,
        document_type=declared_document_type,
        status=DocumentStatus.uploaded,
        pages=build_pages_from_upload(
            content,
            filename,
            ocr_provider=ocr_provider,
            source_path=source_path,
            document_type=declared_document_type,
        ),
    )
    document.page_count = len(document.pages)

    try:
        result = await gemma_client.extract(
            case_type=case_type,
            expected_document_type=declared_document_type,
            pages=document.pages,
        )
    except Exception as exc:
        result = fallback_extraction(
            case_type=case_type,
            declared_document_type=declared_document_type,
            document=document,
        )
        result.findings.append(
            ValidationFinding(
                severity="warning",
                code="gemma_unavailable",
                message=f"Gemma 4 26B extraction fell back to deterministic extraction: {exc}",
                document_id=document.id,
            )
        )

    if result is None:
        result = fallback_extraction(
            case_type=case_type,
            declared_document_type=declared_document_type,
            document=document,
        )

    document.document_type = result.document_type
    document.summary = result.summary
    document.status = DocumentStatus.processed

    for field in result.fields:
        field.document_id = document.id
        field.extracted_by = field.extracted_by or gemma_client.settings.gemma_model
        field.evidence.document_id = document.id
        validation = validate_field(field.key, field.value, result.document_type.value)
        field.validation_status = ValidationStatus(validation["status"])
        field.validation_message = validation["message"]
        if field.evidence.bbox and not field.bbox:
            field.bbox = field.evidence.bbox

    for finding in result.findings:
        finding.document_id = finding.document_id or document.id

    return document, result.fields, result.findings
