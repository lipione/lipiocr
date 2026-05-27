from typing import Dict, List

from app.models import DocumentTemplate, ExtractedField
from app.services.ocr import OcrObservation
from app.services.validation import validate_field


def extract_fields(template: DocumentTemplate, observations: List[OcrObservation]) -> List[ExtractedField]:
    by_key: Dict[str, OcrObservation] = {
        str(observation.get("field_key")): observation for observation in observations
    }

    fields: List[ExtractedField] = []
    raw_text = "\n".join(str(observation.get("text", "")) for observation in observations)

    for template_field in template.fields:
        observation = by_key.get(template_field.key)
        value = str(observation.get("text", "")) if observation else ""
        confidence = float(observation.get("confidence", 0.0)) if observation else 0.0
        validation = validate_field(template_field.key, value, template.document_type.value)
        fields.append(
            ExtractedField(
                key=template_field.key,
                label=template_field.label,
                value=value,
                confidence=round(confidence, 2),
                required=template_field.required,
                source="template",
                validation_status=validation["status"],
                validation_message=validation["message"],
                bbox=template_field.bbox,
            )
        )

    if not any(field.value for field in fields) and raw_text:
        fields.append(
            ExtractedField(
                key="raw_text",
                label="Raw OCR Text",
                value=raw_text,
                confidence=0.50,
                required=False,
                source="ocr",
                validation_status="warning",
                validation_message="Raw OCR text requires reviewer mapping",
            )
        )

    return fields
