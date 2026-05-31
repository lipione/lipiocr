from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.core.config import get_settings
from app.services.calendar_intelligence import normalize_nepali_digits


SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "address_evidence_seed.json"
OCR_SPELLING_OVERRIDES = {
    "metropolitian": "metropolitan",
    "kathmadu": "kathmandu",
    "samakushi": "samakhusi",
}


@dataclass
class AddressEvidenceRecord:
    id: str
    tenant_id: str
    visibility: str
    kind: str
    province_name: str = ""
    district_name: str = ""
    local_level_name: str = ""
    local_level_type: str = ""
    ward: str = ""
    name_en: str = ""
    name_np: str = ""
    aliases_en: list[str] = field(default_factory=list)
    aliases_np: list[str] = field(default_factory=list)
    legacy_aliases: list[str] = field(default_factory=list)
    source: str = "manual_seed"
    confidence_weight: float = 0.75
    approved_by: str = ""
    created_from_document_id: str = ""
    disabled: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AddressEvidenceRecord":
        return cls(
            id=str(payload.get("id") or ""),
            tenant_id=str(payload.get("tenant_id") or "system"),
            visibility=str(payload.get("visibility") or "tenant_private"),
            kind=str(payload.get("kind") or "area_or_tole"),
            province_name=str(payload.get("province_name") or payload.get("province") or ""),
            district_name=str(payload.get("district_name") or payload.get("district") or ""),
            local_level_name=str(payload.get("local_level_name") or payload.get("local_level") or ""),
            local_level_type=str(payload.get("local_level_type") or ""),
            ward=str(payload.get("ward") or ""),
            name_en=str(payload.get("name_en") or ""),
            name_np=str(payload.get("name_np") or ""),
            aliases_en=_string_list(payload.get("aliases_en")),
            aliases_np=_string_list(payload.get("aliases_np")),
            legacy_aliases=_string_list(payload.get("legacy_aliases")),
            source=str(payload.get("source") or "manual_seed"),
            confidence_weight=float(payload.get("confidence_weight") or 0.75),
            approved_by=str(payload.get("approved_by") or ""),
            created_from_document_id=str(payload.get("created_from_document_id") or ""),
            disabled=bool(payload.get("disabled") or False),
        )

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class AddressEvidenceStore:
    def __init__(self, path: str | Path, seed_records: Iterable[AddressEvidenceRecord] | None = None):
        self.path = Path(path)
        self._records: dict[str, AddressEvidenceRecord] = {}
        for record in seed_records or []:
            self._records[record.id] = record
        self._load_persisted_records()

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        district: str = "",
        local_level: str = "",
        ward: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        normalized_query = normalize_address_text(query)
        raw_query = _normalize_address_text(query, apply_ocr_overrides=False)
        if not normalized_query:
            return []

        results: list[dict[str, Any]] = []
        for record in self._records.values():
            if record.disabled or not self._is_visible_to_tenant(record, tenant_id):
                continue
            if not self._matches_filters(record, district=district, local_level=local_level, ward=ward):
                continue

            match = self._best_match(record, normalized_query=normalized_query, raw_query=raw_query)
            if match is None:
                continue

            payload = record.model_dump()
            payload["matched_alias"] = match["matched_alias"]
            payload["match_score"] = round(float(match["match_score"]) * float(record.confidence_weight), 4)
            results.append(payload)

        results.sort(
            key=lambda item: (
                -float(item["match_score"]),
                -float(item.get("confidence_weight") or 0),
                str(item.get("name_en") or item.get("name_np") or item.get("id") or ""),
            )
        )
        return results[:limit]

    def upsert(self, record: AddressEvidenceRecord) -> dict[str, Any]:
        self._records[record.id] = record
        self._persist()
        return record.model_dump()

    def delete(self, record_id: str, *, tenant_id: str | None = None) -> dict[str, Any]:
        record = self._records.get(record_id)
        if record is None:
            return {"id": record_id, "disabled": False, "deleted": False}
        if tenant_id is not None and record.visibility == "tenant_private" and record.tenant_id != tenant_id:
            return {"id": record_id, "disabled": False, "deleted": False}
        record.disabled = True
        self._persist()
        return {"id": record_id, "disabled": True, "deleted": True}

    def _load_persisted_records(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("records", []):
            if isinstance(item, dict):
                record = AddressEvidenceRecord.from_payload(item)
                if record.id:
                    self._records[record.id] = record

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": {"version": 1, "description": "Tenant address evidence store."},
            "records": [record.model_dump() for record in self._records.values()],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _is_visible_to_tenant(record: AddressEvidenceRecord, tenant_id: str) -> bool:
        if record.visibility == "shared_reference":
            return True
        return record.visibility == "tenant_private" and record.tenant_id == tenant_id

    @staticmethod
    def _matches_filters(record: AddressEvidenceRecord, *, district: str, local_level: str, ward: str) -> bool:
        if district and normalize_address_text(record.district_name) != normalize_address_text(district):
            return False
        if local_level and normalize_address_text(record.local_level_name) != normalize_address_text(local_level):
            return False
        if ward and normalize_address_text(record.ward) != normalize_address_text(ward):
            return False
        return True

    @staticmethod
    def _best_match(record: AddressEvidenceRecord, *, normalized_query: str, raw_query: str) -> dict[str, Any] | None:
        candidates = (
            record.aliases_en
            + record.aliases_np
            + record.legacy_aliases
            + [record.name_en, record.name_np, record.local_level_name, record.district_name]
        )
        best: dict[str, Any] | None = None
        for candidate in candidates:
            if not candidate:
                continue
            raw_candidate = _normalize_address_text(candidate, apply_ocr_overrides=False)
            normalized_candidate = normalize_address_text(candidate)
            if raw_query and raw_query == raw_candidate:
                score = 1.0
            elif normalized_query == normalized_candidate:
                score = 0.96
            elif normalized_query in normalized_candidate or normalized_candidate in normalized_query:
                score = 0.82
            else:
                continue
            if best is None or score > float(best["match_score"]):
                best = {"matched_alias": candidate, "match_score": score}
        return best


def normalize_address_text(value: str) -> str:
    return _normalize_address_text(value, apply_ocr_overrides=True)


def load_address_evidence_store() -> AddressEvidenceStore:
    settings = get_settings()
    return AddressEvidenceStore(path=settings.address_evidence_path, seed_records=_load_seed_records())


def import_address_evidence_csv(path: str | Path, tenant_id: str, source: str) -> list[AddressEvidenceRecord]:
    records: list[AddressEvidenceRecord] = []
    with Path(path).open(newline="", encoding="utf-8") as csv_file:
        for index, row in enumerate(csv.DictReader(csv_file), start=1):
            name_en = str(row.get("name_en") or "").strip()
            name_np = str(row.get("name_np") or "").strip()
            district = str(row.get("district") or row.get("district_name") or "").strip()
            local_level = str(row.get("local_level") or row.get("local_level_name") or "").strip()
            ward = str(row.get("ward") or "").strip()
            kind = str(row.get("kind") or "area_or_tole").strip()
            record_id = str(row.get("id") or "").strip() or _record_id(
                tenant_id=tenant_id,
                district=district,
                local_level=local_level,
                ward=ward,
                kind=kind,
                name=name_en or name_np or str(index),
            )
            records.append(
                AddressEvidenceRecord(
                    id=record_id,
                    tenant_id=tenant_id,
                    visibility=str(row.get("visibility") or "tenant_private").strip(),
                    kind=kind,
                    province_name=str(row.get("province") or row.get("province_name") or "").strip(),
                    district_name=district,
                    local_level_name=local_level,
                    local_level_type=str(row.get("local_level_type") or "").strip(),
                    ward=ward,
                    name_en=name_en,
                    name_np=name_np,
                    aliases_en=_split_aliases(row.get("aliases_en")),
                    aliases_np=_split_aliases(row.get("aliases_np")),
                    legacy_aliases=_split_aliases(row.get("legacy_aliases")),
                    source=source,
                    confidence_weight=float(row.get("confidence_weight") or 0.75),
                )
            )
    return records


@lru_cache(maxsize=1)
def _load_seed_records() -> tuple[AddressEvidenceRecord, ...]:
    if not SEED_PATH.exists():
        return ()
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return tuple(
        AddressEvidenceRecord.from_payload(item)
        for item in payload.get("records", [])
        if isinstance(item, dict)
    )


def _normalize_address_text(value: str, *, apply_ocr_overrides: bool) -> str:
    normalized = normalize_nepali_digits(str(value)).lower()
    normalized = re.sub(r"[^0-9a-z\u0900-\u097F]+", " ", normalized)
    tokens = [token for token in normalized.split() if token]
    if apply_ocr_overrides:
        tokens = [OCR_SPELLING_OVERRIDES.get(token, token) for token in tokens]
    return " ".join(tokens)


def _split_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split("|") if part.strip()]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return _split_aliases(value)


def _record_id(*, tenant_id: str, district: str, local_level: str, ward: str, kind: str, name: str) -> str:
    slug = normalize_address_text(" ".join([tenant_id, district, local_level, ward, kind, name]))
    slug = re.sub(r"[^0-9a-z]+", "_", slug).strip("_")
    return f"addr_{slug or 'evidence'}"
