from pathlib import Path

import pytest

from app.models import ExtractedField, FinancialDocument, OcrBlock, OcrPage, ValidationStatus
from app.services.address_evidence_store import AddressEvidenceRecord, AddressEvidenceStore
from app.services.address_intelligence import is_address_field_key, suggest_address_corrections
from app.services.document_intelligence import analyze_document, apply_document_intelligence


def _store(tmp_path: Path) -> AddressEvidenceStore:
    return AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_seed_samakhusi",
                tenant_id="system",
                visibility="shared_reference",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Samakhusi",
                aliases_en=["Samakushi", "Samakhusi Chowk"],
                aliases_np=[],
                source="manual_seed",
                confidence_weight=0.84,
            )
        ],
    )


@pytest.mark.parametrize(
    "field_key",
    [
        "address_en",
        "address_np",
        "address_ne",
        "permanent_address_en",
        "permanent_address_np",
        "permanent_address_ne",
        "temporary_address",
        "contact_address",
        "birth_place",
        "ठेगाना",
        "स्थायी ठेगाना",
    ],
)
def test_is_address_field_key_recognizes_localized_address_keys(field_key: str):
    assert is_address_field_key(field_key)


def test_address_candidate_corrects_misspelled_kathmandu_address(tmp_path: Path):
    candidates = suggest_address_corrections(
        "Kathmadu Metropolitian ward 26 Samakushi",
        target_field="permanent_address",
        tenant_id="demo-institution",
        store=_store(tmp_path),
    )

    assert candidates
    top = candidates[0]
    assert top["target_field"] == "permanent_address"
    assert top["suggested_value"] == "Kathmandu Metropolitan City, Ward 26, Samakhusi"
    assert top["structured"]["district"] == "Kathmandu"
    assert top["structured"]["local_level"] == "Kathmandu Metropolitan City"
    assert top["structured"]["ward"] == "26"
    assert top["structured"]["area_or_tole"] == "Samakhusi"
    assert top["confidence"] >= 0.80
    assert "address_evidence_store" in top["sources"]
    assert "score_breakdown" in top


def test_low_context_street_match_does_not_overstate_confidence(tmp_path: Path):
    candidates = suggest_address_corrections(
        "Samakushi",
        target_field="address",
        tenant_id="demo-institution",
        store=_store(tmp_path),
    )

    assert candidates
    assert candidates[0]["confidence"] < 0.80
    assert candidates[0]["status"] == "needs_review"


def test_conflicting_location_context_does_not_merge_unrelated_area(tmp_path: Path):
    candidates = suggest_address_corrections(
        "Pokhara Metropolitan City ward 26 Samakushi",
        target_field="address",
        tenant_id="demo-institution",
        store=_store(tmp_path),
    )

    assert candidates
    top = candidates[0]
    assert not (
        top["status"] == "suggested"
        and top["confidence"] >= 0.80
        and top["structured"].get("area_or_tole") == "Samakhusi"
    )
    if top["confidence"] >= 0.80:
        assert "area_or_tole" not in top["structured"]


def _document_with_address() -> FinancialDocument:
    return FinancialDocument(
        filename="address-form.txt",
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=700,
                blocks=[
                    OcrBlock(
                        text="Permanent Address: Kathmadu Metropolitian ward 26 Samakushi",
                        bbox=[80, 120, 700, 160],
                        confidence=0.74,
                        block_type="field_candidate",
                    )
                ],
            )
        ],
    )


def test_document_intelligence_exposes_address_candidates():
    document = _document_with_address()

    analysis = analyze_document(document)

    assert analysis["address_candidates"]
    candidate = analysis["address_candidates"][0]
    assert candidate["target_field"] in {"permanent_address", "address_en", "address"}
    assert candidate["structured"]["district"] == "Kathmandu"
    assert "address_evidence_store" in candidate["sources"]


def test_apply_document_intelligence_attaches_address_candidates_to_review_field():
    document = _document_with_address()
    field = ExtractedField(
        key="permanent_address",
        label="Permanent Address",
        value="Kathmadu Metropolitian ward 26 Samakushi",
        confidence=0.74,
        validation_status=ValidationStatus.warning,
        validation_message="Needs review",
    )

    analysis = apply_document_intelligence(document, [field])

    assert analysis["address_candidates"]
    assert field.correction_candidates
    assert field.correction_candidates[0]["suggested_value"].startswith("Kathmandu Metropolitan City")
    assert field.original_ocr_value == "Kathmadu Metropolitian ward 26 Samakushi"
