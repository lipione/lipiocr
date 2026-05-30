from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

from app.models import DocumentType, EvidenceRef, ExtractedField, FinancialDocument, ReviewStatus, ValidationStatus
from app.services.calendar_intelligence import convert_calendar_date, normalize_nepali_digits
from app.services.validation import validate_field


DEVANAGARI_TEXT_RE = re.compile(r"[\u0900-\u097F]")
LABEL_VALUE_RE = re.compile(r"^\s*(?P<label>[^:：]{1,96})\s*[:：]\s*(?P<value>.+?)\s*$")


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


FIELD_ALIASES: tuple[dict[str, Any], ...] = (
    {"canonical_key": "full_name", "variant": "np", "aliases": ("नाम थर", "नाम", "आवेदकको नाम")},
    {
        "canonical_key": "full_name",
        "variant": "en",
        "aliases": ("full name", "applicant name", "applicant's full name", "name", "given name"),
    },
    {"canonical_key": "father_name", "variant": "np", "aliases": ("बाबुको नाम", "बुबाको नाम", "पिताको नाम")},
    {"canonical_key": "father_name", "variant": "en", "aliases": ("father name", "father's name")},
    {"canonical_key": "mother_name", "variant": "np", "aliases": ("आमाको नाम", "माताको नाम")},
    {"canonical_key": "mother_name", "variant": "en", "aliases": ("mother name", "mother's name")},
    {"canonical_key": "address", "variant": "np", "aliases": ("ठेगाना", "स्थायी वासस्थान", "स्थायी ठेगाना")},
    {"canonical_key": "address", "variant": "en", "aliases": ("address", "permanent address", "current address")},
    {"canonical_key": "dob", "kind": "date", "aliases": ("date of birth", "dob", "d.o.b", "जन्म मिति")},
    {"canonical_key": "issue_date", "kind": "date", "aliases": ("date of issue", "issue date", "जारी मिति")},
    {"canonical_key": "expiry_date", "kind": "date", "aliases": ("date of expiry", "expiry date", "date of expire")},
    {"canonical_key": "citizenship_number", "aliases": ("citizenship no", "citizenship number", "ना.प्र.नं", "ना प्र नं")},
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
    "address": "address",
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
        conversion = convert_calendar_date(value, context=context)
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
                identity = (output_key, value)
                if identity in seen:
                    continue
                seen.add(identity)

                observations.append(
                    FieldObservation(
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
                )

    return observations


def _canonical_fields(observations: list[FieldObservation]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for observation in observations:
        if observation.output_key not in fields:
            fields[observation.output_key] = observation.value
        public_alias = _public_field_alias(observation.output_key)
        if public_alias and public_alias not in fields:
            fields[public_alias] = observation.value

        if observation.canonical_key in {"dob", "issue_date", "expiry_date"}:
            conversion = convert_calendar_date(observation.value, context=observation.evidence_text)
            if conversion:
                fields[f"{observation.canonical_key}_ad"] = conversion.ad
                fields[f"{observation.canonical_key}_bs"] = conversion.bs
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


def _cross_checks(canonical_fields: dict[str, str], language_pairs: list[dict[str, object]]) -> list[dict[str, object]]:
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
    cross_checks = _cross_checks(canonical_fields, language_pairs)

    review_recommendations: list[str] = []
    if classification["confidence"] < 0.85:
        review_recommendations.append("Confirm document type before export.")
    if language_pairs:
        review_recommendations.append("Confirm Nepali and English field pairs before CBS/LOS ingestion.")
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
            }
            for observation in observations
        ],
        "canonical_fields": canonical_fields,
        "normalizations": normalizations,
        "language_pairs": language_pairs,
        "confidence_repairs": confidence_repairs,
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

    return analysis
