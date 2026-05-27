from typing import Dict, List

from app.models import DocumentTemplate, DocumentType, TemplateField


VALIDATION_RULES: Dict[DocumentType, List[Dict[str, object]]] = {}


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
}


def list_templates() -> List[DocumentTemplate]:
    return list(TEMPLATES.values())


def get_template(document_type: DocumentType) -> DocumentTemplate:
    return TEMPLATES[document_type]


def upsert_template(
    *,
    document_type: DocumentType,
    name: str,
    fields: List[TemplateField],
    validation_rules: List[Dict[str, object]],
) -> Dict[str, object]:
    TEMPLATES[document_type] = DocumentTemplate(document_type=document_type, name=name, fields=fields)
    VALIDATION_RULES[document_type] = validation_rules
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
    return {key.value: value for key, value in VALIDATION_RULES.items()}
