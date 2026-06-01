from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.models import DocumentType, OcrBlock, TemplateProfileField, TemplateProfilePage


@dataclass(frozen=True)
class LabelRule:
    key: str
    label: str
    field_type: str
    required: bool
    language_hint: str
    signals: tuple[str, ...]


LABEL_RULES: tuple[LabelRule, ...] = (
    LabelRule("application_number", "Application Number", "number", False, "mixed", ("application no", "application number", "form no", "serial no", "नि. व.", "नि. नं", "दर्ता नं")),
    LabelRule("dp_id", "DP ID", "number", True, "en", ("dp id", "depository participant")),
    LabelRule("client_id", "Client ID", "number", True, "en", ("client id", "client no")),
    LabelRule("applicant_name", "Applicant Name", "name", True, "mixed", ("applicant's full name", "applicant full name", "applicant's name", "applicant name", "आवेदकको नाम", "निवेदन गर्ने व्यक्तिको नाम")),
    LabelRule("full_name_en", "Full Name (English)", "name", True, "en", ("applicant's full name", "applicant full name", "full name", "name in english", "name (english)", "नाम (english)")),
    LabelRule("name_ne", "नाम", "name", True, "ne", ("नाम (नेपाली)", "नाम थर", "मेरो नाम", "आवेदकको नाम")),
    LabelRule("company_name", "Company Name", "text", False, "mixed", ("company's name", "company name", "संस्थाको नाम", "कम्पनीको नाम")),
    LabelRule("father_name_en", "Father Name (English)", "name", False, "en", ("father's name", "father name")),
    LabelRule("father_name_ne", "बाबुको नाम", "name", False, "ne", ("बाबुको नाम", "बुवाको नाम")),
    LabelRule("grandfather_name_en", "Grandfather Name (English)", "name", False, "en", ("grandfather's name", "grandfather name", "हजुरबुवाको नाम", "बाजेको नाम")),
    LabelRule("spouse_name_en", "Spouse Name (English)", "name", False, "en", ("spouse name", "husband/wife name", "पति/पत्नीको नाम", "पति पत्नीको नाम")),
    LabelRule("address_en", "Address (English)", "address", True, "en", ("permanent address", "current address", "address in english", "address")),
    LabelRule("address_ne", "ठेगाना", "address", True, "ne", ("ठेगाना", "स्थायी ठेगाना", "हालको ठेगाना")),
    LabelRule("mobile", "Mobile No", "phone", True, "mixed", ("mobile no", "mobile", "phone no", "contact no", "सम्पर्क फोन")),
    LabelRule("email", "Email", "email", False, "en", ("email", "e-mail", "इमेल")),
    LabelRule("pan", "PAN", "number", False, "mixed", ("pan no", "pan", "प्यान")),
    LabelRule("citizenship_number", "Citizenship Number", "number", True, "mixed", ("citizenship no", "citizenship number", "नागरिकता")),
    LabelRule("boid", "BOID", "number", False, "en", ("boid", "beneficiary account", "हितग्राही खाता")),
    LabelRule("bank_name", "Bank Name", "text", False, "mixed", ("bank name", "बैंकको नाम", "बैंक नाम")),
    LabelRule("bank_account_number", "Bank Account Number", "number", True, "mixed", ("bank account", "account number", "खाता नं")),
    LabelRule("applied_units", "Applied Units", "number", True, "mixed", ("no. of share applied", "share applied", "applied units", "कित्ता")),
    LabelRule("call_money_per_share", "Call Money Per Share", "amount", False, "mixed", ("call money per share", "money per share")),
    LabelRule("amount_words", "Amount in Words", "amount", False, "mixed", ("amount in words", "अक्षरेपी")),
    LabelRule("amount", "Amount", "amount", False, "mixed", ("amount deposited", "amount", "रकम", "rs.", "रु")),
    LabelRule("date", "Date", "date", False, "mixed", ("date", "मिति")),
    LabelRule("signature", "Signature", "signature", True, "mixed", ("signature", "दस्तखत", "हस्ताक्षर")),
    LabelRule("photo", "Photo", "photo", False, "mixed", ("photo", "फोटो")),
)


DOCUMENT_SIGNALS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.asba_application, ("asba", "c-asba", "dp id", "client id", "हितग्राही खाता", "nic asia", "nic-bank", "nic bank")),
    (DocumentType.ipo_application, ("ipo", "share", "no. of share applied", "कित्ता", "शेयर", "सेयर", "शेयर खरिद", "सेयर खरिद")),
    (DocumentType.citizenship, ("citizenship", "नागरिकता", "जिल्ला प्रशासन")),
    (DocumentType.national_id, ("national identity", "national id", "राष्ट्रिय परिचयपत्र")),
    (DocumentType.passport, ("passport", " राहदानी", "mrz")),
    (DocumentType.driving_license, ("driving licence", "driving license", "license office", "सवारी चालक")),
    (DocumentType.account_opening, ("account opening", "account type", "nominee", "खाता खोल्ने")),
)


def infer_template_document_type(
    pages: Iterable[TemplateProfilePage],
    declared_type: DocumentType,
) -> tuple[DocumentType, float, str]:
    if declared_type != DocumentType.unknown:
        return declared_type, 1.0, "Document family selected by operator."

    corpus = _page_corpus(pages)
    scores: list[tuple[int, DocumentType, list[str]]] = []
    for document_type, signals in DOCUMENT_SIGNALS:
        matched = [signal for signal in signals if signal in corpus]
        if matched:
            scores.append((len(matched), document_type, matched))

    if not scores:
        return DocumentType.unknown, 0.0, "No strong template document signal found."

    scores.sort(key=lambda item: (-item[0], item[1].value))
    score, document_type, matched = scores[0]
    confidence = min(0.98, round(0.55 + (score * 0.09), 2))
    return document_type, confidence, f"Detected {document_type.value} from labels: {', '.join(matched[:4])}."


def suggest_label_fields(pages: Iterable[TemplateProfilePage]) -> list[TemplateProfileField]:
    suggestions: dict[tuple[str, int], TemplateProfileField] = {}
    for page in pages:
        for block in page.blocks:
            if block.block_type in {"handwriting", "field_candidate"}:
                continue
            text = _clean_label(block.text)
            if len(text) < 2:
                continue
            for rule in LABEL_RULES:
                if _is_non_template_header_contact(rule, page, block, text):
                    continue
                matched_signal = _matched_signal(text, rule.signals)
                if not matched_signal:
                    continue
                identity = (rule.key, page.page_number)
                candidate = _field_from_rule(rule, page, block, matched_signal)
                previous = suggestions.get(identity)
                if previous is None or candidate.confidence > previous.confidence:
                    suggestions[identity] = candidate

    return sorted(suggestions.values(), key=lambda field: (field.page_number, field.bbox[1], field.bbox[0], field.key))


ASBA_LAYOUT_PRESET: tuple[tuple[str, str, str, bool, str, list[int]], ...] = (
    ("applied_units", "Applied Units", "number", True, "mixed", [141, 168, 176, 221]),
    ("amount", "Amount", "amount", False, "mixed", [256, 168, 335, 221]),
    ("bank_name", "Bank Name", "text", False, "mixed", [385, 168, 520, 221]),
    ("dp_id", "DP ID", "number", True, "en", [536, 174, 609, 199]),
    ("client_id", "Client ID", "number", True, "en", [536, 199, 609, 223]),
    ("name_ne", "Applicant Name (Nepali)", "name", True, "ne", [116, 267, 360, 294]),
    ("full_name_en", "Applicant Name (English)", "name", True, "en", [150, 295, 526, 323]),
    ("address_ne", "Permanent Address (Nepali)", "address", True, "ne", [145, 333, 674, 361]),
    ("address_en", "Permanent Address (English)", "address", True, "en", [145, 365, 674, 392]),
    ("current_address_ne", "Current Address (Nepali)", "address", False, "ne", [145, 398, 674, 425]),
    ("current_address_en", "Current Address (English)", "address", False, "en", [145, 429, 674, 456]),
    ("father_name_ne", "Father Name (Nepali)", "name", False, "ne", [145, 462, 368, 489]),
    ("father_name_en", "Father Name (English)", "name", False, "en", [455, 462, 674, 489]),
    ("grandfather_name_ne", "Grandfather Name (Nepali)", "name", False, "ne", [145, 489, 368, 516]),
    ("grandfather_name_en", "Grandfather Name (English)", "name", False, "en", [455, 489, 674, 516]),
    ("citizenship_number", "Citizenship Number", "number", True, "mixed", [108, 523, 254, 551]),
    ("date", "Citizenship Issue Date", "date", False, "mixed", [474, 523, 636, 551]),
    ("phone", "Phone Number", "phone", False, "mixed", [103, 573, 229, 599]),
    ("mobile", "Mobile Number", "phone", True, "mixed", [281, 573, 408, 599]),
    ("email", "Email", "email", False, "en", [454, 573, 651, 599]),
    ("signature", "Applicant Signature", "signature", True, "mixed", [568, 688, 678, 745]),
)


def suggest_preset_fields(
    pages: Iterable[TemplateProfilePage],
    document_type: DocumentType,
) -> list[TemplateProfileField]:
    if document_type != DocumentType.asba_application:
        return []

    fields: list[TemplateProfileField] = []
    for page in pages:
        corpus = (f"{page.filename} " + " ".join(block.text for block in page.blocks)).lower()
        if (
            "nic asia" not in corpus
            and "nic-bank" not in corpus
            and "nic bank" not in corpus
            and "asba" not in corpus
            and "हितग्राही" not in corpus
        ):
            continue
        for key, label, field_type, required, language_hint, bbox in ASBA_LAYOUT_PRESET:
            fields.append(
                TemplateProfileField(
                    key=key,
                    label=label,
                    page_number=page.page_number,
                    bbox=_scale_bbox(bbox, page, base_width=714, base_height=1024),
                    type=field_type,
                    required=required,
                    language_hint=language_hint,
                    extraction_hint="Use ASBA form layout preset; adjust in canvas if this institution revision differs.",
                    confidence=0.74,
                    detection_source="layout_preset",
                    detection_reason="Applied Nepal ASBA/NIC-style layout preset because OCR labels were weak or incomplete.",
                )
            )
    return fields


def score_template_quality(fields: Iterable[TemplateProfileField], pages: Iterable[TemplateProfilePage]) -> tuple[float, list[dict[str, object]]]:
    field_list = list(fields)
    page_list = list(pages)
    page_numbers = {page.page_number for page in page_list}
    mapped_pages = {field.page_number for field in field_list}
    required_count = sum(1 for field in field_list if field.required)
    average_confidence = round(sum(field.confidence for field in field_list) / len(field_list), 4) if field_list else 0.0
    page_coverage = round(len(mapped_pages.intersection(page_numbers)) / len(page_numbers), 4) if page_numbers else 0.0
    field_depth = min(len(field_list) / 8, 1.0)
    required_depth = min(required_count / 5, 1.0)
    score = round((field_depth * 0.3) + (required_depth * 0.25) + (average_confidence * 0.3) + (page_coverage * 0.15), 2)
    checks = [
        _quality_check("field_depth", len(field_list) >= 4, f"{len(field_list)} fields detected"),
        _quality_check("required_fields", required_count >= 2, f"{required_count} required fields marked"),
        _quality_check("page_coverage", page_coverage >= 0.8 if page_numbers else False, f"{int(page_coverage * 100)}% page coverage"),
        _quality_check("average_confidence", average_confidence >= 0.65, f"{int(average_confidence * 100)}% average mapping confidence"),
    ]
    return score, checks


def _field_from_rule(rule: LabelRule, page: TemplateProfilePage, block: OcrBlock, matched_signal: str) -> TemplateProfileField:
    bbox = _target_bbox(rule, block, page)
    label = _label_from_block(block.text, rule.label)
    confidence = min(0.95, round(max(block.confidence, 0.62) + 0.12, 2))
    return TemplateProfileField(
        key=rule.key,
        label=label,
        page_number=page.page_number,
        bbox=bbox,
        type=rule.field_type,
        required=rule.required,
        language_hint=rule.language_hint,
        extraction_hint=f"Use printed label near '{_clean_label(block.text)}'.",
        confidence=confidence,
        detection_source="label_intelligence",
        detection_reason=f"Matched label signal '{matched_signal}' in '{_clean_label(block.text)}'.",
    )


def _page_corpus(pages: Iterable[TemplateProfilePage]) -> str:
    return "\n".join(
        [page.filename for page in pages] + [block.text for page in pages for block in page.blocks]
    ).lower()


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("：", ":").strip())


def _matched_signal(text: str, signals: tuple[str, ...]) -> str:
    normalized = text.lower()
    for signal in signals:
        if signal in normalized:
            return signal
    return ""


def _scale_bbox(bbox: list[int], page: TemplateProfilePage, *, base_width: int, base_height: int) -> list[int]:
    x_scale = page.width / base_width if base_width else 1
    y_scale = page.height / base_height if base_height else 1
    return [
        int(round(bbox[0] * x_scale)),
        int(round(bbox[1] * y_scale)),
        int(round(bbox[2] * x_scale)),
        int(round(bbox[3] * y_scale)),
    ]


def _is_known_label_text(text: str) -> bool:
    normalized = _clean_label(text).lower()
    if not normalized:
        return False
    return any(signal in normalized for rule in LABEL_RULES for signal in rule.signals)


def _block_center_y(block: OcrBlock) -> float:
    return (block.bbox[1] + block.bbox[3]) / 2


def _block_overlaps_label_row(label: OcrBlock, candidate: OcrBlock) -> bool:
    label_height = max(1, label.bbox[3] - label.bbox[1])
    row_tolerance = max(12, label_height * 0.9)
    return abs(_block_center_y(candidate) - _block_center_y(label)) <= row_tolerance


def _is_writable_value_block(block: OcrBlock) -> bool:
    if block.block_type in {"field_candidate"}:
        return False
    if block.block_type == "handwriting":
        return True
    return not _is_known_label_text(block.text)


def _row_boundary_x(rule: LabelRule, page: TemplateProfilePage, label_block: OcrBlock) -> int | None:
    if rule.field_type == "address":
        return None
    boundaries = [
        block.bbox[0]
        for block in page.blocks
        if block is not label_block
        and block.block_type not in {"handwriting", "field_candidate"}
        and block.bbox[0] > label_block.bbox[2] + 16
        and _block_overlaps_label_row(label_block, block)
        and _is_known_label_text(block.text)
    ]
    return min(boundaries) if boundaries else None


def _linked_writable_bbox(rule: LabelRule, page: TemplateProfilePage, label_block: OcrBlock) -> list[int] | None:
    x1, y1, x2, y2 = label_block.bbox[:4]
    boundary_x = _row_boundary_x(rule, page, label_block)
    candidates = [
        block
        for block in page.blocks
        if block is not label_block
        and block.bbox[0] >= x2 - 2
        and _block_overlaps_label_row(label_block, block)
        and _is_writable_value_block(block)
        and (boundary_x is None or block.bbox[0] < boundary_x - 4)
    ]
    if not candidates:
        return None

    left = min(block.bbox[0] for block in candidates)
    right = max(block.bbox[2] for block in candidates)
    top = min(block.bbox[1] for block in candidates)
    bottom = max(block.bbox[3] for block in candidates)

    if boundary_x is not None:
        if left - x2 > 120:
            left = x2 + 12
        right = max(right, boundary_x - 8)
    elif rule.field_type == "address":
        left = min(left, x2 + 12)

    return [
        int(max(0, left)),
        int(max(0, top - 4)),
        int(min(page.width, right)),
        int(min(page.height, bottom + 4)),
    ]


def _is_non_template_header_contact(rule: LabelRule, page: TemplateProfilePage, block: OcrBlock, text: str) -> bool:
    if rule.key != "email":
        return False
    y1 = block.bbox[1] if len(block.bbox) >= 2 else 0
    if y1 > int(page.height * 0.35):
        return False
    normalized = text.lower()
    return bool(re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", normalized))


def _label_from_block(text: str, fallback: str) -> str:
    cleaned = _clean_label(text)
    label = re.split(r"[:=–]|\s+-\s+", cleaned, maxsplit=1)[0].strip()
    if not label or len(label) > 48:
        return fallback
    return label


def _target_bbox(rule: LabelRule, block: OcrBlock, page: TemplateProfilePage) -> list[int]:
    linked = _linked_writable_bbox(rule, page, block)
    if linked:
        return linked

    x1, y1, x2, y2 = (block.bbox + [0, 0, 0, 0])[:4]
    height = max(34, y2 - y1 + 16)
    if x2 + 120 < page.width:
        label_width = max(0, x2 - x1)
        label_offset = 120 if label_width >= 120 else label_width + 12
        left = min(page.width - 80, max(x2 + 12, x1 + label_offset))
        right = min(page.width - 32, left + max(220, int(page.width * 0.34)))
    else:
        left = max(24, x1)
        right = min(page.width - 32, max(x2, left + 240))
    top = max(0, y1 - 6)
    bottom = min(page.height, top + height)
    return [int(left), int(top), int(right), int(bottom)]


def _quality_check(key: str, passed: bool, detail: str) -> dict[str, object]:
    return {
        "key": key,
        "status": "pass" if passed else "needs_review",
        "detail": detail,
    }
