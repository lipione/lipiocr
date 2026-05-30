import json
import os
from pathlib import Path
from typing import Dict, List

from app.core.config import get_settings
from app.models import DocumentTemplate, DocumentType, TemplateField


VALIDATION_RULES: Dict[DocumentType, List[Dict[str, object]]] = {}
_PERSISTED_LOADED = False


TEMPLATES: Dict[DocumentType, DocumentTemplate] = {
    DocumentType.citizenship: DocumentTemplate(
        document_type=DocumentType.citizenship,
        name="Citizenship Card",
        fields=[
            TemplateField(key="name", label="Name", required=True, bbox=[120, 170, 520, 215]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[120, 225, 360, 265]),
            TemplateField(
                key="citizenship_number",
                label="Citizenship Number",
                required=True,
                bbox=[470, 120, 760, 165],
            ),
            TemplateField(key="address", label="Address", required=True, bbox=[120, 285, 760, 340]),
            TemplateField(
                key="father_mother_name",
                label="Father/Mother Name",
                required=False,
                bbox=[120, 350, 760, 400],
            ),
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
            TemplateField(key="full_name", label="Full Name", required=True, bbox=[248, 100, 452, 176]),
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[250, 210, 430, 262]),
            TemplateField(key="gender", label="Gender", required=True, bbox=[108, 70, 146, 108]),
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[252, 340, 430, 386]),
            TemplateField(key="father_name", label="Father Name", required=False, bbox=[250, 296, 455, 334]),
            TemplateField(key="mother_name", label="Mother Name", required=False, bbox=[250, 252, 455, 292]),
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
            TemplateField(key="dob", label="Date of Birth", required=True, bbox=[146, 558, 330, 586]),
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[146, 610, 330, 640]),
            TemplateField(key="expiry_date", label="Date of Expiry", required=True, bbox=[146, 640, 330, 670]),
            TemplateField(key="citizenship_number", label="Citizenship Number", required=False, bbox=[360, 558, 540, 590]),
            TemplateField(key="mrz_line_1", label="MRZ Line 1", required=True, bbox=[24, 704, 548, 742]),
            TemplateField(key="mrz_line_2", label="MRZ Line 2", required=False, bbox=[24, 742, 548, 780]),
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
            TemplateField(key="issue_date", label="Date of Issue", required=False, bbox=[78, 308, 236, 344]),
            TemplateField(key="expiry_date", label="Date of Expiry", required=True, bbox=[78, 368, 236, 404]),
            TemplateField(key="citizenship_number", label="Citizenship Number", required=True, bbox=[330, 326, 560, 362]),
            TemplateField(key="category", label="Category", required=True, bbox=[646, 292, 736, 330]),
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
        TEMPLATES[template.document_type] = template

    raw_rules = payload.get("validation_rules", {})
    if isinstance(raw_rules, dict):
        for document_type_value, rules in raw_rules.items():
            try:
                document_type = DocumentType(str(document_type_value))
            except ValueError:
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


def get_template(document_type: DocumentType) -> DocumentTemplate:
    _load_persisted_templates()
    return TEMPLATES[document_type]


def upsert_template(
    *,
    document_type: DocumentType,
    name: str,
    fields: List[TemplateField],
    validation_rules: List[Dict[str, object]],
) -> Dict[str, object]:
    _load_persisted_templates()
    TEMPLATES[document_type] = DocumentTemplate(document_type=document_type, name=name, fields=fields)
    VALIDATION_RULES[document_type] = validation_rules
    _persist_templates()
    return {
        "template": {
            "document_type": document_type.value,
            "name": name,
            "field_count": len(fields),
            "required_fields": [field.key for field in fields if field.required],
            "status": "configured",
            "mode": "template_coordinates",
        },
        "validation_rules": validation_rules,
    }


def list_validation_rules() -> Dict[str, List[Dict[str, object]]]:
    _load_persisted_templates()
    return {key.value: value for key, value in VALIDATION_RULES.items()}
