from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Optional

import nepali_datetime

from app.models import (
    DocumentAsset,
    DocumentSection,
    DocumentType,
    EvidenceLedgerEntry,
    EvidenceRef,
    ExtractedField,
    FinancialDocument,
    KycCase,
    OcrBlock,
    ReviewStatus,
    ValidationStatus,
)
from app.services.address_intelligence import is_address_field_key, suggest_address_corrections
from app.services.calendar_intelligence import CalendarConversion, convert_calendar_date, normalize_nepali_digits
from app.services.nepal_locations import resolve_nepal_location
from app.services.nepali_name_lexicon import suggest_name_corrections
from app.services.validation import validate_field


DEVANAGARI_TEXT_RE = re.compile(r"[\u0900-\u097F]")
LABEL_VALUE_RE = re.compile(r"^\s*(?P<label>[^:：]{1,96})\s*[:：]\s*(?P<value>.+?)\s*$")

MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


DOCUMENT_SIGNALS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.citizenship: (
        "citizenship",
        "citizenship no",
        "government of nepal",
        "nepali nagarikta",
        "नागरिकताको",
        "नागरिकता",
        "ना.प्र",
        "जिल्ला प्रशासन",
    ),
    DocumentType.national_id: (
        "national identity",
        "national id",
        "identity card",
        "परिचयपत्र",
        "राष्ट्रिय परिचयपत्र",
    ),
    DocumentType.passport: ("passport", "p<npl", "mrz", "travel document", "राहदानी"),
    DocumentType.driving_license: ("driving license", "driving licence", "d.l.no", "license office", "सवारी चालक"),
    DocumentType.account_opening: ("account opening", "account type", "nominee", "kyc form"),
    DocumentType.ipo_application: (
        "share application",
        "ipo application",
        "share applied",
        "capital market",
        "दरखास्त फाराम",
    ),
    DocumentType.asba_application: (
        "asba",
        "c-asba",
        "हितोपत्र खरिद",
        "हितोपत्र खरीद",
        "dp id",
        "client id",
        "boid",
        "demat",
    ),
    DocumentType.pan: ("pan", "permanent account number", "taxpayer", "स्थायी लेखा"),
    DocumentType.vat: ("vat", "value added tax", "मूल्य अभिवृद्धि"),
    DocumentType.cheque: ("cheque", "account payee", "payee", "rupees", "चेक"),
    DocumentType.bank_statement: ("statement", "debit", "credit", "balance", "transaction"),
    DocumentType.company_registration: ("company registrar", "company registration", "pvt", "limited", "कम्पनी"),
    DocumentType.board_resolution: ("board resolution", "resolved that", "authorized signatory", "minute"),
    DocumentType.tax_clearance: ("tax clearance", "clearance certificate", "ird"),
}


DOCUMENT_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "key": "citizenship_old_district_certificate",
        "label": "Nepal Citizenship Certificate (Old District Format)",
        "document_type": DocumentType.citizenship,
        "version_family": "old_district_certificate",
        "signals": (
            "जिल्ला प्रशासन",
            "नेपाली नागरिकताको प्रमाणपत्र",
            "ना.प्र",
            "नाम थर",
            "बाबुको नाम",
            "आमाको नाम",
        ),
    },
    {
        "key": "citizenship_new_certificate",
        "label": "Nepal Citizenship Certificate (New Format)",
        "document_type": DocumentType.citizenship,
        "version_family": "new_certificate",
        "signals": (
            "government of nepal",
            "ministry of home affairs",
            "citizenship certificate",
            "citizenship number",
            "date of birth",
        ),
    },
    {
        "key": "national_id_smart_card",
        "label": "Nepal National Identity Card",
        "document_type": DocumentType.national_id,
        "version_family": "smart_card",
        "signals": (
            "national identity card",
            "government of nepal",
            "परिचयपत्र",
            "date of birth",
            "given name",
        ),
    },
    {
        "key": "passport_mrp",
        "label": "Nepal Machine Readable Passport",
        "document_type": DocumentType.passport,
        "version_family": "mrp",
        "signals": ("passport", "p<npl", "mrz", "issuing authority", "date of expiry"),
    },
    {
        "key": "driving_license_smart_card",
        "label": "Nepal Smart Driving License",
        "document_type": DocumentType.driving_license,
        "version_family": "smart_card",
        "signals": ("driving license", "d.l.no", "license office", "category", "citizenship no"),
    },
    {
        "key": "asba_application_form",
        "label": "Nepal ASBA / IPO Application Form",
        "document_type": DocumentType.asba_application,
        "version_family": "financial_form",
        "signals": ("हितोपत्र खरिद", "dp id", "client id", "boid", "amount deposited", "demat"),
    },
    {
        "key": "ipo_application_form",
        "label": "Nepal IPO Application Form",
        "document_type": DocumentType.ipo_application,
        "version_family": "financial_form",
        "signals": ("share application", "share applied", "capital market", "amount deposited", "kisan micro finance"),
    },
)


DOCUMENT_SIDE_SIGNALS: dict[DocumentType, dict[str, tuple[str, ...]]] = {
    DocumentType.citizenship: {
        "front": (
            "नेपाली नागरिकताको प्रमाणपत्र",
            "citizenship certificate",
            "नाम थर",
            "name",
            "ना.प्र",
            "citizenship no",
            "जन्म मिति",
            "date of birth",
            "photo",
            "फोटो",
        ),
        "back": (
            "बाबुको नाम",
            "बुबाको नाम",
            "आमाको नाम",
            "पतिको नाम",
            "पत्नीको नाम",
            "स्थायी वासस्थान",
            "स्थायी ठेगाना",
            "जारी मिति",
            "father",
            "mother",
            "permanent address",
            "date of issue",
            "signature",
            "हस्ताक्षर",
        ),
    },
    DocumentType.national_id: {
        "front": (
            "national identity card",
            "national id",
            "given name",
            "date of birth",
            "national id number",
            "परिचयपत्र",
            "photo",
            "फोटो",
        ),
        "back": (
            "father",
            "mother",
            "permanent address",
            "address",
            "date of issue",
            "जारी मिति",
            "बाबुको नाम",
            "आमाको नाम",
            "ठेगाना",
            "qr",
            "barcode",
        ),
    },
    DocumentType.passport: {
        "front": ("passport", "surname", "given name", "date of birth", "passport no", "p<npl", "mrz"),
        "back": ("emergency contact", "observation", "endorsement", "address"),
    },
    DocumentType.driving_license: {
        "front": ("driving license", "d.l.no", "name", "address", "license office", "category", "photo"),
        "back": ("vehicle category", "restriction", "blood group", "date of issue", "date of expiry"),
    },
}


FIELD_ALIASES: tuple[dict[str, Any], ...] = (
    {"canonical_key": "full_name", "variant": "np", "aliases": ("नाम थर", "नाम", "आवेदकको नाम")},
    {
        "canonical_key": "full_name",
        "variant": "en",
        "aliases": ("full name", "applicant name", "applicant's full name", "name", "given name"),
    },
    {
        "canonical_key": "issuing_authority_name",
        "aliases": ("प्रमाण पत्र जारी गर्ने अधिकारीको नाम थर", "प्रमाण-पत्र दिने अधिकारीको नाम थर"),
    },
    {
        "canonical_key": "issuing_authority_name",
        "aliases": ("issuing officer name", "issuing authority name", "officer name"),
    },
    {"canonical_key": "issuing_authority_designation", "aliases": ("दर्जा", "designation", "officer designation")},
    {
        "canonical_key": "father_name",
        "variant": "np",
        "aliases": ("बाबुको नाम थर", "बाबुको नाम", "बुबाको नाम", "पिताको नाम"),
    },
    {"canonical_key": "father_name", "variant": "en", "aliases": ("father name", "father's name")},
    {"canonical_key": "mother_name", "variant": "np", "aliases": ("आमाको नाम थर", "आमाको नाम", "माताको नाम")},
    {"canonical_key": "mother_name", "variant": "en", "aliases": ("mother name", "mother's name")},
    {
        "canonical_key": "spouse_name",
        "variant": "np",
        "aliases": ("पति/पत्नीको नामथर", "पति/पत्नीको नाम थर", "पतिको नाम", "पत्नीको नाम"),
    },
    {"canonical_key": "spouse_name", "variant": "en", "aliases": ("spouse name", "husband name", "wife name")},
    {"canonical_key": "permanent_address", "variant": "np", "aliases": ("स्थायी वासस्थान", "स्थायी ठेगाना")},
    {"canonical_key": "permanent_address", "variant": "en", "aliases": ("permanent address",)},
    {"canonical_key": "address", "variant": "np", "aliases": ("ठेगाना",)},
    {"canonical_key": "address", "variant": "en", "aliases": ("address", "current address")},
    {"canonical_key": "birth_place", "aliases": ("birth place", "जन्म स्थान", "जन्मस्थान")},
    {"canonical_key": "dob", "kind": "date", "aliases": ("date of birth", "dob", "d.o.b", "जन्म मिति")},
    {"canonical_key": "issue_date", "kind": "date", "aliases": ("date of issue", "issue date", "जारी मिति")},
    {"canonical_key": "expiry_date", "kind": "date", "aliases": ("date of expiry", "expiry date", "date of expire")},
    {
        "canonical_key": "citizenship_number",
        "aliases": (
            "citizen id",
            "citizenship no",
            "citizenship number",
            "citizenship certificate no",
            "citizenship certificate number",
            "ना.प्र.नं",
            "ना प्र नं",
            "ना. प्र. नं",
            "ना प्र न",
        ),
    },
    {"canonical_key": "gender", "aliases": ("sex", "gender", "लिंग", "लिङ्ग")},
    {"canonical_key": "citizenship_type", "aliases": ("citizenship type", "citizenship kind", "नागरिकता किसिम", "नागरिकताको किसिम", "ना.कि", "ना कि")},
    {"canonical_key": "copy_type", "aliases": ("copy type", "प्रतिलिपि", "प्रथम प्रतिलिपि", "दोस्रो प्रतिलिपि")},
    {
        "canonical_key": "issuing_office",
        "aliases": ("issuing office", "issuing authority", "issuing authority office", "जारी गर्ने कार्यालय", "जारी गर्ने निकाय"),
    },
    {"canonical_key": "national_id_number", "aliases": ("national id no", "national id number", "परिचयपत्र नं")},
    {"canonical_key": "passport_number", "aliases": ("passport no", "passport number")},
    {"canonical_key": "license_number", "aliases": ("d.l.no", "dl no", "license no", "license number")},
    {"canonical_key": "pan", "aliases": ("pan", "pan no", "permanent account number")},
    {"canonical_key": "mobile", "aliases": ("mobile", "mobile no", "phone no", "contact no", "सम्पर्क फोन नं")},
    {"canonical_key": "email", "aliases": ("email", "e-mail", "इमेल")},
    {"canonical_key": "boid", "aliases": ("boid", "bo id", "demat no", "beneficiary id")},
    {"canonical_key": "dp_id", "aliases": ("dp id", "depository participant id")},
    {"canonical_key": "client_id", "aliases": ("client id", "client no")},
    {"canonical_key": "account_number", "aliases": ("account no", "account number", "bank account no", "खाता नम्बर")},
    {"canonical_key": "amount", "aliases": ("amount", "amount deposited", "total amount", "रकम")},
)

PUBLIC_FIELD_ALIASES = {
    "full_name": "name",
    "father_name": "father_name",
    "mother_name": "mother_name",
    "spouse_name": "spouse_name",
    "address": "address",
    "permanent_address": "permanent_address",
    "birth_place": "birth_place",
}

NEPALI_TRANSLITERATION_OVERRIDES = {
    "रुद्रमान": "rudra man",
    "रुद्र": "rudra",
    "मान": "man",
    "इसुवा": "isuwa",
    "सीता": "sita",
    "शर्मा": "sharma",
    "माया": "maya",
    "लामा": "lama",
    "काठमाण्डौ": "kathmandu",
    "काठमाडौं": "kathmandu",
    "काठमाण्डौँ": "kathmandu",
    "नेपाल": "nepal",
}

DEVANAGARI_VOWELS = {
    "अ": "a",
    "आ": "a",
    "इ": "i",
    "ई": "i",
    "उ": "u",
    "ऊ": "u",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
}

DEVANAGARI_CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ng",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "ny",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "w",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
}

DEVANAGARI_MATRAS = {
    "ा": "a",
    "ि": "i",
    "ी": "i",
    "ु": "u",
    "ू": "u",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
}


@dataclass(frozen=True)
class FieldObservation:
    canonical_key: str
    output_key: str
    label: str
    value: str
    language: str
    confidence: float
    source_page: int
    bbox: Optional[list[int]]
    evidence_text: str


def _normalize_text(value: str) -> str:
    normalized = normalize_nepali_digits(value).lower()
    normalized = re.sub(r"[\s\-_:：#|]+", " ", normalized)
    normalized = re.sub(r"[.,;()]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _clean_value(value: str) -> str:
    return normalize_nepali_digits(value.strip().strip(":-|,;"))


def _format_date_value(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _month_number(value: str) -> Optional[int]:
    normalized = normalize_nepali_digits(value).strip().lower().strip(".")
    if not normalized:
        return None
    if normalized.isdigit():
        month = int(normalized)
        return month if 1 <= month <= 12 else None
    return MONTH_ALIASES.get(normalized)


def _regex_group(pattern: str, text: str, *, flags: int = re.IGNORECASE) -> Optional[str]:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return next((group for group in match.groups() if group), None)


def _structured_date_conversion(value: str, context: str = "") -> Optional[CalendarConversion]:
    normalized = normalize_nepali_digits(f"{value} {context}")
    year_value = _regex_group(r"(?:year|साल)\s*[:：.]?\s*([0-9]{4})", normalized)
    month_value = _regex_group(r"(?:month|महिना)\s*[:：.]?\s*([A-Za-z]{3,9}|[0-9]{1,2})", normalized)
    day_value = _regex_group(r"(?:day|गते)\s*[:：.]?\s*([0-9]{1,2})", normalized)
    if not year_value or not month_value or not day_value:
        return None

    year = int(year_value)
    month = _month_number(month_value)
    day = int(day_value)
    if month is None:
        return None

    try:
        if year >= 2040 or any(signal in normalized for signal in ("साल", "गते", "महिना", "वि.सं", "बि.सं")):
            bs_date = nepali_datetime.date(year, month, day)
            ad_date = bs_date.to_datetime_date()
            return CalendarConversion(
                calendar="bs",
                ad=ad_date.isoformat(),
                bs=_format_date_value(bs_date.year, bs_date.month, bs_date.day),
            )

        ad_date = date(year, month, day)
        bs_date = nepali_datetime.date.from_datetime_date(ad_date)
        return CalendarConversion(
            calendar="ad",
            ad=ad_date.isoformat(),
            bs=_format_date_value(bs_date.year, bs_date.month, bs_date.day),
        )
    except (ValueError, OverflowError):
        return None


def _calendar_conversion(value: str, context: str = "") -> Optional[CalendarConversion]:
    return convert_calendar_date(value, context=context) or _structured_date_conversion(value, context=context)


def _normalized_gender(value: str) -> str:
    normalized = _normalize_text(value)
    if any(token in normalized for token in ("male", "पुरुष")):
        return "Male"
    if any(token in normalized for token in ("female", "महिला")):
        return "Female"
    return _clean_value(value)


def _citizenship_type_value(value: str) -> str:
    normalized = _normalize_text(value)
    if "वंशज" in normalized or "descent" in normalized:
        return "वंशज"
    if "जन्मसिद्ध" in normalized:
        return "जन्मसिद्ध"
    if "अंगीकृत" in normalized or "naturalized" in normalized:
        return "अंगीकृत"
    return _clean_value(value)


def _field_language(value: str) -> str:
    if DEVANAGARI_TEXT_RE.search(value):
        return "np"
    if re.search(r"[A-Za-z]", value):
        return "en"
    return "numeric"


def _public_field_alias(output_key: str) -> Optional[str]:
    for suffix, public_suffix in (("_np", "_ne"), ("_en", "_en")):
        if not output_key.endswith(suffix):
            continue
        canonical_key = output_key[: -len(suffix)]
        public_key = PUBLIC_FIELD_ALIASES.get(canonical_key)
        if public_key:
            return f"{public_key}{public_suffix}"
    return None


def _strip_inherent_vowel(buffer: list[str]) -> None:
    if buffer and buffer[-1].endswith("a"):
        buffer[-1] = buffer[-1][:-1]


def _transliterate_devanagari_token(token: str) -> str:
    buffer: list[str] = []
    for char in token:
        if char in DEVANAGARI_CONSONANTS:
            buffer.append(f"{DEVANAGARI_CONSONANTS[char]}a")
        elif char in DEVANAGARI_MATRAS:
            _strip_inherent_vowel(buffer)
            buffer.append(DEVANAGARI_MATRAS[char])
        elif char == "्":
            _strip_inherent_vowel(buffer)
        elif char in DEVANAGARI_VOWELS:
            buffer.append(DEVANAGARI_VOWELS[char])
        elif char in {"ं", "ँ"}:
            buffer.append("n")
        elif char == "ः":
            buffer.append("h")
        elif char == "।":
            buffer.append(" ")
        elif char.strip():
            buffer.append(char)
    return "".join(buffer)


def _transliterate_nepali(value: str) -> str:
    tokens = re.split(r"(\s+)", value.strip())
    converted = [
        NEPALI_TRANSLITERATION_OVERRIDES.get(token, _transliterate_devanagari_token(token))
        if token.strip()
        else token
        for token in tokens
    ]
    transliterated = "".join(converted)
    return _normalize_text(transliterated)


def _normalize_roman_entity(value: str) -> str:
    normalized = normalize_nepali_digits(value).lower()
    normalized = normalized.replace(".", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalized_semantic_value(value: str, language: str) -> str:
    if language in {"np", "ne"} or DEVANAGARI_TEXT_RE.search(value):
        return _transliterate_nepali(value)
    return _normalize_roman_entity(value)


def _name_tokens(value: str) -> list[str]:
    return [token for token in _normalized_semantic_value(value, _field_language(value)).split() if token]


def _canonical_roman_token(token: str) -> str:
    return token.replace("w", "v")


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left

    left_index = right_index = edits = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            left_index += 1
            right_index += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(left) == len(right):
            left_index += 1
        right_index += 1
    return True


def _tokens_compatible(left: str, right: str) -> bool:
    left = _canonical_roman_token(left)
    right = _canonical_roman_token(right)
    return left == right or _edit_distance_at_most_one(left, right)


def compare_person_names(left: str, right: str) -> dict[str, object]:
    left_normalized = _normalized_semantic_value(left, _field_language(left))
    right_normalized = _normalized_semantic_value(right, _field_language(right))
    if not left_normalized or not right_normalized:
        return {
            "status": "insufficient_data",
            "confidence": 0.0,
            "reason": "One or both name values are empty.",
            "left_normalized": left_normalized,
            "right_normalized": right_normalized,
        }
    if left_normalized == right_normalized:
        return {
            "status": "same_person_likely",
            "confidence": 0.98,
            "reason": "Names match after normalization/transliteration.",
            "left_normalized": left_normalized,
            "right_normalized": right_normalized,
        }

    left_tokens = _name_tokens(left)
    right_tokens = _name_tokens(right)
    if (
        len(left_tokens) == len(right_tokens)
        and left_tokens
        and all(_tokens_compatible(left_token, right_token) for left_token, right_token in zip(left_tokens, right_tokens))
    ):
        return {
            "status": "same_person_likely",
            "confidence": 0.94,
            "reason": "Names match after Nepali transliteration and fuzzy token normalization.",
            "left_normalized": left_normalized,
            "right_normalized": right_normalized,
        }

    if (
        len(left_tokens) >= 2
        and len(right_tokens) >= 2
        and _tokens_compatible(left_tokens[0], right_tokens[0])
        and _tokens_compatible(left_tokens[-1], right_tokens[-1])
    ):
        left_middle = left_tokens[1:-1]
        right_middle = right_tokens[1:-1]
        if not left_middle or not right_middle:
            confidence = 0.88
            reason = "First and last names match; one value omits middle name."
        elif any(
            _tokens_compatible(left_part, right_part) or left_part[:1] == right_part[:1]
            for left_part in left_middle
            for right_part in right_middle
        ):
            confidence = 0.92
            reason = "First and last names match; middle initial/name is compatible."
        else:
            confidence = 0.76
            reason = "First and last names match but middle names differ; reviewer confirmation required."
        return {
            "status": "same_person_likely" if confidence >= 0.88 else "needs_review",
            "confidence": confidence,
            "reason": reason,
            "left_normalized": left_normalized,
            "right_normalized": right_normalized,
        }

    overlap = 0
    unmatched_right = right_tokens[:]
    for left_token in left_tokens:
        match_index = next(
            (index for index, right_token in enumerate(unmatched_right) if _tokens_compatible(left_token, right_token)),
            None,
        )
        if match_index is None:
            continue
        overlap += 1
        unmatched_right.pop(match_index)
    confidence = round(overlap / max(len(set(left_tokens + right_tokens)), 1), 2)
    return {
        "status": "needs_review" if confidence >= 0.45 else "different_or_unclear",
        "confidence": confidence,
        "reason": "Name tokens partially overlap; reviewer confirmation required.",
        "left_normalized": left_normalized,
        "right_normalized": right_normalized,
    }


def _document_text(document: FinancialDocument) -> str:
    return "\n".join(block.text for page in document.pages for block in page.blocks if block.text)


def classify_document(document: FinancialDocument) -> dict[str, object]:
    text = _normalize_text(_document_text(document))
    scores: Counter[DocumentType] = Counter()
    matched_signals: dict[str, list[str]] = {}

    for document_type, signals in DOCUMENT_SIGNALS.items():
        for signal in signals:
            normalized_signal = _normalize_text(signal)
            if normalized_signal and normalized_signal in text:
                scores[document_type] += 1
                matched_signals.setdefault(document_type.value, []).append(signal)

    if scores:
        predicted, score = scores.most_common(1)[0]
        confidence = round(min(0.98, 0.66 + score * 0.08), 2)
        reason = f"matched {score} document signal(s)"
        signals = matched_signals.get(predicted.value, [])
    elif document.declared_document_type != DocumentType.unknown:
        predicted = document.declared_document_type
        confidence = 0.76
        reason = "using declared document type; no stronger OCR signal found"
        signals = []
    else:
        predicted = DocumentType.unknown
        confidence = 0.35
        reason = "no strong OCR document signal found"
        signals = []

    return {
        "document_type": predicted.value,
        "confidence": confidence,
        "reason": reason,
        "signals": signals,
    }


def _document_type_from_value(value: object) -> DocumentType:
    try:
        return DocumentType(str(value))
    except ValueError:
        return DocumentType.unknown


def detect_document_variant(document: FinancialDocument, classification: dict[str, object]) -> dict[str, object]:
    text = _normalize_text(_document_text(document))
    predicted_type = _document_type_from_value(classification.get("document_type"))
    scored: list[tuple[float, int, dict[str, Any], list[str]]] = []

    for variant in DOCUMENT_VARIANTS:
        signals = tuple(str(signal) for signal in variant["signals"])
        matched = [signal for signal in signals if _normalize_text(signal) in text]
        if not matched:
            continue
        type_bonus = 1 if variant["document_type"] == predicted_type else 0
        score = len(matched) + type_bonus
        confidence = round(min(0.98, 0.56 + score * 0.08), 2)
        scored.append((confidence, score, variant, matched))

    if scored:
        confidence, score, variant, matched = max(scored, key=lambda item: (item[0], item[1]))
        return {
            "key": variant["key"],
            "label": variant["label"],
            "document_type": variant["document_type"].value,
            "version_family": variant["version_family"],
            "confidence": confidence,
            "reason": f"matched {len(matched)} Nepal layout/version signal(s)",
            "matched_signals": matched,
        }

    if predicted_type != DocumentType.unknown:
        return {
            "key": f"{predicted_type.value}_unclassified_variant",
            "label": f"{predicted_type.value.replace('_', ' ').title()} (Unclassified Variant)",
            "document_type": predicted_type.value,
            "version_family": "unclassified",
            "confidence": round(max(0.45, float(classification.get("confidence") or 0.0) - 0.12), 2),
            "reason": "document type detected, but no known Nepal layout/version signal matched",
            "matched_signals": [],
        }

    return {
        "key": "unknown_variant",
        "label": "Unknown Document Variant",
        "document_type": DocumentType.unknown.value,
        "version_family": "unknown",
        "confidence": 0.25,
        "reason": "no known document variant signal matched",
        "matched_signals": [],
    }


def _asset_type_for_block(block: OcrBlock) -> Optional[str]:
    block_type = (block.block_type or "").lower().strip()
    if block_type in {"photo", "portrait", "face"}:
        return "photo"
    if block_type in {"fingerprint", "thumbprint"}:
        return "fingerprint"
    if block_type in {"signature", "sign"}:
        return "signature"
    if block_type in {"stamp", "seal"}:
        return "stamp"
    if block_type in {"chip", "card_chip"}:
        return "chip"

    text = _normalize_text(block.text)
    if any(signal in text for signal in ("photo", "photograph", "फोटो")):
        return "photo"
    if any(signal in text for signal in ("fingerprint", "thumbprint", "thumb impression", "औंठा", "औँठा")):
        return "fingerprint"
    if any(signal in text for signal in ("signature", "signed by", "हस्ताक्षर", "दस्तखत")):
        return "signature"
    if "chip" in text:
        return "chip"
    if any(signal in text for signal in ("stamp", "seal", "छाप")):
        return "stamp"
    return None


def detect_document_assets(document: FinancialDocument) -> list[DocumentAsset]:
    assets: list[DocumentAsset] = []
    seen: set[tuple[str, int, tuple[int, ...]]] = set()
    for page in document.pages:
        for block in page.blocks:
            asset_type = _asset_type_for_block(block)
            if asset_type is None:
                continue
            bbox_key: tuple[int, ...] = tuple(block.bbox or [])
            identity = (asset_type, page.page_number, bbox_key)
            if identity in seen:
                continue
            seen.add(identity)
            assets.append(
                DocumentAsset(
                    asset_type=asset_type,
                    label=asset_type.replace("_", " ").title(),
                    page_number=page.page_number,
                    bbox=block.bbox,
                    confidence=round(min(0.96, max(float(block.confidence), 0.72)), 2),
                    source="block_type"
                    if (block.block_type or "").lower() in {"photo", "fingerprint", "signature", "stamp", "seal", "chip"}
                    else "ocr_signal",
                )
            )
    return assets


def _union_bbox(blocks: list[OcrBlock], page_width: int, page_height: int) -> Optional[list[int]]:
    boxes = [block.bbox for block in blocks if block.bbox and len(block.bbox) == 4]
    if not boxes:
        return None
    padding = 24
    return [
        max(0, min(box[0] for box in boxes) - padding),
        max(0, min(box[1] for box in boxes) - padding),
        min(page_width, max(box[2] for box in boxes) + padding),
        min(page_height, max(box[3] for box in boxes) + padding),
    ]


def _block_side_signal(document_type: DocumentType, block: OcrBlock) -> tuple[str, list[str]]:
    side_signals = DOCUMENT_SIDE_SIGNALS.get(document_type, {})
    text = _normalize_text(block.text)
    scores: list[tuple[int, str, list[str]]] = []
    for side, signals in side_signals.items():
        matched = [signal for signal in signals if _normalize_text(signal) in text]
        if matched:
            scores.append((len(matched), side, matched))
    if not scores:
        return "unknown", []
    _, side, matched = max(scores, key=lambda item: item[0])
    return side, matched


def detect_document_sections(
    document: FinancialDocument,
    classification: dict[str, object],
) -> list[DocumentSection]:
    document_type = _document_type_from_value(classification.get("document_type"))
    sections: list[DocumentSection] = []
    if document_type not in DOCUMENT_SIDE_SIGNALS:
        return sections

    if len(document.pages) > 1:
        for page in document.pages:
            inferred_side = "front" if page.page_number == 1 else "back" if page.page_number == 2 else "unknown"
            page_blocks = [block for block in page.blocks if block.text.strip()]
            signals: list[str] = []
            for block in page_blocks:
                _side, matched = _block_side_signal(document_type, block)
                signals.extend(matched)
            sections.append(
                DocumentSection(
                    side=inferred_side,
                    label=f"{inferred_side.title()} Side" if inferred_side != "unknown" else "Unknown Side",
                    page_number=page.page_number,
                    bbox=_union_bbox(page_blocks, page.width, page.height) or [0, 0, page.width, page.height],
                    confidence=0.88 if inferred_side != "unknown" else 0.45,
                    source="page_order_inference",
                    signals=sorted(set(signals)),
                )
            )
        return sections

    for page in document.pages:
        side_blocks: dict[str, list[OcrBlock]] = {"front": [], "back": []}
        side_signals: dict[str, list[str]] = {"front": [], "back": []}
        for block in page.blocks:
            side, matched = _block_side_signal(document_type, block)
            if side not in side_blocks:
                continue
            side_blocks[side].append(block)
            side_signals[side].extend(matched)

        detected_sides = [side for side in ("front", "back") if side_blocks[side]]
        if not detected_sides and len(document.pages) > 1:
            inferred_side = "front" if page.page_number == 1 else "back" if page.page_number == 2 else "unknown"
            sections.append(
                DocumentSection(
                    side=inferred_side,
                    label=f"{inferred_side.title()} Side" if inferred_side != "unknown" else "Unknown Side",
                    page_number=page.page_number,
                    bbox=[0, 0, page.width, page.height],
                    confidence=0.72 if inferred_side != "unknown" else 0.40,
                    source="page_order_inference",
                    signals=[],
                )
            )
            continue

        for side in detected_sides:
            signals = sorted(set(side_signals[side]))
            sections.append(
                DocumentSection(
                    side=side,
                    label=f"{side.title()} Side",
                    page_number=page.page_number,
                    bbox=_union_bbox(side_blocks[side], page.width, page.height),
                    confidence=round(min(0.96, 0.68 + len(signals) * 0.06), 2),
                    source="ocr_side_signal",
                    signals=signals,
                )
            )

    return sections


def _bbox_center(bbox: Optional[list[int]]) -> tuple[float, float]:
    if not bbox or len(bbox) != 4:
        return 0.0, 0.0
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def _bbox_contains(container: Optional[list[int]], point: tuple[float, float]) -> bool:
    if not container or len(container) != 4:
        return False
    x, y = point
    return container[0] <= x <= container[2] and container[1] <= y <= container[3]


def _nearest_section(
    page_number: int,
    bbox: Optional[list[int]],
    sections: list[DocumentSection],
) -> Optional[DocumentSection]:
    page_sections = [section for section in sections if section.page_number == page_number]
    if not page_sections:
        return None
    if len(page_sections) == 1:
        return page_sections[0]

    point = _bbox_center(bbox)
    containing = [section for section in page_sections if _bbox_contains(section.bbox, point)]
    if containing:
        return containing[0]

    def distance(section: DocumentSection) -> float:
        section_center = _bbox_center(section.bbox)
        return abs(point[0] - section_center[0]) + abs(point[1] - section_center[1])

    return min(page_sections, key=distance)


def _mapped_observation_for_block(
    page_number: int,
    block: OcrBlock,
    observations: list[FieldObservation],
) -> Optional[FieldObservation]:
    for observation in observations:
        if observation.source_page != page_number:
            continue
        if observation.bbox == block.bbox:
            return observation
        block_text = block.text.strip()
        if observation.evidence_text and observation.evidence_text in block_text:
            return observation
    return None


def build_evidence_ledger(
    document: FinancialDocument,
    observations: list[FieldObservation],
    sections: Optional[list[DocumentSection]] = None,
) -> list[EvidenceLedgerEntry]:
    ledger: list[EvidenceLedgerEntry] = []
    sections = sections or []
    for page in document.pages:
        for block_index, block in enumerate(page.blocks, start=1):
            observation = _mapped_observation_for_block(page.page_number, block, observations)
            section = _nearest_section(page.page_number, block.bbox, sections)
            ledger.append(
                EvidenceLedgerEntry(
                    page_number=page.page_number,
                    block_index=block_index,
                    text=block.text,
                    normalized_text=_normalize_text(block.text),
                    language=block.language,
                    block_type=block.block_type,
                    confidence=round(float(block.confidence), 2),
                    bbox=block.bbox,
                    mapped_field_key=observation.output_key if observation else None,
                    asset_type=_asset_type_for_block(block),
                    section_id=section.id if section else None,
                    section_side=section.side if section else None,
                )
            )
    return ledger


def _normalization_value(normalizations: dict[str, dict[str, object]], key: str) -> str:
    payload = normalizations.get(key, {})
    value = payload.get("normalized_value", "")
    return value if isinstance(value, str) else ""


def _observation_confidence(observations: list[FieldObservation], key: str) -> float:
    for observation in observations:
        if observation.output_key == key:
            return observation.confidence
    return 0.0


def build_entity_records(
    canonical_fields: dict[str, str],
    normalizations: dict[str, dict[str, object]],
    language_pairs: list[dict[str, object]],
    observations: list[FieldObservation],
) -> list[dict[str, object]]:
    pair_status = {str(pair.get("canonical_key")): str(pair.get("status")) for pair in language_pairs}
    entity_records: list[dict[str, object]] = []

    person_fields = {
        "full_name": "person.full_name",
        "father_name": "person.father_name",
        "mother_name": "person.mother_name",
        "address": "person.address",
    }
    for canonical_key, entity_key in person_fields.items():
        nepali_key = f"{canonical_key}_np"
        english_key = f"{canonical_key}_en"
        original_ne = canonical_fields.get(nepali_key) or canonical_fields.get(
            f"{PUBLIC_FIELD_ALIASES.get(canonical_key, canonical_key)}_ne"
        )
        original_en = canonical_fields.get(english_key) or canonical_fields.get(
            f"{PUBLIC_FIELD_ALIASES.get(canonical_key, canonical_key)}_en"
        )
        if not original_ne and not original_en:
            continue
        source_fields = [key for key, value in ((nepali_key, original_ne), (english_key, original_en)) if value]
        confidences = [_observation_confidence(observations, key) for key in source_fields]
        non_zero_confidences = [confidence for confidence in confidences if confidence > 0]
        if original_ne and original_en:
            status = "paired" if pair_status.get(canonical_key) == "matched" else "needs_review"
        else:
            status = "single_source"
        entity_records.append(
            {
                "entity_key": entity_key,
                "canonical_key": canonical_key,
                "original_ne": original_ne or "",
                "original_en": original_en or "",
                "normalized_ne": _normalization_value(normalizations, nepali_key),
                "normalized_en": _normalization_value(normalizations, english_key),
                "source_fields": source_fields,
                "confidence": round(sum(non_zero_confidences) / len(non_zero_confidences), 2)
                if non_zero_confidences
                else 0.0,
                "status": status,
                "audit_reason": "Original bilingual values retained; normalized values support matching and export.",
            }
        )

    identifier_entities = {
        "citizenship_number": "person.citizenship_number",
        "national_id_number": "person.national_id_number",
        "passport_number": "person.passport_number",
        "license_number": "person.license_number",
        "pan": "person.pan",
        "mobile": "contact.mobile",
        "email": "contact.email",
        "account_number": "bank.account_number",
        "boid": "demat.boid",
        "dp_id": "demat.dp_id",
        "client_id": "demat.client_id",
    }
    for field_key, entity_key in identifier_entities.items():
        value = canonical_fields.get(field_key)
        if not value:
            continue
        entity_records.append(
            {
                "entity_key": entity_key,
                "canonical_key": field_key,
                "value": value,
                "normalized_value": _normalized_semantic_value(value, _field_language(value)),
                "source_fields": [field_key],
                "confidence": _observation_confidence(observations, field_key),
                "status": "single_source",
                "audit_reason": "Identifier retained from source OCR for reviewer confirmation and export mapping.",
            }
        )

    return entity_records


def _match_alias(label: str) -> Optional[dict[str, Any]]:
    normalized_label = _normalize_text(label)
    if not normalized_label:
        return None

    scored: list[tuple[int, dict[str, Any]]] = []
    for spec in FIELD_ALIASES:
        for alias in spec["aliases"]:
            normalized_alias = _normalize_text(alias)
            if not normalized_alias:
                continue
            if normalized_label == normalized_alias:
                scored.append((100 + len(normalized_alias), spec))
            elif normalized_alias in normalized_label:
                scored.append((50 + len(normalized_alias), spec))

    if not scored:
        return None
    return max(scored, key=lambda item: item[0])[1]


def _output_key(spec: dict[str, Any], value: str, context: str) -> str:
    canonical_key = str(spec["canonical_key"])
    if spec.get("kind") == "date":
        conversion = _calendar_conversion(value, context=context)
        if conversion is None:
            return canonical_key
        return f"{canonical_key}_{conversion.calendar}"

    variant = spec.get("variant")
    if variant:
        detected_language = _field_language(value)
        if detected_language in {"np", "en"}:
            return f"{canonical_key}_{detected_language}"
        return f"{canonical_key}_{variant}"

    return canonical_key


def _observation_value(spec: dict[str, Any], value: str, context: str) -> str:
    canonical_key = str(spec["canonical_key"])
    if spec.get("kind") == "date":
        conversion = _calendar_conversion(value, context=context)
        output_key = _output_key(spec, value, context)
        if conversion and output_key.endswith("_ad"):
            return conversion.ad
        if conversion and output_key.endswith("_bs"):
            return conversion.bs
    if canonical_key == "gender":
        return _normalized_gender(value)
    if canonical_key == "citizenship_type":
        return _citizenship_type_value(value)
    return _clean_value(value)


def _add_structured_observation(
    observations: list[FieldObservation],
    seen: set[tuple[str, str]],
    *,
    canonical_key: str,
    output_key: str,
    label: str,
    value: str,
    source_page: int,
    bbox: Optional[list[int]],
    confidence: float,
    evidence_text: str,
) -> None:
    cleaned_value = _clean_value(value)
    if canonical_key == "gender":
        cleaned_value = _normalized_gender(cleaned_value)
    elif canonical_key == "citizenship_type":
        cleaned_value = _citizenship_type_value(cleaned_value)
    if not cleaned_value:
        return
    identity = (output_key, cleaned_value)
    if identity in seen:
        return
    seen.add(identity)
    observations.append(
        FieldObservation(
            canonical_key=canonical_key,
            output_key=output_key,
            label=label,
            value=cleaned_value,
            language=_field_language(cleaned_value),
            confidence=round(min(0.97, confidence + 0.04), 2),
            source_page=source_page,
            bbox=bbox,
            evidence_text=evidence_text,
        )
    )


def _citizenship_structured_observations(
    document: FinancialDocument,
    seen: set[tuple[str, str]],
) -> list[FieldObservation]:
    text = _normalize_text(_document_text(document))
    if (
        document.document_type != DocumentType.citizenship
        and document.declared_document_type != DocumentType.citizenship
        and "citizenship" not in text
        and "नागरिकता" not in text
        and "ना प्र" not in text
    ):
        return []

    observations: list[FieldObservation] = []
    for page in document.pages:
        for block in page.blocks:
            line = block.text.strip()
            if not line:
                continue
            normalized_line = normalize_nepali_digits(line)

            office_match = re.search(r"(जिल्ला\s+प्रशासन\s+कार्यालय\s*[,।]?\s*[\u0900-\u097F A-Za-z]+)", normalized_line)
            if office_match:
                _add_structured_observation(
                    observations,
                    seen,
                    canonical_key="issuing_office",
                    output_key="issuing_office",
                    label="Issuing Office",
                    value=office_match.group(1),
                    source_page=page.page_number,
                    bbox=block.bbox,
                    confidence=block.confidence,
                    evidence_text=line,
                )

            if "प्रथम प्रतिलिपि" in normalized_line or "दोस्रो प्रतिलिपि" in normalized_line:
                copy_value = "दोस्रो प्रतिलिपि" if "दोस्रो प्रतिलिपि" in normalized_line else "प्रथम प्रतिलिपि"
                _add_structured_observation(
                    observations,
                    seen,
                    canonical_key="copy_type",
                    output_key="copy_type",
                    label="Copy Type",
                    value=copy_value,
                    source_page=page.page_number,
                    bbox=block.bbox,
                    confidence=block.confidence,
                    evidence_text=line,
                )

            type_match = re.search(r"(वंशज|जन्मसिद्ध|अंगीकृत|descent|naturalized)", normalized_line, re.IGNORECASE)
            if type_match and any(signal in _normalize_text(normalized_line) for signal in ("नागरिकता किसिम", "ना कि", "citizenship type")):
                _add_structured_observation(
                    observations,
                    seen,
                    canonical_key="citizenship_type",
                    output_key="citizenship_type",
                    label="Citizenship Type",
                    value=type_match.group(1),
                    source_page=page.page_number,
                    bbox=block.bbox,
                    confidence=block.confidence,
                    evidence_text=line,
                )

    return observations


def detect_fields(document: FinancialDocument) -> list[FieldObservation]:
    observations: list[FieldObservation] = []
    seen: set[tuple[str, str]] = set()

    for page in document.pages:
        for block in page.blocks:
            for raw_line in block.text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                match = LABEL_VALUE_RE.match(line)
                if not match:
                    continue

                label = match.group("label").strip()
                value = _clean_value(match.group("value"))
                if not value:
                    continue
                spec = _match_alias(label)
                if spec is None:
                    continue

                canonical_key = str(spec["canonical_key"])
                output_key = _output_key(spec, value, context=line)
                value = _observation_value(spec, value, context=line)
                identity = (output_key, value)
                if identity in seen:
                    continue
                seen.add(identity)

                observation = FieldObservation(
                    canonical_key=canonical_key,
                    output_key=output_key,
                    label=label,
                    value=value,
                    language=_field_language(value),
                    confidence=round(min(0.97, float(block.confidence) + 0.05), 2),
                    source_page=page.page_number,
                    bbox=block.bbox,
                    evidence_text=line,
                )
                observations.append(observation)

                if canonical_key == "permanent_address" and observation.language in {"np", "en"}:
                    address_key = f"address_{observation.language}"
                    address_identity = (address_key, value)
                    if address_identity not in seen:
                        seen.add(address_identity)
                        observations.append(
                            FieldObservation(
                                canonical_key="address",
                                output_key=address_key,
                                label=label,
                                value=value,
                                language=observation.language,
                                confidence=observation.confidence,
                                source_page=page.page_number,
                                bbox=block.bbox,
                                evidence_text=line,
                            )
                        )

    observations.extend(_citizenship_structured_observations(document, seen))
    return observations


def _place_component(patterns: tuple[str, ...], text: str) -> Optional[str]:
    normalized = normalize_nepali_digits(text)
    stop = (
        r"(?=\s+(?:district|metropolitan|municipality|r\.?\s*m\.?|vdc|ward|"
        r"जिल्ला|म\.?न\.?पा\.?|न\.?पा\.?|गा\.?वि\.?स\.?|वडा|$))"
    )
    for pattern in patterns:
        match = re.search(pattern + r"\s*[:：.]?\s*([A-Za-z\u0900-\u097F ]+?|\d+)\s*" + stop, normalized, re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))
    return None


def _place_ward(text: str) -> Optional[str]:
    normalized = normalize_nepali_digits(text)
    match = re.search(r"(?:ward\s*no\.?|वडा\s*नं\.?|वडा\s*न)\s*[:：.]?\s*([0-9]{1,3})", normalized, re.IGNORECASE)
    return match.group(1) if match else None


def _prefer_component(existing: Optional[str], value: Optional[str]) -> Optional[str]:
    if not value:
        return existing
    if not existing:
        return value
    if DEVANAGARI_TEXT_RE.search(existing) and not DEVANAGARI_TEXT_RE.search(value):
        return value
    return existing


def _derive_location_fields(fields: dict[str, str], prefix: str, value: str) -> None:
    district = _place_component((r"district", r"जिल्ला"), value)
    municipality = _place_component(
        (
            r"metropolitan",
            r"municipality",
            r"r\.?\s*m\.?",
            r"vdc",
            r"म\.?न\.?पा\.?",
            r"न\.?पा\.?",
            r"गा\.?वि\.?स\.?",
        ),
        value,
    )
    ward = _place_ward(value)
    for suffix, component in (("district", district), ("municipality", municipality), ("ward", ward)):
        key = f"{prefix}_{suffix}"
        preferred = _prefer_component(fields.get(key), component)
        if preferred:
            fields[key] = preferred


def _derive_citizenship_components(fields: dict[str, str], observations: list[FieldObservation]) -> None:
    for observation in observations:
        if observation.output_key.startswith("birth_place"):
            _derive_location_fields(fields, "birth_place", observation.value)
        elif observation.output_key.startswith("permanent_address"):
            _derive_location_fields(fields, "permanent_address", observation.value)


def _canonical_fields(observations: list[FieldObservation]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for observation in observations:
        if observation.output_key not in fields:
            fields[observation.output_key] = observation.value
        public_alias = _public_field_alias(observation.output_key)
        if public_alias and public_alias not in fields:
            fields[public_alias] = observation.value

        if observation.canonical_key in {"dob", "issue_date", "expiry_date"}:
            conversion = _calendar_conversion(observation.value, context=observation.evidence_text)
            if conversion:
                fields[f"{observation.canonical_key}_ad"] = conversion.ad
                fields[f"{observation.canonical_key}_bs"] = conversion.bs
    _derive_citizenship_components(fields, observations)
    return fields


def _normalizations(observations: list[FieldObservation]) -> dict[str, dict[str, object]]:
    normalizations: dict[str, dict[str, object]] = {}
    for observation in observations:
        normalized_value = _normalized_semantic_value(observation.value, observation.language)
        language = "ne" if observation.language == "np" else observation.language
        payload = {
            "canonical_key": observation.canonical_key,
            "field_key": observation.output_key,
            "language": language,
            "original_value": observation.value,
            "normalized_value": normalized_value,
            "method": "transliteration" if language == "ne" else "normalization",
            "confidence": observation.confidence,
            "audit_reason": "Original OCR value retained; normalized value is used for matching and export preparation.",
        }
        normalizations[observation.output_key] = payload
        public_alias = _public_field_alias(observation.output_key)
        if public_alias:
            normalizations[public_alias] = {**payload, "field_key": public_alias, "source_field": observation.output_key}
    return normalizations


def _language_pairs(
    canonical_fields: dict[str, str],
    normalizations: Optional[dict[str, dict[str, object]]] = None,
) -> list[dict[str, object]]:
    pairs: list[dict[str, object]] = []
    for canonical_key in ("full_name", "father_name", "mother_name", "address"):
        nepali_value = canonical_fields.get(f"{canonical_key}_np")
        english_value = canonical_fields.get(f"{canonical_key}_en")
        if nepali_value and english_value:
            public_key = PUBLIC_FIELD_ALIASES.get(canonical_key, canonical_key)
            nepali_normalized = (normalizations or {}).get(f"{canonical_key}_np", {}).get("normalized_value", "")
            english_normalized = (normalizations or {}).get(f"{canonical_key}_en", {}).get("normalized_value", "")
            if canonical_key.endswith("name") or canonical_key == "full_name":
                comparison = compare_person_names(nepali_value, english_value)
                matched = float(comparison["confidence"]) >= 0.88
            else:
                matched = bool(nepali_normalized and nepali_normalized == english_normalized)
            pairs.append(
                {
                    "canonical_key": canonical_key,
                    "nepali_field": f"{public_key}_ne",
                    "english_field": f"{public_key}_en",
                    "nepali_value": nepali_value,
                    "english_value": english_value,
                    "nepali_normalized": nepali_normalized,
                    "english_normalized": english_normalized,
                    "status": "matched" if matched else "needs_review",
                    "message": "Bilingual values detected; LipiCore keeps both originals and uses normalized values for matching.",
                }
            )
    return pairs


def _confidence_repairs(observations: list[FieldObservation]) -> list[dict[str, object]]:
    repairs: list[dict[str, object]] = []
    grouped: dict[str, dict[str, FieldObservation]] = {}
    for observation in observations:
        if observation.language not in {"np", "en"}:
            continue
        grouped.setdefault(observation.canonical_key, {})[observation.language] = observation

    for canonical_key, variants in grouped.items():
        nepali = variants.get("np")
        english = variants.get("en")
        if not nepali or not english:
            continue
        is_name_field = canonical_key.endswith("name") or canonical_key == "full_name"
        comparison = compare_person_names(nepali.value, english.value) if is_name_field else {
            "status": "needs_review",
            "confidence": 0.75,
            "reason": "Bilingual values are paired for reviewer confirmation.",
        }
        if is_name_field and float(comparison["confidence"]) < 0.88:
            continue
        for target, source in ((nepali, english), (english, nepali)):
            if target.confidence >= 0.80 or source.confidence < 0.85:
                continue
            repaired_confidence = round(min(0.92, max(target.confidence, float(source.confidence) - 0.03)), 2)
            repairs.append(
                {
                    "canonical_key": canonical_key,
                    "target_field": target.output_key,
                    "source_field_used": source.output_key,
                    "original_ocr_value": target.value,
                    "corrected_value": source.value,
                    "source_value": source.value,
                    "original_confidence": target.confidence,
                    "confidence": repaired_confidence,
                    "status": "suggested",
                    "audit_reason": (
                        "Confidence repaired from bilingual paired field; original OCR value is not overwritten and "
                        f"reviewer confirmation remains required. {comparison['reason']}"
                    ),
                }
            )
    return repairs


def _name_candidates(observations: list[FieldObservation]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, FieldObservation]] = {}
    for observation in observations:
        if observation.canonical_key not in {"full_name", "father_name", "mother_name", "spouse_name"}:
            continue
        if observation.language not in {"np", "en"}:
            continue
        grouped.setdefault(observation.canonical_key, {})[observation.language] = observation

    candidates: list[dict[str, object]] = []
    for canonical_key, variants in grouped.items():
        for target_language in ("en", "np"):
            target = variants.get(target_language)
            if not target:
                continue
            source_language = "np" if target_language == "en" else "en"
            source = variants.get(source_language)
            for suggestion in suggest_name_corrections(
                target.value,
                counterpart=source.value if source else "",
                field_key=target.output_key,
            ):
                suggested_value = str(suggestion.get("suggested_value") or "")
                if not suggested_value or _normalize_roman_entity(suggested_value) == _normalize_roman_entity(target.value):
                    continue
                candidates.append(
                    {
                        **suggestion,
                        "canonical_key": canonical_key,
                        "target_field": target.output_key,
                        "source_field_used": f"{source.output_key}+name_lexicon" if source else "name_lexicon",
                        "original_ocr_value": target.value,
                        "original_confidence": target.confidence,
                    }
                )
    return sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)


def _address_candidates(observations: list[FieldObservation], *, tenant_id: str = "demo-institution") -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for observation in observations:
        if not is_address_field_key(observation.output_key) and not is_address_field_key(observation.canonical_key):
            continue
        target_field = observation.canonical_key if is_address_field_key(observation.canonical_key) else observation.output_key
        for suggestion in suggest_address_corrections(
            observation.value,
            target_field=target_field,
            tenant_id=tenant_id,
        ):
            candidates.append(
                {
                    **suggestion,
                    "canonical_key": observation.canonical_key,
                    "target_field": target_field,
                    "source_field_used": "address_intelligence",
                    "original_confidence": observation.confidence,
                }
            )
    return sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)


def _location_source_value(canonical_fields: dict[str, str], prefix: str) -> str:
    values = [
        canonical_fields.get(prefix, ""),
        canonical_fields.get(f"{prefix}_np", ""),
        canonical_fields.get(f"{prefix}_ne", ""),
        canonical_fields.get(f"{prefix}_en", ""),
        canonical_fields.get(f"{prefix}_district", ""),
        canonical_fields.get(f"{prefix}_municipality", ""),
        canonical_fields.get(f"{prefix}_ward", ""),
    ]
    return " ".join(value for value in values if value).strip()


def _location_resolutions(canonical_fields: dict[str, str]) -> list[dict[str, object]]:
    resolutions: list[dict[str, object]] = []
    for prefix in ("permanent_address", "birth_place", "address"):
        source_value = _location_source_value(canonical_fields, prefix)
        if not source_value:
            continue
        resolution = resolve_nepal_location(source_value)
        if resolution.status == "unresolved":
            continue
        for key, value in resolution.as_fields(prefix).items():
            canonical_fields[key] = value
        payload = resolution.model_dump()
        payload["field_prefix"] = prefix
        payload["source_value"] = source_value
        resolutions.append(payload)
    return resolutions


def _cross_checks(
    canonical_fields: dict[str, str],
    language_pairs: list[dict[str, object]],
    location_resolutions: Optional[list[dict[str, object]]] = None,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for pair in language_pairs:
        checks.append(
            {
                "key": f"{pair['canonical_key']}_bilingual_match",
                "status": "needs_review",
                "severity": "warning",
                "message": pair["message"],
            }
        )

    for date_key in ("dob", "issue_date", "expiry_date"):
        if canonical_fields.get(f"{date_key}_ad") and canonical_fields.get(f"{date_key}_bs"):
            checks.append(
                {
                    "key": f"{date_key}_calendar_pair",
                    "status": "passed",
                    "severity": "info",
                    "message": f"{date_key.replace('_', ' ').title()} has matched AD and BS values.",
                }
            )

    for resolution in location_resolutions or []:
        prefix = str(resolution.get("field_prefix") or "address")
        status = "passed" if resolution.get("status") == "matched" else "needs_review"
        warnings = resolution.get("warnings") if isinstance(resolution.get("warnings"), list) else []
        checks.append(
            {
                "key": f"{prefix}_location_registry",
                "status": status,
                "severity": "info" if status == "passed" else "warning",
                "message": (
                    f"{prefix.replace('_', ' ').title()} resolved against Nepal location registry."
                    if status == "passed"
                    else f"{prefix.replace('_', ' ').title()} needs location review: {', '.join(str(item) for item in warnings)}."
                ),
            }
        )

    if not checks:
        checks.append(
            {
                "key": "semantic_extraction",
                "status": "needs_review",
                "severity": "warning",
                "message": "Review extracted values before export.",
            }
        )

    return checks


def analyze_document(document: FinancialDocument) -> dict[str, object]:
    classification = classify_document(document)
    observations = detect_fields(document)
    canonical_fields = _canonical_fields(observations)
    normalizations = _normalizations(observations)
    language_pairs = _language_pairs(canonical_fields, normalizations)
    confidence_repairs = _confidence_repairs(observations)
    name_candidates = _name_candidates(observations)
    address_candidates = _address_candidates(observations)
    location_resolutions = _location_resolutions(canonical_fields)
    cross_checks = _cross_checks(canonical_fields, language_pairs, location_resolutions)
    document_variant = detect_document_variant(document, classification)
    assets = detect_document_assets(document)
    document_sections = detect_document_sections(document, classification)
    evidence_ledger = build_evidence_ledger(document, observations, document_sections)
    entity_records = build_entity_records(canonical_fields, normalizations, language_pairs, observations)

    review_recommendations: list[str] = []
    if classification["confidence"] < 0.85:
        review_recommendations.append("Confirm document type before export.")
    if document_variant["confidence"] < 0.80:
        review_recommendations.append("Confirm Nepal document variant before template export.")
    if document_sections:
        review_recommendations.append("Confirm detected front/back document side sections before export.")
    if language_pairs:
        review_recommendations.append("Confirm Nepali and English field pairs before CBS/LOS ingestion.")
    if assets:
        review_recommendations.append("Review detected photo, signature, fingerprint, or stamp assets.")
    if not canonical_fields:
        review_recommendations.append("No canonical fields were detected; map OCR lines manually.")

    return {
        "document_id": document.id,
        "filename": document.filename,
        "document_type": classification["document_type"],
        "declared_document_type": document.declared_document_type.value,
        "confidence": classification["confidence"],
        "reason": classification["reason"],
        "signals": classification["signals"],
        "document_variant": document_variant,
        "document_sections": [section.model_dump() for section in document_sections],
        "detected_fields": [
            {
                "canonical_key": observation.canonical_key,
                "key": observation.output_key,
                "label": observation.label,
                "value": observation.value,
                "language": observation.language,
                "confidence": observation.confidence,
                "source_page": observation.source_page,
                "bbox": observation.bbox,
                "evidence_text": observation.evidence_text,
                "section_side": (
                    _nearest_section(observation.source_page, observation.bbox, document_sections).side
                    if _nearest_section(observation.source_page, observation.bbox, document_sections)
                    else None
                ),
                "section_id": (
                    _nearest_section(observation.source_page, observation.bbox, document_sections).id
                    if _nearest_section(observation.source_page, observation.bbox, document_sections)
                    else None
                ),
            }
            for observation in observations
        ],
        "canonical_fields": canonical_fields,
        "normalizations": normalizations,
        "language_pairs": language_pairs,
        "entity_records": entity_records,
        "location_resolutions": location_resolutions,
        "assets": [asset.model_dump() for asset in assets],
        "evidence_ledger": [entry.model_dump() for entry in evidence_ledger],
        "confidence_repairs": confidence_repairs,
        "name_candidates": name_candidates,
        "address_candidates": address_candidates,
        "cross_checks": cross_checks,
        "review_recommendations": review_recommendations,
    }


def _label_for_key(key: str) -> str:
    overrides = {
        "full_name_np": "Full Name (Nepali)",
        "full_name_en": "Full Name (English)",
        "dob_ad": "Date of Birth (AD)",
        "dob_bs": "Date of Birth (BS)",
        "issue_date_ad": "Date of Issue (AD)",
        "issue_date_bs": "Date of Issue (BS)",
        "expiry_date_ad": "Date of Expiry (AD)",
        "expiry_date_bs": "Date of Expiry (BS)",
    }
    return overrides.get(key, key.replace("_", " ").title())


def _observation_by_output_key(observations: list[FieldObservation]) -> dict[str, FieldObservation]:
    return {observation.output_key: observation for observation in observations}


def _make_field(
    *,
    key: str,
    value: str,
    document: FinancialDocument,
    observation: Optional[FieldObservation],
) -> ExtractedField:
    validation = validate_field(key, value, document.document_type.value)
    evidence = EvidenceRef(
        document_id=document.id,
        source_page=observation.source_page if observation else 1,
        bbox=observation.bbox if observation else None,
        evidence_text=observation.evidence_text if observation else f"Derived {key}: {value}",
    )
    return ExtractedField(
        key=key,
        label=_label_for_key(key),
        value=value,
        confidence=observation.confidence if observation else 0.90,
        required=False,
        source="document_intelligence",
        validation_status=ValidationStatus(validation["status"]),
        validation_message=validation["message"],
        bbox=observation.bbox if observation else None,
        evidence=evidence,
        extracted_by="LipiCore",
        review_status=ReviewStatus.needs_review,
        document_id=document.id,
    )


def apply_document_intelligence(
    document: FinancialDocument,
    fields: list[ExtractedField],
) -> dict[str, object]:
    analysis = analyze_document(document)
    predicted_type = DocumentType(str(analysis["document_type"]))
    if predicted_type != DocumentType.unknown and document.document_type == DocumentType.unknown:
        document.document_type = predicted_type
    document_variant = analysis.get("document_variant")
    if isinstance(document_variant, dict):
        document.document_variant = str(document_variant.get("key") or "") or None
    document.assets = [
        asset if isinstance(asset, DocumentAsset) else DocumentAsset.model_validate(asset)
        for asset in analysis.get("assets", [])
        if isinstance(asset, (dict, DocumentAsset))
    ]
    document.document_sections = [
        section if isinstance(section, DocumentSection) else DocumentSection.model_validate(section)
        for section in analysis.get("document_sections", [])
        if isinstance(section, (dict, DocumentSection))
    ]
    document.evidence_ledger = [
        entry if isinstance(entry, EvidenceLedgerEntry) else EvidenceLedgerEntry.model_validate(entry)
        for entry in analysis.get("evidence_ledger", [])
        if isinstance(entry, (dict, EvidenceLedgerEntry))
    ]
    document.intelligence = analysis

    observations = detect_fields(document)
    observations_by_key = _observation_by_output_key(observations)
    fields_by_key = {field.key: field for field in fields}

    for key, value in analysis["canonical_fields"].items():
        existing = fields_by_key.get(key)
        if existing and existing.source.startswith("reviewer"):
            continue

        observation = observations_by_key.get(key)
        if existing is None:
            field = _make_field(key=key, value=value, document=document, observation=observation)
            fields.append(field)
            fields_by_key[key] = field
            continue

        if not existing.value:
            existing.value = value
            existing.source = "document_intelligence"
            existing.extracted_by = "LipiCore"
            existing.evidence = _make_field(key=key, value=value, document=document, observation=observation).evidence

    for repair in analysis.get("confidence_repairs", []):
        if not isinstance(repair, dict):
            continue
        target_key = str(repair.get("target_field") or "")
        field = fields_by_key.get(target_key)
        if field is None or field.source.startswith("reviewer"):
            continue
        repaired_confidence = float(repair.get("confidence") or field.confidence)
        if repaired_confidence <= field.confidence:
            continue
        field.confidence = repaired_confidence
        field.source = "document_intelligence_confidence_repair"
        field.validation_message = str(repair.get("audit_reason") or field.validation_message)
        field.original_ocr_value = str(repair.get("original_ocr_value") or field.value)
        field.corrected_value = str(repair.get("corrected_value") or "")
        field.source_field_used = str(repair.get("source_field_used") or "")
        field.correction_confidence = repaired_confidence
        field.audit_reason = str(repair.get("audit_reason") or "")

    grouped_name_candidates: dict[str, list[dict[str, object]]] = defaultdict(list)
    for candidate in analysis.get("name_candidates", []):
        if isinstance(candidate, dict):
            grouped_name_candidates[str(candidate.get("target_field") or "")].append(candidate)

    for target_key, candidates in grouped_name_candidates.items():
        field = fields_by_key.get(target_key)
        if field is None or field.source.startswith("reviewer"):
            continue
        ordered = sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)
        field.correction_candidates = ordered[:5]
        top = ordered[0]
        candidate_confidence = float(top.get("confidence") or field.confidence)
        if candidate_confidence < 0.80:
            continue
        field.original_ocr_value = str(top.get("original_ocr_value") or field.original_ocr_value or field.value)
        field.corrected_value = str(top.get("suggested_value") or field.corrected_value or "")
        field.source_field_used = str(top.get("source_field_used") or "name_lexicon")
        field.correction_confidence = round(max(field.correction_confidence or 0, candidate_confidence), 2)
        field.audit_reason = str(top.get("audit_reason") or field.audit_reason or "")
        field.validation_message = field.audit_reason or field.validation_message

    grouped_address_candidates: dict[str, list[dict[str, object]]] = defaultdict(list)
    for candidate in analysis.get("address_candidates", []):
        if isinstance(candidate, dict):
            grouped_address_candidates[str(candidate.get("target_field") or "")].append(candidate)

    for target_key, candidates in grouped_address_candidates.items():
        field = fields_by_key.get(target_key)
        if field is None or field.source.startswith("reviewer"):
            continue
        ordered = sorted(candidates, key=lambda item: float(item.get("confidence") or 0), reverse=True)
        field.correction_candidates = [*field.correction_candidates, *ordered[:5]][:5]
        top = ordered[0]
        candidate_confidence = float(top.get("confidence") or field.confidence)
        if candidate_confidence < 0.80:
            continue
        field.original_ocr_value = str(top.get("original_ocr_value") or field.original_ocr_value or field.value)
        field.corrected_value = str(top.get("suggested_value") or field.corrected_value or "")
        field.source_field_used = str(top.get("source_field_used") or "address_intelligence")
        field.correction_confidence = round(max(field.correction_confidence or 0, candidate_confidence), 2)
        field.audit_reason = str(top.get("audit_reason") or field.audit_reason or "")
        field.validation_message = field.audit_reason or field.validation_message

    return analysis


def _correction_value(metadata: dict[str, object], key: str, fallback: str = "") -> str:
    value = metadata.get(key, fallback)
    return str(value or fallback)


def build_correction_memory(cases: Iterable[KycCase]) -> dict[str, object]:
    field_memory: defaultdict[str, Counter[str]] = defaultdict(Counter)
    document_type_memory: defaultdict[str, Counter[str]] = defaultdict(Counter)
    variant_memory: defaultdict[str, Counter[str]] = defaultdict(Counter)
    handwriting_fields: Counter[str] = Counter()
    correction_count = 0

    for case in cases:
        for event in case.audit_events:
            if event.action != "field_correction_recorded":
                continue
            metadata = event.metadata or {}
            correction_count += 1
            field_key = _correction_value(metadata, "field_key", "unknown")
            document_type = _correction_value(metadata, "document_type", "unknown")
            document_variant = _correction_value(metadata, "document_variant", f"{document_type}_unclassified_variant")
            block_type = _correction_value(metadata, "block_type")

            field_memory[field_key]["corrections"] += 1
            document_type_memory[document_type]["corrections"] += 1
            variant_memory[document_variant]["corrections"] += 1
            if block_type == "handwriting":
                handwriting_fields[field_key] += 1

    recommendations: list[str] = []
    if correction_count:
        most_common_fields = ", ".join(field for field, _ in Counter({k: v["corrections"] for k, v in field_memory.items()}).most_common(3))
        if most_common_fields:
            recommendations.append(f"Prioritize template and prompt tuning for corrected fields: {most_common_fields}.")
    if handwriting_fields:
        recommendations.append("Route corrected handwriting samples into a reviewed Nepali handwriting benchmark before model claims.")
    if variant_memory:
        recommendations.append("Review high-correction Nepal document variants before publishing template updates.")

    return {
        "correction_count": correction_count,
        "field_memory": {key: dict(value) for key, value in field_memory.items()},
        "document_type_memory": {key: dict(value) for key, value in document_type_memory.items()},
        "variant_memory": {key: dict(value) for key, value in variant_memory.items()},
        "layout_memory": {
            key: {
                "corrections": value["corrections"],
                "priority": "template_review" if value["corrections"] else "monitor",
            }
            for key, value in variant_memory.items()
        },
        "handwriting_memory": {
            "corrections": sum(handwriting_fields.values()),
            "fields": dict(handwriting_fields),
            "status": "benchmark_required" if handwriting_fields else "no_reviewed_handwriting_corrections",
        },
        "recommendations": recommendations,
    }
