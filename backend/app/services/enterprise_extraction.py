import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

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
from app.services.calendar_intelligence import apply_calendar_intelligence
from app.services.document_intelligence import apply_document_intelligence
from app.services.gemma import GemmaExtractionResult, GemmaReasoningClient
from app.services.validation import validate_field


DEVANAGARI_DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९", "0123456789")
DATE_VALUE_PATTERN = r"(\d{2,4}[-\/.]\d{1,2}[-\/.]\d{1,2})"
IDENTIFIER_VALUE_PATTERN = r"([\w\-\/]+)"
GENERIC_LABEL_VALUE_PATTERNS = (
    re.compile(r"^\s*(?P<label>[^:：]{2,96})\s*[:：]\s*(?P<value>.{1,240})\s*$"),
    re.compile(
        r"^\s*(?P<label>[^\n._:：]{2,96}?)\s*(?:\.{2,}|_{2,}|[-–—]{1})\s*(?P<value>.{1,240})\s*$"
    ),
)
GENERIC_FIELD_ALIASES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("full_name_np", "Full Name (Nepali)", ("नाम थर", "आवेदकको नाम")),
    ("full_name_en", "Full Name (English)", ("full name", "customer name", "name")),
    ("applicant_name", "Applicant Name", ("applicant name", "applicant's full name")),
    ("father_name_np", "Father Name (Nepali)", ("बाबुको नाम", "बुबाको नाम", "पिताको नाम")),
    ("father_name_en", "Father Name (English)", ("father name", "father's name")),
    ("mother_name_np", "Mother Name (Nepali)", ("आमाको नाम", "माताको नाम")),
    ("mother_name_en", "Mother Name (English)", ("mother name", "mother's name")),
    ("address_np", "Address (Nepali)", ("ठेगाना", "स्थायी वासस्थान", "स्थायी ठेगाना")),
    ("address_en", "Address (English)", ("address", "permanent address", "current address")),
    ("dob_bs", "Date of Birth (BS)", ("जन्म मिति",)),
    ("dob_ad", "Date of Birth (AD)", ("date of birth", "dob", "d.o.b")),
    ("issue_date_bs", "Date of Issue (BS)", ("जारी मिति",)),
    ("issue_date_ad", "Date of Issue (AD)", ("date of issue", "issue date")),
    ("citizenship_number", "Citizenship Number", ("citizenship no", "citizenship number", "ना.प्र.नं", "ना प्र नं")),
    ("national_id_number", "National ID Number", ("national id no", "national id number", "परिचयपत्र नं")),
    ("passport_number", "Passport Number", ("passport no", "passport number")),
    ("license_number", "License Number", ("d.l.no", "dl no", "license no", "license number")),
    ("mobile", "Mobile Number", ("mobile no", "mobile", "phone no", "contact no", "सम्पर्क फोन नं")),
    ("email", "Email", ("email", "e-mail", "इमेल")),
    ("account_number", "Account Number", ("bank account no", "account no", "account number", "खाता नम्बर")),
    ("requested_amount", "Requested Amount", ("requested amount", "loan amount", "amount requested")),
    ("amount", "Amount", ("amount", "amount deposited", "total amount", "रकम")),
    ("dp_id", "DP ID", ("dp id", "depository participant id")),
    ("client_id", "Client ID", ("client id", "client no")),
    ("boid", "BOID", ("boid", "bo id", "demat no", "beneficiary id")),
)


def _pages_from_text_lines(lines: List[Sequence[object]], filename: str) -> List[OcrPage]:
    if not lines:
        lines = [(f"Uploaded scanned document: {filename}. Full OCR pending for binary page image.", 0.40)]

    blocks: List[OcrBlock] = []
    for index, line_item in enumerate(lines, start=1):
        line = str(line_item[0])
        confidence = float(line_item[1])
        block_type = str(line_item[2]) if len(line_item) > 2 else "text"
        language = str(line_item[3]) if len(line_item) > 3 else "mixed"
        bbox = line_item[4] if len(line_item) > 4 else None
        y1 = 100 + (index - 1) * 48
        blocks.append(
            OcrBlock(
                text=line,
                bbox=bbox if isinstance(bbox, list) else [80, y1, 920, y1 + 34],
                confidence=round(float(confidence), 2),
                block_type=block_type,
                language=language,
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
            block_type = str(observation.get("block_type") or "text")
            language = str(observation.get("language") or "mixed")
            bbox = observation.get("bbox")
            for raw_line in text_value.splitlines() or [text_value]:
                line_value = raw_line.strip()
                if not line_value:
                    continue
                if field_key and field_key != "raw_text":
                    label = field_key.replace("_", " ").title()
                    line_value = f"{label}: {line_value}"
                lines.append((line_value, float(observation.get("confidence") or 0.50), block_type, language, bbox))
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
    return re.sub(r"\s+", " ", value.strip().strip(":-|,;")).translate(DEVANAGARI_DIGIT_TRANSLATION)


def _normalize_generic_label(label: str) -> str:
    normalized = _clean_value(label).lower()
    normalized = re.sub(r"[#().,/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _canonical_generic_field(label: str) -> Optional[tuple[str, str]]:
    normalized_label = _normalize_generic_label(label)
    if not normalized_label:
        return None

    scored: list[tuple[int, str, str]] = []
    for key, display_label, aliases in GENERIC_FIELD_ALIASES:
        for alias in aliases:
            normalized_alias = _normalize_generic_label(alias)
            if normalized_label == normalized_alias:
                scored.append((100 + len(normalized_alias), key, display_label))
            elif normalized_alias and normalized_alias in normalized_label:
                scored.append((50 + len(normalized_alias), key, display_label))

    if not scored:
        return None
    _, key, display_label = max(scored, key=lambda item: item[0])
    return key, display_label


def _known_prefix_label_value(line: str) -> Optional[tuple[str, str, str, str]]:
    alias_rows = sorted(
        (
            (alias, key, display_label)
            for key, display_label, aliases in GENERIC_FIELD_ALIASES
            for alias in aliases
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, key, display_label in alias_rows:
        pattern = re.compile(
            rf"^\s*(?P<label>{re.escape(alias)})\s*(?:[:：#.\-–—_]+|\s+)(?P<value>.{{1,240}})\s*$",
            flags=0 if re.search(r"[\u0900-\u097F]", alias) else re.IGNORECASE,
        )
        match = pattern.match(line)
        if not match:
            continue
        value = _clean_value(match.group("value"))
        if value:
            return match.group("label").strip(), value, key, display_label
    return None


def _parse_generic_label_value(line: str) -> Optional[tuple[str, str, Optional[str], Optional[str]]]:
    for pattern in GENERIC_LABEL_VALUE_PATTERNS:
        match = pattern.match(line)
        if not match:
            continue
        label = _clean_value(match.group("label"))
        value = _clean_value(match.group("value"))
        if not label or not value:
            continue
        canonical = _canonical_generic_field(label)
        if canonical:
            key, display_label = canonical
            return label, value, key, display_label
        return label, value, None, None

    known = _known_prefix_label_value(line)
    if known:
        label, value, key, display_label = known
        return label, value, key, display_label
    return None


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
        if normalized_value in line.lower() or normalized_value in _clean_value(line).lower():
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


def _normalized_ocr_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def _ocr_line_label(line: str, index: int) -> str:
    label_candidate = re.split(r"[:：]", line, maxsplit=1)[0].strip()
    if label_candidate and label_candidate != line and len(label_candidate) <= 64:
        return _clean_value(label_candidate)
    return f"OCR Line {index:03d}"


def _append_full_page_ocr_fields(
    *,
    fields: List[ExtractedField],
    pages: List[OcrPage],
    document_id: str,
) -> None:
    seen: set[str] = set()
    line_index = 1
    for page in pages:
        for block in page.blocks:
            for raw_line in block.text.splitlines():
                line = raw_line.strip()
                normalized = _normalized_ocr_line(line)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                is_handwriting = block.block_type == "handwriting"
                fields.append(
                    ExtractedField(
                        key=f"ocr_line_{line_index:03d}",
                        label=_ocr_line_label(line, line_index),
                        value=line,
                        confidence=round(float(block.confidence), 2),
                        required=False,
                        source="handwriting_ocr" if is_handwriting else "full_page_ocr",
                        validation_status=ValidationStatus.warning,
                        validation_message=(
                            "Handwritten OCR text retained for reviewer/template mapping."
                            if is_handwriting
                            else "Full-page OCR text retained for reviewer/template mapping."
                        ),
                        bbox=block.bbox,
                        evidence=EvidenceRef(
                            document_id=document_id,
                            source_page=page.page_number,
                            bbox=block.bbox,
                            evidence_text=line,
                        ),
                        extracted_by="full-page-ocr",
                        document_id=document_id,
                    )
                )
                line_index += 1


def _generic_field_key(label: str, fallback_index: int) -> str:
    canonical = _canonical_generic_field(label)
    if canonical:
        return canonical[0]
    key = _clean_value(label).lower()
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key[:64] or f"generic_field_{fallback_index:03d}"


def _append_generic_label_value_fields(
    *,
    fields: List[ExtractedField],
    pages: List[OcrPage],
    document_id: str,
) -> None:
    existing_keys = {field.key for field in fields}
    used_keys = set(existing_keys)
    generic_index = 1

    for page in pages:
        for block in page.blocks:
            for raw_line in block.text.splitlines():
                line = raw_line.strip()
                parsed = _parse_generic_label_value(line)
                if not parsed:
                    continue

                label, value, canonical_key, canonical_label = parsed
                if not label or not value:
                    continue

                base_key = canonical_key or _generic_field_key(label, generic_index)
                if base_key in existing_keys or base_key.startswith("ocr_line_"):
                    continue

                key = base_key
                suffix = 2
                while key in used_keys:
                    key = f"{base_key}_{suffix}"
                    suffix += 1
                used_keys.add(key)

                validation = validate_field(key, value, "unknown")
                fields.append(
                    ExtractedField(
                        key=key,
                        label=canonical_label or label,
                        value=value,
                        confidence=round(min(0.74, float(block.confidence)), 2),
                        required=False,
                        source="generic_field_extraction",
                        validation_status=ValidationStatus(validation["status"]),
                        validation_message=validation["message"],
                        bbox=block.bbox,
                        evidence=EvidenceRef(
                            document_id=document_id,
                            source_page=page.page_number,
                            bbox=block.bbox,
                            evidence_text=line,
                        ),
                        extracted_by="LipiCore",
                        document_id=document_id,
                    )
                )
                generic_index += 1


FieldSpec = tuple[str, str, tuple[str, ...], bool]


FIELD_SPECS: dict[DocumentType, tuple[FieldSpec, ...]] = {
    DocumentType.citizenship: (
        ("full_name", "Full Name", (r"^\s*(?:Name|नाम(?:\s*थर)?)\s*[:\-]?\s*([^\n]+)",), True),
        (
            "citizenship_number",
            "Citizenship Number",
            (rf"^\s*(?:Citizenship\s*(?:No|Number)|Ctz\.?\s*No|ना\.?\s*प्र\.?\s*नं\.?)\s*[:#.\-]*\s*{IDENTIFIER_VALUE_PATTERN}",),
            True,
        ),
        ("dob", "Date of Birth", (rf"^\s*(?:Date of Birth|DOB|D\.O\.B\.|जन्म मिति)\s*[:.\-]*\s*{DATE_VALUE_PATTERN}",), True),
        ("address", "Address", (r"^\s*(?:Address|Permanent Address|ठेगाना|स्थायी वासस्थान)\s*[:\-]?\s*([^\n]+)",), True),
        ("father_mother_name", "Father/Mother Name", (r"^\s*(?:Father/Mother Name|Father Name|Mother Name|बाबुको नाम थर|आमाको नाम थर|बाबु|आमा)\s*[:\-]?\s*([^\n]+)",), False),
    ),
    DocumentType.national_id: (
        (
            "national_id_number",
            "National ID Number",
            (rf"^\s*(?:National ID No|National ID Number|NIN|ID No|परिचयपत्र नं)\s*[:#.\-]*\s*{IDENTIFIER_VALUE_PATTERN}",),
            True,
        ),
        ("full_name", "Full Name", (r"^\s*(?:Name|Full Name|Given Name|नाम थर)\s*[:\-]?\s*([^\n]+)",), True),
        ("gender", "Gender", (r"^\s*(?:Sex|Gender)\s*[:\-]?\s*([A-Za-z]+)",), True),
        ("dob", "Date of Birth", (rf"^\s*(?:Date of Birth|DOB|जन्म मिति)\s*[:.\-]*\s*{DATE_VALUE_PATTERN}",), True),
        ("issue_date", "Date of Issue", (rf"^\s*(?:Date of Issue|Issue Date|जारी मिति)\s*[:.\-]*\s*{DATE_VALUE_PATTERN}",), False),
        ("mother_name", "Mother Name", (r"^\s*(?:Mother's Name|Mother Name|आमाको नाम)\s*[:\-]?\s*([^\n]+)",), False),
        ("father_name", "Father Name", (r"^\s*(?:Father's Name|Father Name|बाबुको नाम)\s*[:\-]?\s*([^\n]+)",), False),
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

    if inferred_type == DocumentType.unknown or not fields:
        _append_generic_label_value_fields(fields=fields, pages=document.pages, document_id=document.id)

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

    _append_full_page_ocr_fields(fields=fields, pages=document.pages, document_id=document.id)

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
        summary=f"Processed {inferred_type.value} for Nepal financial KYC with full-page OCR evidence.",
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
                code="lipicore_unavailable",
                message=f"LipiCore extraction fell back to deterministic extraction: {exc}",
                document_id=document.id,
            )
        )

    if result is None:
        result = fallback_extraction(
            case_type=case_type,
            declared_document_type=declared_document_type,
            document=document,
        )

    if not any(field.source in {"full_page_ocr", "handwriting_ocr"} for field in result.fields):
        _append_full_page_ocr_fields(fields=result.fields, pages=document.pages, document_id=document.id)

    document.document_type = result.document_type
    document.summary = result.summary
    document.status = DocumentStatus.processed

    for field in result.fields:
        field.document_id = document.id
        field.extracted_by = field.extracted_by or "LipiCore"
        field.evidence.document_id = document.id
        if field.source not in {"full_page_ocr", "handwriting_ocr"}:
            validation = validate_field(field.key, field.value, result.document_type.value)
            field.validation_status = ValidationStatus(validation["status"])
            field.validation_message = validation["message"]
        if field.evidence.bbox and not field.bbox:
            field.bbox = field.evidence.bbox

    apply_document_intelligence(document, result.fields)
    apply_calendar_intelligence(result.fields, document_id=document.id)

    for finding in result.findings:
        finding.document_id = finding.document_id or document.id

    return document, result.fields, result.findings
