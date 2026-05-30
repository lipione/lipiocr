import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import nepali_datetime

from app.models import EvidenceRef, ExtractedField, ReviewStatus, ValidationStatus


DEVANAGARI_DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९", "0123456789")
NEPALI_DIGITS = set("०१२३४५६७८९")
DATE_PATTERN = re.compile(
    r"(?P<year>[0-9०-९]{4})\s*[-/.]\s*(?P<month>[0-9०-९]{1,2})\s*[-/.]\s*(?P<day>[0-9०-९]{1,2})"
)
BS_CONTEXT_HINTS = (
    "वि.सं",
    "बि.सं",
    "विक्रम",
    "सम्बत",
    "साल",
    "मिति",
    "जन्म",
    "जारी",
    "गते",
)
DATE_KEY_HINTS = ("date", "dob", "birth", "issue", "expiry", "मिति")


@dataclass(frozen=True)
class CalendarConversion:
    calendar: str
    ad: str
    bs: str


def normalize_nepali_digits(value: str) -> str:
    return value.translate(DEVANAGARI_DIGIT_TRANSLATION)


def _format_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _has_nepali_digit(value: str) -> bool:
    return any(character in NEPALI_DIGITS for character in value)


def _looks_like_bs_date(original_value: str, context: str, year: int) -> bool:
    combined_context = f"{original_value} {context}"
    if _has_nepali_digit(original_value):
        return True
    if year >= 2040:
        return True
    return year >= 2000 and any(hint in combined_context for hint in BS_CONTEXT_HINTS)


def convert_calendar_date(value: str, context: str = "") -> Optional[CalendarConversion]:
    match = DATE_PATTERN.search(normalize_nepali_digits(value))
    if not match:
        return None

    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))

    try:
        if _looks_like_bs_date(value, context, year):
            bs_date = nepali_datetime.date(year, month, day)
            ad_date = bs_date.to_datetime_date()
            return CalendarConversion(
                calendar="bs",
                ad=ad_date.isoformat(),
                bs=_format_date(bs_date.year, bs_date.month, bs_date.day),
            )

        ad_date = date(year, month, day)
        bs_date = nepali_datetime.date.from_datetime_date(ad_date)
        return CalendarConversion(
            calendar="ad",
            ad=ad_date.isoformat(),
            bs=_format_date(bs_date.year, bs_date.month, bs_date.day),
        )
    except (ValueError, OverflowError):
        return None


def _is_calendar_variant_key(key: str) -> bool:
    return key.endswith("_ad") or key.endswith("_bs")


def _is_date_source_field(field: ExtractedField) -> bool:
    key = field.key.lower()
    if _is_calendar_variant_key(key):
        return False
    label = field.label.lower()
    return any(hint in key or hint in label for hint in DATE_KEY_HINTS)


def _context_for(field: ExtractedField) -> str:
    return " ".join(
        part
        for part in (field.key, field.label, field.evidence.evidence_text)
        if part
    )


def _calendar_label(label: str, calendar: str) -> str:
    base_label = re.sub(r"\s*\((?:AD|BS)\)\s*$", "", label, flags=re.IGNORECASE).strip()
    return f"{base_label} ({calendar.upper()})"


def _derived_review_status(source_field: ExtractedField) -> ReviewStatus:
    if source_field.review_status == ReviewStatus.verified or source_field.confidence >= 0.95:
        return ReviewStatus.verified
    return ReviewStatus.needs_review


def _derived_field(
    *,
    source_field: ExtractedField,
    key: str,
    value: str,
    label: str,
    document_id: Optional[str],
) -> ExtractedField:
    evidence = EvidenceRef(
        document_id=document_id or source_field.document_id or source_field.evidence.document_id,
        source_page=source_field.evidence.source_page,
        bbox=source_field.evidence.bbox,
        evidence_text=f"Converted from {source_field.label}: {source_field.value}",
        image_crop_uri=source_field.evidence.image_crop_uri,
    )
    return ExtractedField(
        key=key,
        label=label,
        value=value,
        confidence=round(source_field.confidence, 2),
        required=False,
        source="calendar_intelligence",
        validation_status=ValidationStatus.valid,
        validation_message="Converted between AD and BS by LipiCore.",
        bbox=source_field.bbox,
        evidence=evidence,
        extracted_by="LipiCore",
        review_status=_derived_review_status(source_field),
        document_id=document_id or source_field.document_id,
    )


def _upsert_calendar_variant(
    *,
    fields_by_key: dict[str, ExtractedField],
    fields: List[ExtractedField],
    source_field: ExtractedField,
    key: str,
    value: str,
    label: str,
    document_id: Optional[str],
) -> None:
    existing = fields_by_key.get(key)
    derived = _derived_field(
        source_field=source_field,
        key=key,
        value=value,
        label=label,
        document_id=document_id,
    )
    if existing is None:
        fields.append(derived)
        fields_by_key[key] = derived
        return

    existing.value = derived.value
    existing.confidence = derived.confidence
    existing.required = False
    existing.source = derived.source
    existing.validation_status = derived.validation_status
    existing.validation_message = derived.validation_message
    existing.bbox = derived.bbox
    existing.evidence = derived.evidence
    existing.extracted_by = derived.extracted_by
    existing.review_status = derived.review_status
    existing.document_id = derived.document_id


def apply_calendar_intelligence(
    fields: List[ExtractedField],
    *,
    document_id: Optional[str] = None,
) -> List[ExtractedField]:
    fields_by_key = {field.key: field for field in fields}
    source_fields = [field for field in fields if _is_date_source_field(field) and field.value.strip()]

    for source_field in source_fields:
        conversion = convert_calendar_date(source_field.value, context=_context_for(source_field))
        if conversion is None:
            continue

        _upsert_calendar_variant(
            fields_by_key=fields_by_key,
            fields=fields,
            source_field=source_field,
            key=f"{source_field.key}_ad",
            value=conversion.ad,
            label=_calendar_label(source_field.label, "ad"),
            document_id=document_id,
        )
        _upsert_calendar_variant(
            fields_by_key=fields_by_key,
            fields=fields,
            source_field=source_field,
            key=f"{source_field.key}_bs",
            value=conversion.bs,
            label=_calendar_label(source_field.label, "bs"),
            document_id=document_id,
        )

    return fields
