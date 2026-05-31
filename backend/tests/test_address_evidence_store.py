from pathlib import Path

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
