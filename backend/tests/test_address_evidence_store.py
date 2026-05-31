from pathlib import Path

import pytest

from app.services.address_evidence_store import (
    AddressEvidenceRecord,
    AddressEvidenceStore,
    import_address_evidence_csv,
)


def test_store_searches_aliases_and_respects_tenant_scope(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_seed_samakhusi",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Samakhusi",
                name_np="",
                aliases_en=["Samakushi", "Samakhusi Chowk"],
                aliases_np=[],
                source="manual_seed",
                confidence_weight=0.86,
            ),
            AddressEvidenceRecord(
                id="addr_other_tenant",
                tenant_id="other-bank",
                visibility="tenant_private",
                kind="area_or_tole",
                province_name="Bagmati Pradesh",
                district_name="Kathmandu",
                local_level_name="Kathmandu Metropolitan City",
                local_level_type="Mahanagarpalika",
                ward="26",
                name_en="Private Area",
                aliases_en=["Samakushi"],
                aliases_np=[],
                source="reviewer_approved",
            ),
        ],
    )

    results = store.search("Samakushi", tenant_id="demo-institution")

    assert [item["id"] for item in results] == ["addr_seed_samakhusi"]
    assert results[0]["name_en"] == "Samakhusi"
    assert results[0]["matched_alias"] == "Samakushi"


def test_store_upserts_and_persists_reviewer_approved_evidence(tmp_path: Path):
    path = tmp_path / "address_evidence.json"
    store = AddressEvidenceStore(path=path, seed_records=[])

    record = store.upsert(
        AddressEvidenceRecord(
            id="addr_reviewed_01",
            tenant_id="demo-institution",
            visibility="tenant_private",
            kind="street_or_road",
            district_name="Kathmandu",
            local_level_name="Kathmandu Metropolitan City",
            ward="26",
            name_en="Tokha Road",
            aliases_en=["Tokha Rd"],
            aliases_np=[],
            source="reviewer_approved",
            approved_by="reviewer-1",
            created_from_document_id="doc_1",
        )
    )

    reloaded = AddressEvidenceStore(path=path, seed_records=[])

    assert record["id"] == "addr_reviewed_01"
    assert reloaded.search("Tokha Rd", tenant_id="demo-institution")[0]["name_en"] == "Tokha Road"


def test_csv_import_builds_records_with_aliases(tmp_path: Path):
    csv_path = tmp_path / "addresses.csv"
    csv_path.write_text(
        "district,local_level,ward,kind,name_en,aliases_en\n"
        "Kathmandu,Kathmandu Metropolitan City,26,area_or_tole,Samakhusi,Samakushi|Samakhusi Chowk\n",
        encoding="utf-8",
    )

    records = import_address_evidence_csv(csv_path, tenant_id="demo-institution", source="manual_seed")

    assert len(records) == 1
    assert records[0].name_en == "Samakhusi"
    assert records[0].aliases_en == ["Samakushi", "Samakhusi Chowk"]


def test_tenant_cannot_overwrite_another_tenant_private_record_by_id(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_private",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="area_or_tole",
                name_en="Original Area",
                aliases_en=["Original Alias"],
            )
        ],
    )

    with pytest.raises(ValueError, match="Cannot mutate address evidence owned by another tenant"):
        store.upsert(
            AddressEvidenceRecord(
                id="addr_private",
                tenant_id="other-bank",
                visibility="tenant_private",
                kind="area_or_tole",
                name_en="Overwritten Area",
                aliases_en=["Overwritten Alias"],
            )
        )

    assert store.search("Original Alias", tenant_id="demo-institution")[0]["name_en"] == "Original Area"


def test_tenant_cannot_overwrite_shared_reference_seed_by_id(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_shared",
                tenant_id="system",
                visibility="shared_reference",
                kind="area_or_tole",
                name_en="Shared Area",
                aliases_en=["Shared Alias"],
            )
        ],
    )

    with pytest.raises(ValueError, match="Cannot mutate shared address evidence"):
        store.upsert(
            AddressEvidenceRecord(
                id="addr_shared",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="area_or_tole",
                name_en="Tenant Area",
                aliases_en=["Tenant Alias"],
            )
        )

    assert store.search("Shared Alias", tenant_id="demo-institution")[0]["name_en"] == "Shared Area"


def test_tenant_cannot_delete_shared_reference_record(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_shared",
                tenant_id="system",
                visibility="shared_reference",
                kind="area_or_tole",
                name_en="Shared Area",
                aliases_en=["Shared Alias"],
            )
        ],
    )

    with pytest.raises(ValueError, match="Cannot mutate shared address evidence"):
        store.delete("addr_shared", tenant_id="demo-institution")

    assert store.search("Shared Alias", tenant_id="demo-institution")


def test_delete_requires_tenant_context_for_existing_records(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_private",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="area_or_tole",
                name_en="Private Area",
                aliases_en=["Private Alias"],
            )
        ],
    )

    with pytest.raises(ValueError, match="tenant_id is required"):
        store.delete("addr_private")

    assert store.search("Private Alias", tenant_id="demo-institution")


def test_same_tenant_can_update_and_delete_tenant_private_record(tmp_path: Path):
    store = AddressEvidenceStore(
        path=tmp_path / "address_evidence.json",
        seed_records=[
            AddressEvidenceRecord(
                id="addr_private",
                tenant_id="demo-institution",
                visibility="tenant_private",
                kind="street_or_road",
                name_en="Original Road",
                aliases_en=["Original Rd"],
            )
        ],
    )

    updated = store.upsert(
        AddressEvidenceRecord(
            id="addr_private",
            tenant_id="demo-institution",
            visibility="tenant_private",
            kind="street_or_road",
            name_en="Updated Road",
            aliases_en=["Updated Rd"],
        )
    )
    deleted = store.delete("addr_private", tenant_id="demo-institution")

    assert updated["name_en"] == "Updated Road"
    assert deleted == {"id": "addr_private", "disabled": True, "deleted": True}
    assert store.search("Updated Rd", tenant_id="demo-institution") == []
