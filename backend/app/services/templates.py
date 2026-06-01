import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi import HTTPException

from app.core.config import get_settings
from app.models import DocumentTemplate, DocumentType, TemplateField


VALIDATION_RULES: Dict[DocumentType, List[Dict[str, object]]] = {}
_PERSISTED_LOADED = False
SYSTEM_TEMPLATE_TYPES = frozenset(
    {
        DocumentType.citizenship,
        DocumentType.passport,
        DocumentType.national_id,
        DocumentType.driving_license,
    }
)


TEMPLATES: Dict[DocumentType, DocumentTemplate] = {
    DocumentType.citizenship: DocumentTemplate(
        document_type=DocumentType.citizenship,
        name="Nepal Citizenship Certificate",
        fields=[
            TemplateField(key="citizenship_number", label="Citizenship Number", required=True, bbox=[42, 132, 160, 168]),
            TemplateField(key="district", label="District", required=False, bbox=[650, 150, 780, 188]),
            TemplateField(key="name_ne", label="Name (Nepali)", required=True, bbox=[214, 210, 380, 244]),
            TemplateField(key="name_en", label="Name (English)", required=False, bbox=[214, 244, 480, 278]),
            TemplateField(key="gender", label="Gender / Sex", required=False, bbox=[650, 210, 760, 244]),
            TemplateField(key="citizenship_type", label="Citizenship Type", required=False, bbox=[650, 520, 760, 556]),
            TemplateField(key="copy_type", label="Copy Type", required=False, bbox=[40, 42, 180, 78]),
            TemplateField(key="birth_place_district", label="Birth Place District", required=False, bbox=[214, 260, 420, 300]),
            TemplateField(key="birth_place_municipality", label="Birth Place Municipality", required=False, bbox=[420, 260, 640, 300]),
            TemplateField(key="birth_place_ward", label="Birth Place Ward", required=False, bbox=[650, 260, 760, 300]),
            TemplateField(key="permanent_address_ne", label="Permanent Address (Nepali)", required=True, bbox=[214, 300, 570, 338]),
            TemplateField(key="permanent_address_en", label="Permanent Address (English)", required=False, bbox=[214, 338, 570, 376]),
            TemplateField(key="permanent_address_district", label="Permanent Address District", required=False, bbox=[214, 300, 420, 338]),
            TemplateField(key="permanent_address_municipality", label="Permanent Address Municipality", required=False, bbox=[420, 300, 640, 338]),
            TemplateField(key="permanent_address_ward", label="Permanent Address Ward", required=False, bbox=[650, 300, 760, 338]),
            TemplateField(key="dob_bs", label="Date of Birth (BS)", required=True, bbox=[380, 380, 640, 414]),
            TemplateField(key="dob_ad", label="Date of Birth (AD)", required=False, bbox=[380, 414, 640, 448]),
            TemplateField(key="father_name_ne", label="Father Name (Nepali)", required=False, bbox=[214, 444, 560, 480]),
            TemplateField(key="father_name_en", label="Father Name (English)", required=False, bbox=[214, 480, 560, 516]),
            TemplateField(key="father_citizenship_number", label="Father Citizenship Number", required=False, bbox=[570, 444, 760, 480]),
            TemplateField(key="mother_name_ne", label="Mother Name (Nepali)", required=False, bbox=[214, 520, 560, 556]),
            TemplateField(key="mother_name_en", label="Mother Name (English)", required=False, bbox=[214, 556, 560, 592]),
            TemplateField(key="mother_citizenship_number", label="Mother Citizenship Number", required=False, bbox=[570, 520, 760, 556]),
            TemplateField(key="spouse_name_ne", label="Spouse Name (Nepali)", required=False, bbox=[214, 596, 560, 632]),
            TemplateField(key="spouse_name_en", label="Spouse Name (English)", required=False, bbox=[214, 632, 560, 668]),
            TemplateField(key="spouse_citizenship_number", label="Spouse Citizenship Number", required=False, bbox=[570, 596, 760, 632]),
            TemplateField(key="issue_date_bs", label="Issue Date (BS)", required=False, bbox=[570, 520, 760, 560]),
            TemplateField(key="issue_date_ad", label="Issue Date (AD)", required=False, bbox=[570, 560, 760, 596]),
            TemplateField(key="issuing_office", label="Issuing Office", required=False, bbox=[260, 72, 690, 120]),
            TemplateField(key="issuing_authority_name", label="Issuing Officer Name", required=False, bbox=[570, 596, 760, 632]),
            TemplateField(key="issuing_authority_designation", label="Issuing Officer Designation", required=False, bbox=[570, 632, 760, 668]),
            TemplateField(key="photo", label="Photo", required=False, bbox=[22, 260, 206, 480]),
            TemplateField(key="holder_signature", label="Holder Signature", required=False, bbox=[22, 520, 206, 590]),
            TemplateField(key="left_thumbprint", label="Left Thumbprint", required=False, bbox=[22, 610, 120, 760]),
            TemplateField(key="right_thumbprint", label="Right Thumbprint", required=False, bbox=[130, 610, 230, 760]),
            TemplateField(key="official_signature", label="Official Signature", required=False, bbox=[600, 610, 760, 690]),
            TemplateField(key="official_stamp", label="Official Stamp", required=False, bbox=[650, 80, 760, 180]),
            TemplateField(key="name", label="Name", required=True, bbox=[214, 210, 480, 278]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[380, 380, 640, 448]),
            TemplateField(
                key="address",
                label="Address",
                required=True,
                bbox=[214, 300, 570, 376],
            ),
            TemplateField(key="father_mother_name", label="Father/Mother Name", required=False, bbox=[214, 444, 560, 556]),
        ],
    ),
    DocumentType.account_opening: DocumentTemplate(
        document_type=DocumentType.account_opening,
        name="Account Opening Form",
        fields=[
            TemplateField(key="customer_name", label="Customer Name", required=True, bbox=[160, 130, 620, 175]),
            TemplateField(key="mobile", label="Mobile", required=True, bbox=[160, 195, 420, 235]),
            TemplateField(key="address", label="Address", required=True, bbox=[160, 255, 720, 305]),
            TemplateField(key="account_type", label="Account Type", required=True, bbox=[160, 330, 460, 370]),
            TemplateField(key="pan", label="PAN", required=False, bbox=[160, 395, 420, 435]),
            TemplateField(key="email", label="Email", required=False, bbox=[160, 460, 620, 500]),
        ],
    ),
    DocumentType.cheque: DocumentTemplate(
        document_type=DocumentType.cheque,
        name="Cheque",
        fields=[
            TemplateField(key="cheque_number", label="Cheque Number", required=True, bbox=[60, 40, 260, 85]),
            TemplateField(key="date", label="Date", required=True, bbox=[600, 45, 760, 90]),
            TemplateField(key="amount", label="Amount", required=True, bbox=[560, 180, 760, 230]),
            TemplateField(key="payee", label="Payee", required=True, bbox=[140, 120, 650, 165]),
        ],
    ),
    DocumentType.national_id: DocumentTemplate(
        document_type=DocumentType.national_id,
        name="Nepal National Identity Card",
        fields=[
            TemplateField(key="national_id_number", label="National ID Number", required=True, bbox=[24, 246, 168, 302]),
            TemplateField(key="full_name_ne", label="Full Name (Nepali)", required=True, bbox=[246, 72, 456, 112]),
            TemplateField(key="full_name_en", label="Full Name (English)", required=True, bbox=[246, 122, 456, 166]),
            TemplateField(key="full_name", label="Full Name", required=True, bbox=[246, 72, 456, 166]),
            TemplateField(key="dob_bs", label="Date of Birth (BS)", required=True, bbox=[250, 202, 360, 236]),
            TemplateField(key="dob_ad", label="Date of Birth (AD)", required=True, bbox=[380, 202, 500, 236]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[250, 202, 500, 236]),
            TemplateField(key="gender", label="Gender", required=True, bbox=[108, 70, 146, 108]),
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[252, 340, 430, 386]),
            TemplateField(key="father_name", label="Father Name", required=False, bbox=[250, 296, 455, 334]),
            TemplateField(key="mother_name", label="Mother Name", required=False, bbox=[250, 252, 455, 292]),
            TemplateField(key="photo", label="Photo", required=False, bbox=[515, 52, 675, 250]),
            TemplateField(key="nationality", label="Nationality", required=False, bbox=[22, 68, 96, 108]),
        ],
    ),
    DocumentType.passport: DocumentTemplate(
        document_type=DocumentType.passport,
        name="Nepal Passport",
        fields=[
            TemplateField(key="passport_number", label="Passport Number", required=True, bbox=[430, 430, 542, 468]),
            TemplateField(key="surname", label="Surname", required=True, bbox=[146, 468, 330, 498]),
            TemplateField(key="given_name", label="Given Name", required=True, bbox=[146, 498, 330, 528]),
            TemplateField(key="nationality", label="Nationality", required=True, bbox=[146, 530, 330, 558]),
            TemplateField(key="sex", label="Sex", required=True, bbox=[146, 586, 220, 610]),
            TemplateField(key="place_of_birth", label="Place of Birth", required=False, bbox=[360, 586, 540, 620]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[146, 558, 330, 586]),
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[146, 610, 330, 640]),
            TemplateField(key="expiry_date", label="Date of Expiry", required=True, bbox=[146, 640, 330, 670]),
            TemplateField(key="citizenship_number", label="Citizenship Number", required=False, bbox=[360, 558, 540, 590]),
            TemplateField(key="issuing_authority", label="Issuing Authority", required=False, bbox=[360, 620, 548, 670]),
            TemplateField(key="mrz_line_1", label="MRZ Line 1", required=True, bbox=[24, 704, 548, 742]),
            TemplateField(key="mrz_line_2", label="MRZ Line 2", required=False, bbox=[24, 742, 548, 780]),
            TemplateField(key="photo", label="Photo", required=False, bbox=[42, 430, 138, 624]),
            TemplateField(key="signature", label="Holder Signature", required=False, bbox=[365, 668, 540, 704]),
        ],
    ),
    DocumentType.driving_license: DocumentTemplate(
        document_type=DocumentType.driving_license,
        name="Nepal Smart Driving License",
        fields=[
            TemplateField(key="license_number", label="License Number", required=True, bbox=[78, 76, 264, 112]),
            TemplateField(key="full_name", label="Full Name", required=True, bbox=[330, 86, 594, 124]),
            TemplateField(key="blood_group", label="Blood Group", required=False, bbox=[86, 126, 154, 164]),
            TemplateField(key="address", label="Address", required=True, bbox=[330, 128, 620, 190]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[330, 236, 502, 272]),
            TemplateField(key="father_husband_name", label="Father/Husband Name", required=False, bbox=[330, 274, 620, 310]),
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[78, 308, 236, 344]),
            TemplateField(key="expiry_date", label="Date of Expiry", required=True, bbox=[78, 368, 236, 404]),
            TemplateField(key="citizenship_number", label="Citizenship Number", required=True, bbox=[330, 326, 560, 362]),
            TemplateField(key="passport_number", label="Passport Number", required=False, bbox=[330, 366, 560, 400]),
            TemplateField(key="phone", label="Phone Number", required=False, bbox=[330, 404, 560, 438]),
            TemplateField(key="category", label="Category", required=True, bbox=[646, 292, 736, 330]),
            TemplateField(key="photo", label="Photo", required=False, bbox=[632, 84, 780, 270]),
            TemplateField(key="holder_signature", label="Holder Signature", required=False, bbox=[560, 418, 760, 486]),
            TemplateField(key="issuer_signature", label="Issuer Signature", required=False, bbox=[70, 418, 250, 486]),
        ],
    ),
    DocumentType.ipo_application: DocumentTemplate(
        document_type=DocumentType.ipo_application,
        name="Nepal IPO Share Application",
        fields=[
            TemplateField(key="company_name", label="Company Name", required=True, bbox=[230, 20, 620, 92]),
            TemplateField(key="application_number", label="Application Number", required=True, bbox=[600, 150, 760, 190]),
            TemplateField(key="applicant_name", label="Applicant Name", required=True, bbox=[150, 430, 570, 470]),
            TemplateField(key="applied_units", label="Applied Units", required=True, bbox=[145, 302, 300, 342]),
            TemplateField(key="amount", label="Amount", required=True, bbox=[440, 302, 610, 342]),
            TemplateField(key="boid", label="BOID", required=True, bbox=[260, 496, 610, 532]),
            TemplateField(key="bank_name", label="Bank Name", required=False, bbox=[152, 370, 430, 410]),
            TemplateField(key="account_number", label="Bank Account Number", required=False, bbox=[500, 370, 740, 410]),
            TemplateField(key="mobile", label="Mobile Number", required=False, bbox=[596, 615, 760, 650]),
            TemplateField(key="father_name", label="Father Name", required=False, bbox=[152, 712, 610, 752]),
            TemplateField(key="grandfather_name", label="Grandfather Name", required=False, bbox=[152, 764, 610, 804]),
        ],
    ),
    DocumentType.asba_application: DocumentTemplate(
        document_type=DocumentType.asba_application,
        name="Nepal C-ASBA / Bank IPO Application",
        fields=[
            TemplateField(key="bank_name", label="Bank Name", required=True, bbox=[42, 36, 270, 88]),
            TemplateField(key="applicant_name", label="Applicant Name", required=True, bbox=[128, 246, 430, 282]),
            TemplateField(key="dp_id", label="DP ID", required=True, bbox=[518, 172, 602, 204]),
            TemplateField(key="client_id", label="Client ID", required=True, bbox=[604, 172, 690, 204]),
            TemplateField(key="account_number", label="Bank Account Number", required=True, bbox=[512, 520, 688, 552]),
            TemplateField(key="amount", label="Amount", required=True, bbox=[388, 166, 510, 206]),
            TemplateField(key="applied_units", label="Applied Units", required=True, bbox=[270, 166, 342, 206]),
            TemplateField(key="company_name", label="Issue Manager / Company", required=False, bbox=[56, 156, 246, 214]),
            TemplateField(key="boid", label="BOID", required=False, bbox=[488, 750, 690, 790]),
            TemplateField(key="mobile", label="Mobile Number", required=False, bbox=[212, 500, 366, 532]),
            TemplateField(key="email", label="Email", required=False, bbox=[206, 530, 470, 562]),
            TemplateField(key="citizenship_number", label="Citizenship Number", required=False, bbox=[116, 482, 306, 514]),
        ],
    ),
}

SYSTEM_VALIDATION_RULES: Dict[DocumentType, List[Dict[str, object]]] = {
    DocumentType.citizenship: [
        {"field_key": "citizenship_number", "rule": "required", "severity": "error"},
        {"field_key": "name_ne", "rule": "required", "severity": "error"},
        {"field_key": "gender", "rule": "recommended", "severity": "warning"},
        {"field_key": "dob_bs", "rule": "date_bs", "severity": "warning"},
        {"field_key": "dob_ad", "rule": "date_ad", "severity": "warning"},
        {"field_key": "birth_place_district", "rule": "recommended", "severity": "warning"},
        {"field_key": "permanent_address_district", "rule": "recommended", "severity": "warning"},
        {"field_key": "father_name_ne", "rule": "recommended", "severity": "warning"},
        {"field_key": "mother_name_ne", "rule": "recommended", "severity": "warning"},
        {"field_key": "citizenship_type", "rule": "recommended", "severity": "warning"},
        {"field_key": "issuing_office", "rule": "recommended", "severity": "warning"},
        {"field_key": "issue_date_bs", "rule": "date_bs", "severity": "warning"},
    ],
    DocumentType.national_id: [
        {"field_key": "national_id_number", "rule": "required", "severity": "error"},
        {"field_key": "full_name_ne", "rule": "required", "severity": "error"},
        {"field_key": "dob_ad", "rule": "date_ad", "severity": "warning"},
    ],
    DocumentType.passport: [
        {"field_key": "passport_number", "rule": "required", "severity": "error"},
        {"field_key": "surname", "rule": "required", "severity": "error"},
        {"field_key": "given_name", "rule": "required", "severity": "error"},
        {"field_key": "expiry_date", "rule": "date_ad", "severity": "warning"},
        {"field_key": "mrz_line_1", "rule": "mrz", "severity": "warning"},
    ],
    DocumentType.driving_license: [
        {"field_key": "license_number", "rule": "required", "severity": "error"},
        {"field_key": "full_name", "rule": "required", "severity": "error"},
        {"field_key": "citizenship_number", "rule": "required", "severity": "error"},
        {"field_key": "expiry_date", "rule": "date_ad", "severity": "warning"},
    ],
}

VALIDATION_RULES.update({key: list(value) for key, value in SYSTEM_VALIDATION_RULES.items()})


def _template_store_enabled() -> bool:
    configured = os.getenv("LIPIOCR_LOAD_TEMPLATE_STORE", "").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    if os.getenv("LIPIOCR_TEMPLATE_STORE"):
        return True
    return get_settings().environment.lower() in {"production", "staging"}


def _template_store_path() -> Path:
    configured = os.getenv("LIPIOCR_TEMPLATE_STORE", "").strip()
    if configured:
        return Path(configured)
    return Path(get_settings().upload_dir) / "_template_studio.json"


def _load_persisted_templates() -> None:
    global _PERSISTED_LOADED
    if _PERSISTED_LOADED or not _template_store_enabled():
        return
    _PERSISTED_LOADED = True
    path = _template_store_path()
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for raw_template in payload.get("templates", []):
        try:
            template = DocumentTemplate.model_validate(raw_template)
        except Exception:
            continue
        if is_system_template(template.document_type):
            continue
        TEMPLATES[template.document_type] = template

    raw_rules = payload.get("validation_rules", {})
    if isinstance(raw_rules, dict):
        for document_type_value, rules in raw_rules.items():
            try:
                document_type = DocumentType(str(document_type_value))
            except ValueError:
                continue
            if is_system_template(document_type):
                continue
            if isinstance(rules, list):
                VALIDATION_RULES[document_type] = rules


def _persist_templates() -> None:
    if not _template_store_enabled():
        return
    path = _template_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "templates": [template.model_dump(mode="json") for template in TEMPLATES.values()],
        "validation_rules": {key.value: value for key, value in VALIDATION_RULES.items()},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def list_templates() -> List[DocumentTemplate]:
    _load_persisted_templates()
    return list(TEMPLATES.values())


def is_system_template(document_type: DocumentType) -> bool:
    return document_type in SYSTEM_TEMPLATE_TYPES


def template_source(document_type: DocumentType) -> str:
    return "system" if is_system_template(document_type) else "custom"


def template_status(document_type: DocumentType) -> str:
    return "permanent" if is_system_template(document_type) else "configured"


def get_template(document_type: DocumentType) -> DocumentTemplate:
    _load_persisted_templates()
    return TEMPLATES[document_type]


def upsert_template(
    *,
    document_type: DocumentType,
    name: str,
    fields: List[TemplateField],
    validation_rules: List[Dict[str, object]],
    allow_system_override: bool = False,
) -> Dict[str, object]:
    _load_persisted_templates()
    if is_system_template(document_type) and not allow_system_override:
        raise HTTPException(status_code=409, detail="This Nepal identity template is permanent and cannot be overwritten")
    TEMPLATES[document_type] = DocumentTemplate(document_type=document_type, name=name, fields=fields)
    VALIDATION_RULES[document_type] = validation_rules
    _persist_templates()
    return {
        "template": {
            "document_type": document_type.value,
            "name": name,
            "field_count": len(fields),
            "required_fields": [field.key for field in fields if field.required],
            "status": template_status(document_type),
            "mode": "template_coordinates",
            "source": template_source(document_type),
            "locked": is_system_template(document_type),
        },
        "validation_rules": validation_rules,
    }


def list_validation_rules() -> Dict[str, List[Dict[str, object]]]:
    _load_persisted_templates()
    return {key.value: value for key, value in VALIDATION_RULES.items()}
