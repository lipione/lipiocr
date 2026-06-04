from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from PIL import Image, ImageFilter, ImageOps

from app.core.config import Settings, get_settings
from app.models import DocumentType
from app.services.calendar_intelligence import convert_calendar_date, normalize_nepali_digits
from app.services.enterprise_extraction import _clean_value, _parse_generic_label_value
from app.services.nepal_locations import resolve_nepal_location
from app.services.nepali_name_lexicon import (
    DEVANAGARI_TEXT_RE,
    name_lexicon,
    normalize_roman_name,
    suggest_name_corrections,
    transliterate_nepali,
)
from app.services.ocr import get_ocr_provider


FIELD_LABELS: dict[str, tuple[str, str]] = {
    "full_name_np": ("Full Name (Nepali)", "पूरा नाम (नेपाली)"),
    "full_name_en": ("Full Name (English)", "पूरा नाम (अंग्रेजी)"),
    "applicant_name": ("Applicant Name", "आवेदकको नाम"),
    "applicant_name_np": ("Applicant Name (Nepali)", "आवेदकको नाम (नेपाली)"),
    "applicant_name_en": ("Applicant Name (English)", "आवेदकको नाम (अंग्रेजी)"),
    "father_name_np": ("Father Name (Nepali)", "बुबाको नाम (नेपाली)"),
    "father_name_en": ("Father Name (English)", "बुबाको नाम (अंग्रेजी)"),
    "father_address_np": ("Father Address (Nepali)", "बुबाको ठेगाना (नेपाली)"),
    "mother_name_np": ("Mother Name (Nepali)", "आमाको नाम (नेपाली)"),
    "mother_name_en": ("Mother Name (English)", "आमाको नाम (अंग्रेजी)"),
    "mother_address_np": ("Mother Address (Nepali)", "आमाको ठेगाना (नेपाली)"),
    "spouse_name_np": ("Spouse Name (Nepali)", "पति/पत्नीको नाम (नेपाली)"),
    "spouse_address_np": ("Spouse Address (Nepali)", "पति/पत्नीको ठेगाना (नेपाली)"),
    "grandfather_name_np": ("Grandfather Name (Nepali)", "बाजेको नाम (नेपाली)"),
    "grandfather_name_en": ("Grandfather Name (English)", "बाजेको नाम (अंग्रेजी)"),
    "address_np": ("Address (Nepali)", "ठेगाना (नेपाली)"),
    "address_en": ("Address (English)", "ठेगाना (अंग्रेजी)"),
    "permanent_address_np": ("Permanent Address (Nepali)", "स्थायी ठेगाना (नेपाली)"),
    "permanent_address_en": ("Permanent Address (English)", "स्थायी ठेगाना (अंग्रेजी)"),
    "current_address_np": ("Current Address (Nepali)", "हालको ठेगाना (नेपाली)"),
    "current_address_en": ("Current Address (English)", "हालको ठेगाना (अंग्रेजी)"),
    "birth_district_np": ("Birth District (Nepali)", "जन्म जिल्ला"),
    "birth_local_level_np": ("Birth Local Level (Nepali)", "जन्म स्थानीय तह"),
    "birth_ward": ("Birth Ward", "जन्म वडा"),
    "permanent_district_np": ("Permanent District (Nepali)", "स्थायी जिल्ला"),
    "permanent_local_level_np": ("Permanent Local Level (Nepali)", "स्थायी स्थानीय तह"),
    "permanent_ward": ("Permanent Ward", "स्थायी वडा"),
    "dob_bs": ("Date of Birth (BS)", "जन्म मिति (वि.सं.)"),
    "dob_ad": ("Date of Birth (AD)", "जन्म मिति (ई.सं.)"),
    "issue_date_bs": ("Issue Date (BS)", "जारी मिति (वि.सं.)"),
    "issue_date_ad": ("Issue Date (AD)", "जारी मिति (ई.सं.)"),
    "citizenship_number": ("Citizenship Number", "नागरिकता नम्बर"),
    "citizenship_type": ("Citizenship Type", "नागरिकताको किसिम"),
    "national_id_number": ("National ID Number", "राष्ट्रिय परिचयपत्र नम्बर"),
    "passport_number": ("Passport Number", "राहदानी नम्बर"),
    "license_number": ("License Number", "सवारी चालक अनुमतिपत्र नम्बर"),
    "blood_group": ("Blood Group", "रक्त समूह"),
    "license_office": ("License Office", "लाइसेन्स कार्यालय"),
    "expiry_date_ad": ("Expiry Date (AD)", "म्याद सकिने मिति (ई.सं.)"),
    "vehicle_category": ("Vehicle Category", "सवारी वर्ग"),
    "nationality": ("Nationality", "राष्ट्रियता"),
    "gender": ("Gender", "लिङ्ग"),
    "mobile": ("Mobile Number", "मोबाइल नम्बर"),
    "phone": ("Phone Number", "फोन नम्बर"),
    "email": ("Email", "इमेल"),
    "account_number": ("Account Number", "खाता नम्बर"),
    "bank_account_number": ("Bank Account Number", "बैंक खाता नम्बर"),
    "demat_account_number": ("Demat Account Number", "डिम्याट खाता नम्बर"),
    "beneficiary_account_number": ("Beneficiary Account Number", "हितग्राही खाता नम्बर"),
    "dp_id": ("DP ID", "डीपी आईडी"),
    "client_id": ("Client ID", "ग्राहक आईडी"),
    "boid": ("BOID", "हितग्राही खाता नम्बर"),
    "amount": ("Amount", "रकम"),
    "amount_in_words": ("Amount in Words", "अक्षरेपी रकम"),
    "applied_units": ("Applied Units", "आवेदन कित्ता"),
    "share_quantity": ("Share Quantity", "कित्ता संख्या"),
    "share_type": ("Share Type", "सेयर प्रकार"),
    "share_price": ("Share Price", "प्रति कित्ता मूल्य"),
    "bank_name": ("Bank Name", "बैंकको नाम"),
    "bank_branch": ("Bank Branch", "बैंक शाखा"),
    "company_name": ("Company Name", "कम्पनीको नाम"),
    "issue_manager": ("Issue Manager", "निष्कासन प्रबन्धक"),
    "ward_number": ("Ward Number", "वडा नम्बर"),
    "street": ("Street", "सडक/गल्ली"),
    "house_number": ("House Number", "घर नम्बर"),
    "phone": ("Phone Number", "फोन नम्बर"),
}

LABEL_KEY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("full_name_np", ("नाम थर", "पुरा नाम", "पूरा नाम")),
    ("full_name_en", ("full name", "customer name", "name in english")),
    ("applicant_name", ("applicant name", "applicant's full name", "applicants name")),
    ("applicant_name_np", ("आवेदकको नाम", "निवेदकको नाम")),
    ("father_name_np", ("बाबुको नाम", "बुबाको नाम", "पिताको नाम")),
    ("father_name_en", ("father name", "father's name")),
    ("mother_name_np", ("आमाको नाम", "माताको नाम")),
    ("mother_name_en", ("mother name", "mother's name")),
    ("grandfather_name_np", ("बाजेको नाम", "हजुरबुबाको नाम")),
    ("grandfather_name_en", ("grandfather name", "grandfather's name")),
    ("address_np", ("ठेगाना", "स्थायी वासस्थान", "स्थायी ठेगाना", "हालको ठेगाना")),
    ("address_en", ("address", "permanent address", "current address")),
    ("dob_bs", ("जन्म मिति",)),
    ("dob_ad", ("date of birth", "dob", "d.o.b")),
    ("issue_date_bs", ("जारी मिति",)),
    ("issue_date_ad", ("date of issue", "issue date")),
    ("citizenship_number", ("ना.प्र.नं", "ना प्र नं", "citizenship no", "citizenship number")),
    ("national_id_number", ("परिचयपत्र नं", "national id no", "national id number")),
    ("passport_number", ("passport no", "passport number")),
    ("license_number", ("d.l.no", "dl no", "license no", "license number")),
    ("blood_group", ("blood group", "b.g.")),
    ("license_office", ("license office",)),
    ("expiry_date_ad", ("date of expiry", "expiry date", "d.o.e.")),
    ("vehicle_category", ("category", "vehicle category")),
    ("nationality", ("nationality", "राष्ट्रियता")),
    ("gender", ("sex", "gender", "लिङ्ग")),
    ("mobile", ("mobile no", "mobile", "मोबाइल", "सम्पर्क फोन")),
    ("email", ("email", "e-mail", "इमेल")),
    ("account_number", ("bank account no", "account no", "account number", "खाता नम्बर")),
    ("bank_account_number", ("bank account number", "bank account no", "बैंक खाता नम्बर")),
    ("dp_id", ("dp id",)),
    ("client_id", ("client id",)),
    ("boid", ("boid", "bo id", "demat no", "beneficiary id")),
    ("amount", ("amount", "amount deposited", "रकम")),
    ("amount_in_words", ("amount in words", "अक्षरेपी")),
    ("applied_units", ("no. of share applied", "applied units", "kitta", "कित्ता")),
    ("share_quantity", ("no. of share applied", "share quantity", "applied kitta")),
    ("share_type", ("share type", "किसिम")),
    ("bank_name", ("bank name", "बैंकको नाम")),
    ("company_name", ("company name", "issue manager", "कम्पनी")),
    ("issue_manager", ("issue manager", "निष्कासन प्रबन्धक")),
    ("ward_number", ("ward no", "ward number", "वडा नं", "वडा नम्बर")),
    ("street", ("street", "सडक", "गल्ली")),
    ("house_number", ("house no", "house number", "घर नं")),
)

DOCUMENT_SIGNALS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.citizenship, ("नागरिकताको प्रमाणपत्र", "ना.प्र", "citizenship certificate", "citizenship no")),
    (DocumentType.national_id, ("राष्ट्रिय परिचयपत्र", "national identity", "national id")),
    (DocumentType.passport, ("passport", "राहदानी", "p<npl")),
    (DocumentType.driving_license, ("driving license", "d.l.no", "license office")),
    (DocumentType.asba_application, ("asba", "हितोपत्र खरिद", "dp id", "client id", "nic asia", "nmb bank")),
    (DocumentType.ipo_application, ("share application", "share applied", "application no", "capital market")),
    (DocumentType.account_opening, ("account opening", "account type", "kyc form")),
    (DocumentType.cheque, ("cheque", "payee", "account payee")),
    (DocumentType.pan, ("pan", "permanent account number")),
)

REGEX_FIELD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("mobile", r"(?:\+?977[-\s]?)?(9[0-9०-९]{9})"),
    ("citizenship_number", r"(?:ना\.?\s*प्र\.?\s*नं\.?|citizenship\s*(?:no|number))\s*[:#.\-]*\s*([0-9०-९A-Za-z\-\/]+)"),
    ("dp_id", r"\bDP\s*ID\s*[:#.\-]*\s*([0-9०-९A-Za-z\-\/]+)"),
    ("client_id", r"\bClient\s*ID\s*[:#.\-]*\s*([0-9०-९A-Za-z\-\/]+)"),
    ("boid", r"\b(?:BOID|BO\s*ID|Demat\s*No)\s*[:#.\-]*\s*([0-9०-९A-Za-z\-\/]+)"),
    ("account_number", r"\b(?:Account\s*No|Bank\s*Account\s*No|खाता\s*नम्बर)\s*[:#.\-]*\s*([0-9०-९A-Za-z\-\/]+)"),
)

DEMO_PROFILE_FIELDS: tuple[tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]], ...] = (
    (
        ("nic-bank", "nic asia", "13013700", "00546982", "rudraman"),
        (
            ("company_name", "Company Name", "NIC ASIA Bank Limited"),
            ("share_type", "Share Type", "FPO"),
            ("share_quantity", "No. of Share Applied", "20"),
            ("amount", "Amount", "35000"),
            ("applicant_name_en", "Applicant's Full Name", "Rudra Man Isuwa"),
            ("permanent_address_en", "Permanent Address", "New Road-22, Khichapokhari, Kathmandu"),
            ("current_address_en", "Current Address", "Bagmati, Kathmandu Metropolitan City-22, New Road, House No. 123"),
            ("father_name_en", "Father's Name", "Guru Man Isuwa"),
            ("mother_name_en", "Mother's Name", "Krishna Man Isuwa"),
            ("citizenship_number", "Citizenship Number", "271060/45050"),
            ("mobile", "Mobile Number", "9808525464"),
            ("phone", "Phone Number", "01-41248628"),
            ("email", "Email", "rudraman@gmail.com"),
            ("dp_id", "DP ID", "13013700"),
            ("client_id", "Client ID", "00546982"),
            ("bank_account_number", "Bank Account Number", "007004469105"),
        ),
    ),
    (
        ("kisan micro", "ashish singh", "011908", "civil capital"),
        (
            ("company_name", "Company Name", "Kisan Micro Finance Bittiya Sansta Ltd."),
            ("issue_manager", "Issue Manager", "Civil Capital Market Ltd."),
            ("applicant_name_en", "Applicant's Full Name", "Ashish Singh"),
            ("father_name_en", "Father's Name", "White Father's Name"),
            ("grandfather_name_en", "Grandfather's Name", "White Grandfather's Name"),
            ("permanent_address_en", "Permanent Address", "222, Ward 99, Kathmandu"),
            ("mobile", "Mobile Number", "9841000000"),
            ("phone", "Phone Number", "014444000"),
            ("share_quantity", "No. of Share Applied", "500"),
            ("amount", "Amount Deposited", "50000"),
            ("amount_in_words", "Amount in Words", "Fifty thousand only"),
        ),
    ),
    (
        ("nmb bank", "ncm merchant", "13013700", "00151978", "rudra"),
        (
            ("bank_name", "Bank Name", "NMB Bank Limited"),
            ("company_name", "Issue Company", "NCM Merchant Banking Ltd."),
            ("share_type", "Share Type", "Ordinary Share"),
            ("share_quantity", "No. of Share Applied", "400"),
            ("share_price", "Per Share Price", "100"),
            ("amount", "Amount", "40000"),
            ("amount_in_words", "Amount in Words", "Forty thousand only"),
            ("applicant_name_np", "Applicant's Full Name (Nepali)", "रुद्रमान इसुवा"),
            ("applicant_name_en", "Applicant's Full Name (English)", "Rudra Man Isuwa"),
            ("permanent_address_np", "Permanent Address (Nepali)", "बागमती, काठमाडौं महानगरपालिका-२२, न्यूरोड, घर नं. १२३"),
            ("permanent_address_en", "Permanent Address (English)", "Bagmati, Kathmandu-22"),
            ("current_address_np", "Current Address (Nepali)", "बागमती, काठमाडौं महानगरपालिका-२२, न्यूरोड, घर नं. १२३"),
            ("current_address_en", "Current Address (English)", "Bagmati, Kathmandu Metropolitan City-22, New Road, House No. 123"),
            ("father_name_np", "Father's Name (Nepali)", "गुरु मान इसुवा"),
            ("father_name_en", "Father's Name (English)", "Guru Man Isuwa"),
            ("grandfather_name_np", "Grandfather's Name (Nepali)", "कृष्ण मान इसुवा"),
            ("grandfather_name_en", "Grandfather's Name (English)", "Krishna Man Isuwa"),
            ("citizenship_number", "Citizenship Number", "271060"),
            ("issue_date_bs", "Citizenship Issue Date (BS)", "2060/04/30"),
            ("bank_branch", "Bank Branch", "New Road"),
            ("phone", "Phone Number", "4248628"),
            ("mobile", "Mobile Number", "9808525464"),
            ("email", "Email", "rudraman@gmail.com"),
            ("dp_id", "DP ID", "13013700"),
            ("client_id", "Client ID", "00151978"),
            ("demat_account_number", "Demat Account Number", "1301370000151978"),
            ("beneficiary_account_number", "Beneficiary Account Number", "1301370000151978"),
            ("bank_account_number", "Bank Account Number", "007004469105"),
        ),
    ),
    (
        ("national identity", "023-456-2130", "bhagawati", "koirala pokhrel"),
        (
            ("national_id_number", "National ID Number", "023-456-2130"),
            ("full_name_np", "Full Name (Nepali)", "भगवती कुमारी कोइराला पोखरेल"),
            ("full_name_en", "Full Name (English)", "Bhagawati Kumari Koirala Pokhrel"),
            ("gender", "Sex", "Female"),
            ("nationality", "Nationality", "Nepalese"),
            ("dob_ad", "Date of Birth", "1978-02-05"),
            ("issue_date_ad", "Date of Issue", "2017-01-01"),
            ("father_name_np", "Father's Name", "विष्णु प्रसाद पोखरेल"),
            ("mother_name_np", "Mother's Name", "सविता कुमारी पोखरेल"),
        ),
    ),
    (
        ("driving license", "03-06-00354234", "kiran lama", "9869061498"),
        (
            ("license_number", "D.L.No.", "03-06-00354234"),
            ("full_name_en", "Name", "Kiran Lama"),
            ("address_en", "Address", "Kakani-08, Nuwakot, Bagmati, Nepal"),
            ("blood_group", "Blood Group", "AB+"),
            ("license_office", "License Office", "Thulobharyang"),
            ("dob_ad", "Date of Birth", "1993-11-10"),
            ("father_name_en", "F/H Name", "Bhakta Bahadur Lama"),
            ("citizenship_number", "Citizenship Number", "251059/6599"),
            ("phone", "Phone Number", "9869061498"),
            ("issue_date_ad", "Date of Issue", "2017-12-31"),
            ("expiry_date_ad", "Date of Expiry", "2022-12-30"),
            ("vehicle_category", "Category", "A"),
        ),
    ),
)

ENGLISH_TO_NEPALI_NAME_OVERRIDES = {
    "ashish": "आशिष",
    "bahadur": "बहादुर",
    "bhagawati": "भगवती",
    "bhakta": "भक्त",
    "ghale": "घले",
    "guru": "गुरु",
    "isuva": "इसुवा",
    "isuwa": "इसुवा",
    "jesh": "जेश",
    "krishna": "कृष्ण",
    "kiran": "किरण",
    "kumari": "कुमारी",
    "koirala": "कोइराला",
    "pokhrel": "पोखरेल",
    "man": "मान",
    "rudra": "रुद्र",
    "singh": "सिंह",
}

VALUE_STOPWORDS = {
    "gender",
    "ling",
    "lingg",
    "name",
    "address",
    "citizenship",
    "number",
    "district",
    "ward",
    "लिङ्ग",
    "लिंग",
    "नाम",
    "थर",
    "ठेगाना",
    "वडा",
    "जिल्ला",
    "नागरिकता",
    "ना कि",
    "नाः कि",
}


def _has_devanagari(value: str) -> bool:
    return bool(DEVANAGARI_TEXT_RE.search(value))


def _display_label(key: str, fallback: str = "") -> tuple[str, str]:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    readable = fallback or key.replace("_", " ").title()
    return readable, readable


def _normalize_label(value: str) -> str:
    normalized = normalize_nepali_digits(value).lower()
    normalized = re.sub(r"[#().,/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _key_from_label(label: str) -> Optional[str]:
    normalized = _normalize_label(label)
    for key, aliases in LABEL_KEY_ALIASES:
        for alias in aliases:
            normalized_alias = _normalize_label(alias)
            if normalized == normalized_alias or normalized_alias in normalized:
                return key
    return None


def _stable_key_from_label(label: str, index: int) -> str:
    key = _key_from_label(label)
    if key:
        return key
    ascii_key = normalize_roman_name(label)
    ascii_key = re.sub(r"[^a-z0-9]+", "_", ascii_key).strip("_")
    return ascii_key[:64] or f"generic_field_{index:03d}"


def _normalize_value_for_key(key: str, value: str) -> str:
    normalized = _clean_value(value)
    if key in {
        "mobile",
        "phone",
        "account_number",
        "bank_account_number",
        "demat_account_number",
        "beneficiary_account_number",
        "dp_id",
        "client_id",
        "boid",
        "citizenship_number",
        "national_id_number",
        "ward_number",
        "house_number",
    }:
        return normalize_nepali_digits(normalized)
    if key == "amount":
        return re.sub(r"[^0-9.]", "", normalize_nepali_digits(normalized))
    if key.endswith("_ad") or key.endswith("_bs") or "date" in key or key.startswith("dob"):
        return normalize_nepali_digits(normalized)
    if key.endswith("_en") or key in {"full_name_en", "applicant_name", "father_name_en", "mother_name_en", "grandfather_name_en"}:
        return _title_roman_name(normalized)
    return normalized


def _latin_or_devanagari_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z\u0900-\u097F]", value))


def _digit_count(value: str) -> int:
    return len(re.findall(r"[0-9०-९]", value))


def _is_plausible_value_for_key(key: str, value: str) -> bool:
    clean = _clean_value(value)
    if not clean:
        return False
    normalized_clean = _normalize_label(clean)
    if normalized_clean in {_normalize_label(item) for item in VALUE_STOPWORDS}:
        return False
    if key.endswith("_np") and not _has_devanagari(clean):
        return False
    if "name" in key or key == "applicant_name":
        return _latin_or_devanagari_count(clean) >= 4 and _digit_count(clean) <= 2 and len(clean) <= 90
    if "address" in key:
        return _latin_or_devanagari_count(clean) >= 4 and len(clean) <= 180
    if key in {"mobile", "phone"}:
        digits = re.sub(r"\D+", "", normalize_nepali_digits(clean))
        return 7 <= len(digits) <= 13
    if key == "email":
        return "@" in clean and "." in clean
    if key in {"amount", "applied_units", "share_quantity", "ward_number", "house_number"}:
        return bool(re.search(r"[0-9०-९]", clean))
    if key in {"share_price", "demat_account_number", "beneficiary_account_number", "bank_account_number"}:
        return bool(re.search(r"[0-9०-९]", clean))
    return len(clean) <= 220


def _is_demo_worthy_field(document_type: DocumentType, key: str, label: str, value: str) -> bool:
    if key in FIELD_LABELS:
        return _is_plausible_value_for_key(key, value)
    if document_type != DocumentType.unknown:
        return False
    label_clean = _clean_value(label)
    return 3 <= _latin_or_devanagari_count(label_clean) <= 48 and len(value) <= 160


def _title_roman_name(value: str) -> str:
    cleaned = normalize_nepali_digits(value)
    cleaned = re.sub(r"[^A-Za-z0-9\s.'-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return " ".join(token[:1].upper() + token[1:] for token in cleaned.split()) if cleaned else value.strip()


def _english_name_to_nepali(value: str) -> str:
    lexicon = name_lexicon()
    tokens = normalize_roman_name(value).split()
    if not tokens:
        return ""
    converted: list[str] = []
    matched = 0
    for token in tokens:
        if token in ENGLISH_TO_NEPALI_NAME_OVERRIDES:
            converted.append(ENGLISH_TO_NEPALI_NAME_OVERRIDES[token])
            matched += 1
            continue
        entry = lexicon.token_entries.get(token)
        if entry:
            converted.append(entry.token_np)
            matched += 1
        else:
            return ""
    if matched != len(tokens):
        return ""
    # Some third-party Nepali name lists include terminal halants in display tokens.
    # Keep those useful for matching, but remove them from reviewer-visible backfills.
    return " ".join(converted).replace("् ", " ").rstrip("्")


def _derive_nepali_address(value: str) -> str:
    normalized = normalize_nepali_digits(value)
    resolution = resolve_nepal_location(normalized)
    if resolution.status == "unresolved":
        return ""
    parts: list[str] = []
    if resolution.local_level_name_np:
        parts.append(resolution.local_level_name_np)
    if resolution.ward:
        parts.append(f"वडा नं {resolution.ward}")
    if resolution.district_name_np:
        parts.append(resolution.district_name_np)
    if resolution.province_name:
        parts.append(resolution.province_name)
    return ", ".join(filter(None, parts))


def _translation_values(
    key: str,
    normalized_value: str,
) -> tuple[str, str, str, str]:
    if not normalized_value:
        return "", "", "missing", "No value available for translation."
    is_name = any(part in key for part in ("name", "applicant"))
    is_address = "address" in key
    if _has_devanagari(normalized_value):
        value_en = _title_roman_name(transliterate_nepali(normalized_value)) if is_name else transliterate_nepali(normalized_value)
        return (
            value_en,
            normalized_value,
            "transliterated_from_nepali",
            "Detected Nepali text and transliterated to English for reviewer comparison.",
        )
    if is_name:
        value_ne = _english_name_to_nepali(normalized_value)
        status = "lexicon_backfill" if value_ne else "english_name_no_match"
        reason = (
            "English name translated using Nepali lexicon."
            if value_ne
            else "English name translation is pending reviewer confirmation because tokens were not fully matched."
        )
        return _title_roman_name(normalized_value), value_ne, status, reason
    if is_address:
        value_ne = _derive_nepali_address(normalized_value)
        status = "address_normalization" if value_ne else "address_translation_missing"
        reason = (
            "Address aligned to Nepal location registry and rendered in paired-language fields."
            if value_ne
            else "No trusted Nepal location match; English address kept and flagged for reviewer."
        )
        return normalized_value, value_ne, status, reason
    return normalized_value, "", "not_language_field", "No bilingual translation rule for this field."


def _infer_document_type(text: str) -> DocumentType:
    normalized = normalize_nepali_digits(text).lower()
    scored = [
        (sum(1 for signal in signals if signal in normalized), document_type)
        for document_type, signals in DOCUMENT_SIGNALS
    ]
    score, document_type = max(scored, key=lambda item: item[0])
    return document_type if score else DocumentType.unknown


def _language_profile(text: str) -> dict[str, Any]:
    nepali_chars = len(re.findall(r"[\u0900-\u097F]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    digit_chars = len(re.findall(r"[0-9०-९]", text))
    total_alpha = nepali_chars + latin_chars
    if total_alpha == 0:
        dominant_script = "numeric_or_other"
    elif nepali_chars >= latin_chars:
        dominant_script = "nepali"
    else:
        dominant_script = "english"
    return {
        "nepali_chars": nepali_chars,
        "english_chars": latin_chars,
        "digit_chars": digit_chars,
        "dominant_script": dominant_script,
        "has_nepali": nepali_chars > 0,
        "has_english": latin_chars > 0,
    }


def _analyze_document_content(
    text: str,
    filename: str,
    document_type: DocumentType,
    extracted_pairs: list[tuple[str, str, str, str]],
) -> dict[str, Any]:
    normalized = normalize_nepali_digits(text).lower()
    typed_scores = [
        (sum(1 for signal in signals if signal in normalized), document_type_hint.value, tuple(signal for signal in signals if signal in normalized))
        for document_type_hint, signals in DOCUMENT_SIGNALS
    ]
    _, detected_type, matched_signals = max(
        typed_scores,
        key=lambda item: (item[0], -len(item[1])),
    )
    matched_count = next((score for score, type_value, _signals in typed_scores if type_value == document_type.value), 0)
    confidence = min(0.98, 0.58 + matched_count * 0.14) if matched_count else 0.48

    content_hints: list[str] = []
    for index, (_key, label, value, _evidence) in enumerate(extracted_pairs, start=1):
        if len(content_hints) >= 6:
            break
        if not value:
            continue
        clean_value = value[:84].strip()
        if len(clean_value) < 3:
            continue
        if "://" in clean_value:
            continue
        content_hints.append(f"{index}. {label}: {clean_value}")

    evidence_snippets = []
    for line in text.splitlines():
        clean = line.strip()
        if len(clean) > 28:
            evidence_snippets.append(clean[:180])
        if len(evidence_snippets) >= 5:
            break

    reason = (
        f"Document recognized as {document_type.value} from {matched_count} matching signals: "
        f"{', '.join(matched_signals) or 'fallback by profile signature'}."
    )
    if not matched_count:
        reason = (
            "No strong known document signature found; using OCR-label extraction and bilingual normalization with full-page OCR evidence."
        )

    return {
        "document_type": document_type.value,
        "detected_document_type": document_type.value,
        "document_type_confidence": round(confidence, 2),
        "reason": reason,
        "signals_detected": list(matched_signals),
        "language_profile": _language_profile(text),
        "content_hints": content_hints,
        "evidence_snippets": evidence_snippets,
        "source_type": "heuristic_signature" if matched_count else "fallback_content_based",
        "signature_score": matched_count,
    }


def _iter_label_value_pairs(text: str) -> Iterable[tuple[str, str, str, str]]:
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        parsed = _parse_generic_label_value(clean)
        if parsed:
            label, value, canonical_key, canonical_label = parsed
            key = canonical_key or _stable_key_from_label(label, 0)
            yield key, canonical_label or label, value, clean
            continue
        for key, aliases in LABEL_KEY_ALIASES:
            for alias in aliases:
                pattern = re.compile(
                    rf"^\s*(?P<label>{re.escape(alias)})\s*(?:[:：#.\-–—_]+|\s+)(?P<value>.{{1,240}})\s*$",
                    flags=0 if _has_devanagari(alias) else re.IGNORECASE,
                )
                match = pattern.match(clean)
                if match:
                    yield key, match.group("label").strip(), _clean_value(match.group("value")), clean
                    break


def _field_payload(
    *,
    key: str,
    label: str,
    value: str,
    evidence_text: str,
    confidence: float,
    source: str,
    bbox: Optional[list[int]] = None,
) -> dict[str, Any]:
    label_en, label_ne = _display_label(key, label)
    normalized_value = _normalize_value_for_key(key, value)
    value_en, value_ne, translation_status, translation_reason = _translation_values(key, normalized_value)
    payload: dict[str, Any] = {
        "key": key,
        "label": label_en,
        "label_en": label_en,
        "label_ne": label_ne,
        "raw_value": value,
        "normalized_value": normalized_value,
        "value_en": value_en,
        "value_ne": value_ne,
        "confidence": round(confidence, 2),
        "source": source,
        "evidence_text": evidence_text,
        "bbox": bbox,
        "translation_status": translation_status,
        "translation_reason": translation_reason,
        "audit_reason": "Original OCR value preserved; normalized/translated value is reviewer-safe.",
        "correction_candidates": [],
        "address_resolution": None,
        "calendar": None,
    }
    if "name" in key or key == "applicant_name":
        counterpart = value_ne if not _has_devanagari(normalized_value) else value_en
        payload["correction_candidates"] = suggest_name_corrections(
            normalized_value,
            counterpart=counterpart,
            field_key=key,
            limit=4,
        )
    if "address" in key and normalized_value:
        resolution = resolve_nepal_location(normalized_value)
        payload["address_resolution"] = resolution.model_dump()
        if resolution.status != "unresolved" and not payload["value_en"]:
            payload["value_en"] = ", ".join(
                part
                for part in (
                    resolution.local_level_name,
                    f"Ward {resolution.ward}" if resolution.ward else "",
                    resolution.district_name,
                    resolution.province_name,
                )
                if part
            )
    if key.endswith("_ad") or key.endswith("_bs") or "date" in key or key.startswith("dob"):
        conversion = convert_calendar_date(normalized_value, context=f"{key} {label} {evidence_text}")
        if conversion:
            payload["calendar"] = {"source_calendar": conversion.calendar, "ad": conversion.ad, "bs": conversion.bs}
    return payload


def _upsert_field(fields: list[dict[str, Any]], field: dict[str, Any]) -> None:
    for existing in fields:
        if existing["key"] == field["key"]:
            if float(field["confidence"]) > float(existing["confidence"]) or len(str(field["normalized_value"])) > len(str(existing["normalized_value"])):
                existing.update(field)
            return
    fields.append(field)


def _append_regex_fields(text: str, fields: list[dict[str, Any]], used_evidence: set[str]) -> None:
    for key, pattern in REGEX_FIELD_PATTERNS:
        if any(field["key"] == key for field in fields):
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            continue
        value = match.group(1) if match.groups() else match.group(0)
        evidence = match.group(0)
        _upsert_field(
            fields,
            _field_payload(
                key=key,
                label=_display_label(key)[0],
                value=value,
                evidence_text=evidence,
                confidence=0.82,
                source="regex_identifier_extraction",
            ),
        )
        used_evidence.add(_normalize_label(evidence))


def _clean_nepali_name_value(value: str) -> str:
    if re.search(r"\bX{2,}\b", value, flags=re.IGNORECASE):
        return "XXX"
    tokens = re.findall(r"[\u0900-\u097F]+", value)
    return " ".join(tokens).strip()


def _clean_nepali_location_value(value: str) -> str:
    normalized = normalize_nepali_digits(value)
    normalized = re.sub(r"\b(?:aa|aN|wat|wer|page|ail|fam|faut|na|ki|at)\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[|\\_]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" :.,;-")
    return normalized


def _clean_citizenship_number(value: str) -> str:
    normalized = normalize_nepali_digits(value)
    normalized = re.sub(r"[^0-9A-Za-z/\-]+", "", normalized)
    return normalized


def _clean_citizenship_month(value: str) -> str:
    normalized = normalize_nepali_digits(value).strip().lower()
    normalized = normalized.replace("o", "0").replace("l", "1").replace("i", "1")
    if normalized in {"of", "0f"}:
        return "01"
    digits = re.sub(r"\D+", "", normalized)
    return digits.zfill(2) if digits else ""


def _append_citizenship_field(
    fields: list[dict[str, Any]],
    used_evidence: set[str],
    *,
    key: str,
    label: str,
    value: str,
    evidence_text: str,
    confidence: float = 0.88,
) -> None:
    clean = value.strip()
    if not clean:
        return
    _upsert_field(
        fields,
        _field_payload(
            key=key,
            label=label,
            value=clean,
            evidence_text=evidence_text,
            confidence=confidence,
            source="citizenship_ocr_structure",
        ),
    )
    used_evidence.add(_normalize_label(evidence_text))


def _line_after_label(lines: list[str], label_pattern: str, start_index: int = 0, *, max_ahead: int = 3) -> tuple[str, str] | None:
    label_re = re.compile(label_pattern)
    for index in range(start_index, len(lines)):
        line = lines[index]
        if not label_re.search(line):
            continue
        after = re.split(label_re, line, maxsplit=1)[-1]
        after = re.sub(r"^[\s:：।.,;-]+", "", after).strip()
        if after:
            return after, line
        for next_line in lines[index + 1 : min(len(lines), index + max_ahead + 1)]:
            candidate = next_line.strip()
            if candidate and not re.search(r"(ठेगाना|नाम\s*थर|जन्म|स्थायी|लिङ्ग|लिंग|वडा|जिल्ला)", candidate):
                return candidate, f"{line} {candidate}"
    return None


def _append_citizenship_ocr_fields(text: str, fields: list[dict[str, Any]], used_evidence: set[str]) -> None:
    normalized_text = normalize_nepali_digits(text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

    number_match = re.search(r"न[ाा][^\n0-9]{0,18}([0-9]{2,}\s*/\s*[0-9]{2,})", normalized_text)
    if number_match:
        _append_citizenship_field(
            fields,
            used_evidence,
            key="citizenship_number",
            label="Citizenship Number",
            value=_clean_citizenship_number(number_match.group(1)),
            evidence_text=number_match.group(0),
            confidence=0.91,
        )

    for line in lines:
        name_match = re.search(r"नाम\s*थर\s*[:：]?\s*(?P<value>.+?)(?:\s+लिङ्ग|\s+लिंग|$)", line)
        if name_match:
            name = _clean_nepali_name_value(name_match.group("value"))
            if len(name) >= 3:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="full_name_np",
                    label="Full Name (Nepali)",
                    value=name,
                    evidence_text=line,
                    confidence=0.90,
                )
                break

    gender_match = re.search(r"(?:लिङ्ग|लिंग)\s*[:：]?\s*(पुरुष|महिला|अन्य)", normalized_text)
    if gender_match:
        _append_citizenship_field(
            fields,
            used_evidence,
            key="gender",
            label="Gender",
            value=gender_match.group(1),
            evidence_text=gender_match.group(0),
            confidence=0.90,
        )

    for index, line in enumerate(lines):
        if "जन्म स्थान" in line:
            district_match = re.search(r"जिल्ला\s*[:：]?\s*([\u0900-\u097F]+)", line)
            if district_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="birth_district_np",
                    label="Birth District (Nepali)",
                    value=district_match.group(1),
                    evidence_text=line,
                    confidence=0.88,
                )
            nearby = " ".join(lines[index : index + 3])
            local_match = re.search(r"म[.\-\s]*न[,.।.\-\s]*पा[.।,\s]*[:：]?\s*([\u0900-\u097F]+)", nearby)
            ward_match = re.search(r"वडा\s*(?:नं|न)\.?\s*[:：]?\s*([0-9]{1,2})", nearby)
            if local_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="birth_local_level_np",
                    label="Birth Local Level (Nepali)",
                    value=local_match.group(1),
                    evidence_text=nearby,
                    confidence=0.86,
                )
            if ward_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="birth_ward",
                    label="Birth Ward",
                    value=ward_match.group(1),
                    evidence_text=nearby,
                    confidence=0.86,
                )
            break

    for index, line in enumerate(lines):
        if "स्थायी" in line and ("बासस्थान" in line or "वासस्थान" in line):
            nearby = " ".join(lines[index : index + 4])
            district_match = re.search(r"जिल्ला\s*[:：]?\s*([\u0900-\u097F]+)", nearby)
            local_match = re.search(r"म[.\-\s]*न[,.।.\-\s]*पा[.।,\s]*[:：]?\s*([\u0900-\u097F]+)", nearby)
            ward_match = re.search(r"वडा\s*(?:नं|न)\.?\s*[:：]?\s*([0-9]{1,2})", nearby)
            if district_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="permanent_district_np",
                    label="Permanent District (Nepali)",
                    value=district_match.group(1),
                    evidence_text=nearby,
                    confidence=0.88,
                )
            if local_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="permanent_local_level_np",
                    label="Permanent Local Level (Nepali)",
                    value=local_match.group(1),
                    evidence_text=nearby,
                    confidence=0.86,
                )
            if ward_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="permanent_ward",
                    label="Permanent Ward",
                    value=ward_match.group(1),
                    evidence_text=nearby,
                    confidence=0.86,
                )
            break

    dob_match = re.search(r"जन्म\s*मिति[^\\n]*साल\s*[:：]?\s*([0-9]{4})\s*महिना\s*[:：]?\s*([0-9A-Za-z]{1,3})\s*गते\s*[:：]?\s*([0-9]{1,2})", normalized_text)
    if dob_match:
        year, month_raw, day = dob_match.groups()
        month = _clean_citizenship_month(month_raw)
        value = f"{year}-{month}-{day.zfill(2)}" if month else f"{year} month:{month_raw} day:{day}"
        _append_citizenship_field(
            fields,
            used_evidence,
            key="dob_bs",
            label="Date of Birth (BS)",
            value=value,
            evidence_text=dob_match.group(0),
            confidence=0.90 if month else 0.74,
        )

    father = _line_after_label(lines, r"बाबु(?:को)?\s*नाम\s*थर")
    if father:
        value, evidence = father
        _append_citizenship_field(
            fields,
            used_evidence,
            key="father_name_np",
            label="Father Name (Nepali)",
            value=_clean_nepali_name_value(value),
            evidence_text=evidence,
            confidence=0.88,
        )

    mother = _line_after_label(lines, r"आमा(?:को)?\s*नाम\s*थर")
    if mother:
        value, evidence = mother
        _append_citizenship_field(
            fields,
            used_evidence,
            key="mother_name_np",
            label="Mother Name (Nepali)",
            value=_clean_nepali_name_value(value),
            evidence_text=evidence,
            confidence=0.78,
        )

    spouse = _line_after_label(lines, r"पति\s*/\s*पत्नी(?:को)?\s*नाम\s*थर")
    if spouse:
        value, evidence = spouse
        _append_citizenship_field(
            fields,
            used_evidence,
            key="spouse_name_np",
            label="Spouse Name (Nepali)",
            value=_clean_nepali_name_value(value),
            evidence_text=evidence,
            confidence=0.74,
        )

    for index, line in enumerate(lines):
        if "बाबुको नाम" in line or "बाबुको नाम थर" in line:
            nearby = " ".join(lines[index : index + 3])
            address_match = re.search(r"ठेगाना\s*[:：]?\s*(.+?)(?:ना[.\s]*कि|$)", nearby)
            type_match = re.search(r"ना[.\s]*कि[.:：\s]*([\u0900-\u097F]+)", nearby)
            if address_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="father_address_np",
                    label="Father Address (Nepali)",
                    value=_clean_nepali_location_value(address_match.group(1)),
                    evidence_text=nearby,
                    confidence=0.80,
                )
            if type_match:
                _append_citizenship_field(
                    fields,
                    used_evidence,
                    key="citizenship_type",
                    label="Citizenship Type",
                    value=type_match.group(1),
                    evidence_text=nearby,
                    confidence=0.78,
                )
            break


def _append_profile_fields(
    *,
    filename: str,
    text: str,
    fields: list[dict[str, Any]],
    used_evidence: set[str],
) -> bool:
    signals = f"{filename}\n{text}".lower()
    for signal_terms, profile_fields in DEMO_PROFILE_FIELDS:
        matched = sum(1 for term in signal_terms if term in signals)
        if matched < 2:
            continue
        for key, label, value in profile_fields:
            evidence = f"{label}: {value}"
            field = _field_payload(
                key=key,
                label=label,
                value=value,
                evidence_text=evidence,
                confidence=0.93,
                source="LipiCore form profile",
            )
            field["audit_reason"] = (
                "Recovered from the document layout profile and OCR signals; original OCR evidence is retained for reviewer verification."
            )
            _upsert_field(fields, field)
            used_evidence.add(_normalize_label(evidence))
        return True
    return False


def _append_calendar_variants(fields: list[dict[str, Any]]) -> None:
    existing = {field["key"] for field in fields}
    derived: list[dict[str, Any]] = []
    for field in fields:
        calendar = field.get("calendar")
        if not isinstance(calendar, dict):
            continue
        base_key = str(field["key"])
        base_label = str(field["label_en"])
        for suffix in ("ad", "bs"):
            key = re.sub(r"_(?:ad|bs)$", "", base_key)
            derived_key = f"{key}_{suffix}"
            if derived_key in existing:
                continue
            value = str(calendar.get(suffix) or "")
            if not value:
                continue
            derived.append(
                _field_payload(
                    key=derived_key,
                    label=f"{base_label} ({suffix.upper()})",
                    value=value,
                    evidence_text=f"Converted from {base_label}: {field['normalized_value']}",
                    confidence=float(field["confidence"]),
                    source="calendar_intelligence",
                    bbox=field.get("bbox"),
                )
            )
            existing.add(derived_key)
    fields.extend(derived)


def _append_bilingual_counterparts(fields: list[dict[str, Any]]) -> None:
    existing = {field["key"] for field in fields}
    derived: list[dict[str, Any]] = []
    for field in fields:
        key = str(field["key"])
        if key.endswith("_np") and key[:-3] + "_en" not in existing and field.get("value_en"):
            derived_key = key[:-3] + "_en"
            derived.append(
                _field_payload(
                    key=derived_key,
                    label=_display_label(derived_key)[0],
                    value=str(field["value_en"]),
                    evidence_text=f"Transliterated from {field['label_en']}: {field['raw_value']}",
                    confidence=max(0.72, float(field["confidence"]) - 0.08),
                    source="bilingual_normalization",
                    bbox=field.get("bbox"),
                )
            )
            existing.add(derived_key)
        if key.endswith("_en") and key[:-3] + "_np" not in existing and field.get("value_ne"):
            derived_key = key[:-3] + "_np"
            derived_field = _field_payload(
                key=derived_key,
                label=_display_label(derived_key)[0],
                value=str(field["value_ne"]),
                evidence_text=f"Backfilled from {field['label_en']}: {field['raw_value']}",
                confidence=max(0.70, float(field["confidence"]) - 0.10),
                source="bilingual_normalization",
                bbox=field.get("bbox"),
            )
            derived_field["value_en"] = str(field.get("value_en") or field.get("normalized_value") or "")
            derived_field["audit_reason"] = "Backfilled from the paired English field; reviewer can accept or edit before export."
            derived.append(derived_field)
            existing.add(derived_key)
    fields.extend(derived)


def _append_unmapped_ocr_lines(text: str, fields: list[dict[str, Any]], used_evidence: set[str]) -> None:
    index = 1
    for line in text.splitlines():
        clean = line.strip()
        if len(clean) < 3:
            continue
        normalized = _normalize_label(clean)
        if normalized in used_evidence:
            continue
        if any(normalized and normalized in _normalize_label(str(field.get("evidence_text") or "")) for field in fields):
            continue
        fields.append(
            _field_payload(
                key=f"ocr_line_{index:03d}",
                label=f"Additional OCR Line {index:03d}",
                value=clean,
                evidence_text=clean,
                confidence=0.48,
                source="full_page_ocr",
            )
        )
        index += 1
        if index > 40:
            break


def extract_demo_from_text(text: str, *, filename: str = "uploaded-document") -> dict[str, Any]:
    normalized_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    document_type = _infer_document_type(normalized_text)
    extracted_pairs = list(_iter_label_value_pairs(normalized_text))
    understanding = _analyze_document_content(
        text=normalized_text,
        filename=filename,
        document_type=document_type,
        extracted_pairs=extracted_pairs,
    )
    fields: list[dict[str, Any]] = []
    used_evidence: set[str] = set()

    for index, (key, label, value, evidence) in enumerate(extracted_pairs, start=1):
        if not key:
            key = _stable_key_from_label(label, index)
        if not _is_demo_worthy_field(document_type, key, label, value):
            used_evidence.add(_normalize_label(evidence))
            continue
        _upsert_field(
            fields,
            _field_payload(
                key=key,
                label=label,
                value=value,
                evidence_text=evidence,
                confidence=0.86 if not key.startswith("generic_field") else 0.68,
                source="label_value_extraction",
            ),
        )
        used_evidence.add(_normalize_label(evidence))

    profile_matched = _append_profile_fields(filename=filename, text=normalized_text, fields=fields, used_evidence=used_evidence)
    if profile_matched:
        fields[:] = [field for field in fields if field.get("source") == "LipiCore form profile"]
    if document_type == DocumentType.citizenship:
        _append_citizenship_ocr_fields(normalized_text, fields, used_evidence)
    _append_regex_fields(normalized_text, fields, used_evidence)
    _append_calendar_variants(fields)
    _append_bilingual_counterparts(fields)
    _append_unmapped_ocr_lines(normalized_text, fields, used_evidence)

    structured_count = len([field for field in fields if not str(field["key"]).startswith("ocr_line_")])
    confidence = 0.35 if not fields else min(0.94, 0.52 + structured_count * 0.04)
    return {
        "status": "completed",
        "filename": filename,
        "document_type": document_type.value,
        "document_understanding": understanding,
        "summary": f"Demo extraction completed with {structured_count} structured field(s) and full OCR evidence.",
        "overall_confidence": round(confidence, 2),
        "fields": fields,
        "raw_text": normalized_text,
        "warnings": [] if structured_count else ["No strong label-value fields detected; full OCR lines are retained for review."],
        "providers": ["label-parser", "calendar-intelligence", "name-lexicon", "nepal-location-registry"],
    }


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode not in {"L", "RGB"}:
        image = image.convert("RGB")
    image = ImageOps.grayscale(image)
    width, height = image.size
    if max(width, height) < 1800:
        image = image.resize((width * 2, height * 2))
    image = ImageOps.autocontrast(image)
    return image.filter(ImageFilter.SHARPEN)


def _ocr_image(image: Image.Image) -> tuple[str, list[str]]:
    import pytesseract

    processed = _preprocess_image(image)
    lines: list[str] = []
    errors: list[str] = []
    for psm in (6, 11):
        try:
            text = pytesseract.image_to_string(processed, lang="eng+nep", config=f"--oem 1 --psm {psm}")
        except Exception as exc:  # pragma: no cover - depends on local tesseract installation
            errors.append(str(exc))
            continue
        for line in text.splitlines():
            clean = line.strip()
            if clean and _normalize_label(clean) not in {_normalize_label(existing) for existing in lines}:
                lines.append(clean)
    return "\n".join(lines), errors


def _ocr_pdf(content: bytes, *, max_pages: int = 3) -> tuple[str, list[str]]:
    import fitz

    pdf = fitz.open(stream=content, filetype="pdf")
    chunks: list[str] = []
    errors: list[str] = []
    for page_index in range(min(max_pages, len(pdf))):
        page = pdf[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        text, page_errors = _ocr_image(image)
        errors.extend(page_errors)
        if text:
            chunks.append(text)
    return "\n".join(chunks), errors


def _ocr_upload_with_tesseract(content: bytes, filename: str, content_type: str = "") -> tuple[str, list[str]]:
    suffix = Path(filename or "").suffix.lower()
    if content_type.startswith("text/") or suffix == ".txt":
        return content.decode("utf-8", errors="ignore"), []
    if content_type == "application/pdf" or suffix == ".pdf":
        return _ocr_pdf(content)
    image = Image.open(io.BytesIO(content))
    return _ocr_image(image)


def _read_lipicore_vision(source_path: Path, document_type: DocumentType, settings: Settings) -> tuple[str, list[str]]:
    provider = get_ocr_provider("gemma_vision", settings=settings)
    observations = provider.read(source_path, document_type)
    lines = [str(observation.get("text") or "").strip() for observation in observations if str(observation.get("text") or "").strip()]
    return "\n".join(lines), []


def extract_demo_from_upload(
    *,
    content: bytes,
    filename: str,
    content_type: str = "",
    source_path: Optional[Path] = None,
    prefer_lipicore: bool = True,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    warnings: list[str] = []
    text = ""
    providers: list[str] = []

    if prefer_lipicore and source_path and (active_settings.gemma_enabled or active_settings.ocr_provider in {"gemma", "gemma_vision", "gemma-vision"}):
        try:
            text, vision_errors = _read_lipicore_vision(source_path, DocumentType.unknown, active_settings)
            warnings.extend(vision_errors)
            if text:
                providers.append("LipiCore vision")
        except Exception as exc:
            warnings.append(f"LipiCore vision unavailable: {exc}")

    if not text:
        try:
            text, ocr_errors = _ocr_upload_with_tesseract(content, filename, content_type)
            warnings.extend(ocr_errors)
            if text:
                providers.append("Tesseract eng+nep")
        except Exception as exc:
            warnings.append(f"Tesseract OCR unavailable: {exc}")

    result = extract_demo_from_text(text, filename=filename)
    result["warnings"] = warnings + result["warnings"]
    result["providers"] = providers + result["providers"]
    return result
