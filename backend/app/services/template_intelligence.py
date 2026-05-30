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
    LabelRule("dp_id", "DP ID", "number", True, "en", ("dp id", "depository participant")),
    LabelRule("client_id", "Client ID", "number", True, "en", ("client id", "client no")),
    LabelRule("full_name_en", "Full Name (English)", "name", True, "en", ("applicant's full name", "applicant full name", "full name", "name in english")),
    LabelRule("name_ne", "नाम", "name", True, "ne", ("नाम", "आवेदकको नाम")),
    LabelRule("father_name_en", "Father Name (English)", "name", False, "en", ("father's name", "father name")),
    LabelRule("father_name_ne", "बाबुको नाम", "name", False, "ne", ("बाबुको नाम", "बुवाको नाम")),
    LabelRule("grandfather_name_en", "Grandfather Name (English)", "name", False, "en", ("grandfather's name", "grandfather name")),
    LabelRule("address_en", "Address (English)", "address", True, "en", ("permanent address", "current address", "address in english", "address")),
    LabelRule("address_ne", "ठेगाना", "address", True, "ne", ("ठेगाना", "स्थायी ठेगाना", "हालको ठेगाना")),
    LabelRule("mobile", "Mobile No", "phone", True, "mixed", ("mobile no", "mobile", "phone no", "contact no", "सम्पर्क फोन")),
    LabelRule("email", "Email", "email", False, "en", ("email", "e-mail", "इमेल")),
    LabelRule("citizenship_number", "Citizenship Number", "number", True, "mixed", ("citizenship no", "citizenship number", "नागरिकता")),
    LabelRule("boid", "BOID", "number", False, "en", ("boid", "beneficiary account", "हितग्राही खाता")),
    LabelRule("bank_account_number", "Bank Account Number", "number", True, "mixed", ("bank account", "account number", "खाता नं")),
    LabelRule("amount", "Amount", "amount", False, "mixed", ("amount", "रकम", "rs.", "रु")),
    LabelRule("date", "Date", "date", False, "mixed", ("date", "मिति")),
    LabelRule("signature", "Signature", "signature", True, "mixed", ("signature", "दस्तखत", "हस्ताक्षर")),
    LabelRule("photo", "Photo", "photo", False, "mixed", ("photo", "फोटो")),
)


DOCUMENT_SIGNALS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.asba_application, ("asba", "dp id", "client id", "हितग्राही", "दरखास्त फारम", "nic asia")),
    (DocumentType.ipo_application, ("ipo", "share", "कित्ता", "शेयर")),
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
            text = _clean_label(block.text)
            if len(text) < 2:
                continue
            for rule in LABEL_RULES:
                matched_signal = _matched_signal(text, rule.signals)
                if not matched_signal:
                    continue
                identity = (rule.key, page.page_number)
                candidate = _field_from_rule(rule, page, block, matched_signal)
                previous = suggestions.get(identity)
                if previous is None or candidate.confidence > previous.confidence:
                    suggestions[identity] = candidate

    return sorted(suggestions.values(), key=lambda field: (field.page_number, field.bbox[1], field.bbox[0], field.key))


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
    bbox = _target_bbox(block.bbox, page)
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
    return "\n".join(block.text for page in pages for block in page.blocks).lower()


def _clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("：", ":").strip())


def _matched_signal(text: str, signals: tuple[str, ...]) -> str:
    normalized = text.lower()
    for signal in signals:
        if signal in normalized:
            return signal
    return ""


def _label_from_block(text: str, fallback: str) -> str:
    cleaned = _clean_label(text)
    label = re.split(r"[:=\-–]", cleaned, maxsplit=1)[0].strip()
    if not label or len(label) > 48:
        return fallback
    return label


def _target_bbox(bbox: list[int], page: TemplateProfilePage) -> list[int]:
    x1, y1, x2, y2 = (bbox + [0, 0, 0, 0])[:4]
    height = max(34, y2 - y1 + 16)
    if x2 + 120 < page.width:
        left = min(page.width - 80, max(x2 + 12, x1 + 120))
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
