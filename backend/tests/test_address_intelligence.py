from pathlib import Path

from app.services.address_evidence_store import AddressEvidenceRecord, AddressEvidenceStore
from app.services.address_intelligence import suggest_address_corrections


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
