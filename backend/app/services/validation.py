import re
from typing import Dict, Iterable


def route_by_confidence(confidence: float) -> str:
    if confidence >= 0.95:
        return "auto_approved"
    if confidence >= 0.80:
        return "review_required"
    return "manual_entry"


def compute_overall_confidence(fields: Iterable[Dict[str, object]]) -> float:
    required_confidences = [
        float(field.get("confidence", 0.0))
        for field in fields
        if bool(field.get("required", True))
    ]
    if not required_confidences:
        return 0.0
    return round(min(required_confidences), 2)


def validate_field(key: str, value: str, document_type: str) -> Dict[str, str]:
    normalized = value.strip()
    if not normalized:
        return {"status": "missing", "message": "Required value is missing"}

    if key in {"mobile", "phone"}:
        if re.fullmatch(r"9\d{9}", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "invalid", "message": "Mobile number must be 10 digits and start with 9"}

    if key == "email":
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "invalid", "message": "Email address is not valid"}

    if key == "pan":
        if re.fullmatch(r"\d{9}", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "warning", "message": "PAN should be 9 digits when provided"}

    if key in {"citizenship_number", "cheque_number"}:
        if re.fullmatch(r"[A-Za-z0-9\-\/]+", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "invalid", "message": "Identifier contains unsupported characters"}

    if key in {"dob", "date"}:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "warning", "message": "Date should use YYYY-MM-DD"}

    if document_type == "cheque" and key == "amount":
        if re.fullmatch(r"\d+(\.\d{1,2})?", normalized):
            return {"status": "valid", "message": "OK"}
        return {"status": "warning", "message": "Amount should be numeric"}

    return {"status": "valid", "message": "OK"}
