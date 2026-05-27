from app.services.validation import (
    compute_overall_confidence,
    route_by_confidence,
    validate_field,
)


def test_confidence_routing_matches_bank_review_policy():
    assert route_by_confidence(0.96) == "auto_approved"
    assert route_by_confidence(0.95) == "auto_approved"
    assert route_by_confidence(0.80) == "review_required"
    assert route_by_confidence(0.79) == "manual_entry"


def test_overall_confidence_uses_lowest_required_field_confidence():
    fields = [
        {"key": "name", "required": True, "confidence": 0.94},
        {"key": "email", "required": False, "confidence": 0.60},
        {"key": "citizenship_number", "required": True, "confidence": 0.88},
    ]

    assert compute_overall_confidence(fields) == 0.88


def test_validate_field_flags_bad_mobile_and_valid_email():
    bad_mobile = validate_field("mobile", "98012", "account_opening")
    valid_email = validate_field("email", "customer@example.com", "account_opening")

    assert bad_mobile["status"] == "invalid"
    assert "10 digits" in bad_mobile["message"]
    assert valid_email["status"] == "valid"
    assert valid_email["message"] == "OK"
