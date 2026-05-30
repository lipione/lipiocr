from app.models import EvidenceRef, ExtractedField
from app.services.calendar_intelligence import apply_calendar_intelligence, convert_calendar_date


def _field(key: str, value: str, evidence_text: str = "") -> ExtractedField:
    return ExtractedField(
        key=key,
        label=key.replace("_", " ").title(),
        value=value,
        confidence=0.82,
        evidence=EvidenceRef(document_id="doc_test", evidence_text=evidence_text or value),
        document_id="doc_test",
    )


def test_convert_calendar_date_handles_bs_and_ad_values():
    bs_conversion = convert_calendar_date("२०४९-०१-०१", context="जन्म मिति")
    assert bs_conversion is not None
    assert bs_conversion.calendar == "bs"
    assert bs_conversion.bs == "2049-01-01"
    assert bs_conversion.ad == "1992-04-13"

    ad_conversion = convert_calendar_date("2023-05-13", context="application date")
    assert ad_conversion is not None
    assert ad_conversion.calendar == "ad"
    assert ad_conversion.ad == "2023-05-13"
    assert ad_conversion.bs == "2080-01-30"


def test_apply_calendar_intelligence_adds_export_ready_ad_and_bs_sibling_fields():
    fields = [
        _field("dob", "२०४९/०१/०१", "जन्म मिति: २०४९/०१/०१"),
        _field("application_date", "2023-05-13", "Application Date: 2023-05-13"),
    ]

    apply_calendar_intelligence(fields)

    by_key = {field.key: field for field in fields}

    assert by_key["dob_bs"].value == "2049-01-01"
    assert by_key["dob_ad"].value == "1992-04-13"
    assert by_key["application_date_ad"].value == "2023-05-13"
    assert by_key["application_date_bs"].value == "2080-01-30"
    assert by_key["dob_ad"].source == "calendar_intelligence"
    assert by_key["application_date_bs"].evidence.document_id == "doc_test"


def test_apply_calendar_intelligence_refreshes_existing_derived_fields_after_review():
    fields = [
        _field("issue_date", "2080-01-30", "जारी मिति: २०८०-०१-३०"),
        _field("issue_date_ad", "2020-01-01"),
        _field("issue_date_bs", "2076-09-16"),
    ]

    apply_calendar_intelligence(fields)

    by_key = {field.key: field for field in fields}

    assert by_key["issue_date_ad"].value == "2023-05-13"
    assert by_key["issue_date_bs"].value == "2080-01-30"
    assert by_key["issue_date_ad"].confidence == 0.82
    assert by_key["issue_date_ad"].validation_status == "valid"
