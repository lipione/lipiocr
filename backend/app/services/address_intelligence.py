from __future__ import annotations

import re
from typing import Any

from app.services.address_evidence_store import (
    AddressEvidenceStore,
    load_address_evidence_store,
    normalize_address_text,
)
from app.services.nepal_locations import LocationResolution, resolve_nepal_location


ADDRESS_FIELD_KEYS = frozenset(
    {
        "address",
        "address_en",
        "address_np",
        "address_ne",
        "permanent_address",
        "permanent_address_en",
        "permanent_address_np",
        "permanent_address_ne",
        "temporary_address",
        "contact_address",
        "current_address",
        "mailing_address",
        "residential_address",
        "birth_place",
        "place_of_birth",
        "issue_place",
        "issued_place",
    }
)

ADDRESS_FIELD_LANGUAGE_SUFFIXES = ("_en", "_np", "_ne")
NEPALI_ADDRESS_FIELD_KEYS = frozenset({"ठेगाना", "स्थायी ठेगाना"})


def is_address_field_key(key: str) -> bool:
    raw_key = str(key or "").strip()
    if raw_key in NEPALI_ADDRESS_FIELD_KEYS:
        return True

    normalized = re.sub(r"[^a-z0-9]+", "_", raw_key.lower()).strip("_")
    if normalized in ADDRESS_FIELD_KEYS or normalized.endswith("_address"):
        return True

    base_key = _strip_language_suffix(normalized)
    return base_key in ADDRESS_FIELD_KEYS or base_key.endswith("_address")


def suggest_address_corrections(
    value: object,
    *,
    target_field: str,
    tenant_id: str = "demo-institution",
    store: AddressEvidenceStore | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    original_value = str(value or "").strip()
    if not original_value:
        return []

    evidence_store = store or load_address_evidence_store()
    resolution = resolve_nepal_location(normalize_address_text(original_value))
    location_matched = _location_matched(resolution)
    evidence_matches = _search_evidence(
        evidence_store,
        original_value,
        tenant_id=tenant_id,
        resolution=resolution if location_matched else None,
        limit=limit,
    )

    candidates = [
        _candidate_from_evidence(
            record,
            target_field=target_field,
            original_value=original_value,
            resolution=resolution if location_matched else None,
        )
        for record in evidence_matches
    ]

    if not candidates and location_matched:
        candidates.append(
            _location_only_candidate(target_field=target_field, original_value=original_value, resolution=resolution)
        )

    candidates.sort(
        key=lambda item: (
            -float(item["confidence"]),
            str(item["suggested_value"]),
        )
    )
    return candidates[: max(1, int(limit or 1))]


def _search_evidence(
    store: AddressEvidenceStore,
    value: str,
    *,
    tenant_id: str,
    resolution: LocationResolution | None,
    limit: int,
) -> list[dict[str, Any]]:
    if resolution is None:
        return store.search(value, tenant_id=tenant_id, limit=limit)

    filtered = store.search(
        value,
        tenant_id=tenant_id,
        district=resolution.district_name or "",
        local_level=resolution.local_level_name or "",
        ward=resolution.ward or "",
        limit=limit,
    )
    return filtered


def _strip_language_suffix(key: str) -> str:
    for suffix in ADDRESS_FIELD_LANGUAGE_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def _candidate_from_evidence(
    record: dict[str, Any],
    *,
    target_field: str,
    original_value: str,
    resolution: LocationResolution | None,
) -> dict[str, object]:
    structured = _structured_from_resolution(resolution)
    _fill_structured_from_evidence(structured, record)

    score_breakdown = _score_breakdown(resolution=resolution, record=record)
    confidence = round(sum(score_breakdown.values()), 2)
    sources = ["address_evidence_store"]
    if resolution is not None:
        sources.insert(0, "nepal_location_registry")

    return {
        "target_field": target_field,
        "original_ocr_value": original_value,
        "suggested_value": _suggested_value(structured),
        "structured": structured,
        "confidence": confidence,
        "status": "suggested" if confidence >= 0.80 else "needs_review",
        "sources": sources,
        "score_breakdown": score_breakdown,
        "audit_reason": _audit_reason(confidence, sources, record=record, resolution=resolution),
    }


def _location_only_candidate(
    *,
    target_field: str,
    original_value: str,
    resolution: LocationResolution,
) -> dict[str, object]:
    structured = _structured_from_resolution(resolution)
    score_breakdown = _score_breakdown(resolution=resolution, record=None)
    confidence = round(sum(score_breakdown.values()), 2)
    return {
        "target_field": target_field,
        "original_ocr_value": original_value,
        "suggested_value": _suggested_value(structured),
        "structured": structured,
        "confidence": confidence,
        "status": "suggested" if confidence >= 0.80 else "needs_review",
        "sources": ["nepal_location_registry"],
        "score_breakdown": score_breakdown,
        "audit_reason": _audit_reason(confidence, ["nepal_location_registry"], record=None, resolution=resolution),
    }


def _structured_from_resolution(resolution: LocationResolution | None) -> dict[str, str]:
    if resolution is None:
        return {}

    structured: dict[str, str] = {}
    if resolution.province_name:
        structured["province"] = resolution.province_name
    if resolution.district_name:
        structured["district"] = resolution.district_name
    if resolution.local_level_name:
        structured["local_level"] = resolution.local_level_name
    if resolution.ward:
        structured["ward"] = resolution.ward
    return structured


def _fill_structured_from_evidence(structured: dict[str, str], record: dict[str, Any]) -> None:
    if record.get("province_name"):
        structured.setdefault("province", str(record["province_name"]))
    if record.get("district_name"):
        structured.setdefault("district", str(record["district_name"]))
    if record.get("local_level_name"):
        structured.setdefault("local_level", str(record["local_level_name"]))
    if record.get("ward"):
        structured.setdefault("ward", str(record["ward"]))

    evidence_name = str(record.get("name_en") or record.get("name_np") or record.get("matched_alias") or "").strip()
    if not evidence_name:
        return
    if str(record.get("kind") or "") == "street_or_road":
        structured["street_or_road"] = evidence_name
    else:
        structured["area_or_tole"] = evidence_name


def _score_breakdown(
    *,
    resolution: LocationResolution | None,
    record: dict[str, Any] | None,
) -> dict[str, float]:
    breakdown = {
        "district": 0.0,
        "local_level": 0.0,
        "ward": 0.0,
        "area_or_tole_or_street": 0.0,
        "script_alias": 0.0,
        "reviewed_memory": 0.0,
    }
    if resolution is not None:
        if resolution.district_name:
            breakdown["district"] = 0.25
        if resolution.local_level_name:
            breakdown["local_level"] = 0.25
        if resolution.ward:
            breakdown["ward"] = 0.20

    if record is not None:
        match_score = float(record.get("match_score") or 0.0)
        breakdown["area_or_tole_or_street"] = round(min(0.20, max(0.0, match_score) * 0.20), 2)
        if _has_devanagari(str(record.get("matched_alias") or record.get("name_np") or "")):
            breakdown["script_alias"] = 0.05
        if str(record.get("source") or "") == "reviewer_approved" or record.get("approved_by"):
            breakdown["reviewed_memory"] = 0.05

    return breakdown


def _location_matched(resolution: LocationResolution) -> bool:
    return resolution.status != "unresolved" and any(
        (resolution.district_name, resolution.local_level_name, resolution.ward)
    )


def _suggested_value(structured: dict[str, str]) -> str:
    parts: list[str] = []
    if structured.get("local_level"):
        parts.append(structured["local_level"])
    elif structured.get("district"):
        parts.append(structured["district"])
    elif structured.get("province"):
        parts.append(structured["province"])

    if structured.get("ward"):
        parts.append(f"Ward {structured['ward']}")
    if structured.get("area_or_tole"):
        parts.append(structured["area_or_tole"])
    if structured.get("street_or_road"):
        parts.append(structured["street_or_road"])
    return ", ".join(parts)


def _audit_reason(
    confidence: float,
    sources: list[str],
    *,
    record: dict[str, Any] | None,
    resolution: LocationResolution | None,
) -> str:
    details: list[str] = [f"confidence={confidence:.2f}", "sources=" + ",".join(sources)]
    if resolution is not None and resolution.reasons:
        details.append("location_reasons=" + ",".join(resolution.reasons))
    if record is not None and record.get("matched_alias"):
        details.append(f"matched_alias={record['matched_alias']}")
    return "; ".join(details)


def _has_devanagari(value: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", value))
