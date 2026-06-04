from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from app.services.calendar_intelligence import normalize_nepali_digits


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "nepal_locations.json"

DISPLAY_NAME_CORRECTIONS = {
    "Chitawan": "Chitwan",
}

PRADESH_CANONICAL_NAMES = {
    "1": "Koshi Pradesh",
    "2": "Madhesh Pradesh",
    "3": "Bagmati Pradesh",
    "4": "Gandaki Pradesh",
    "5": "Lumbini Pradesh",
    "6": "Karnali Pradesh",
    "7": "Sudurpashchim Pradesh",
}

NEPALI_LOCATION_ALIASES = {
    "काठमाडौँ": "kathmandu",
    "काठमाडौं": "kathmandu",
    "काठमाण्डौ": "kathmandu",
    "काठमाण्डौँ": "kathmandu",
    "भक्तपुर": "bhaktapur",
    "ललितपुर": "lalitpur",
    "चितवन": "chitwan",
    "झापा": "jhapa",
    "पोखरा": "pokhara",
    "मध्यपुर": "madhyapur",
    "थिमी": "thimi",
}

LOCAL_TYPE_ALIASES = {
    "Mahanagarpalika": ("metropolitan city", "metropolitan", "mahanagarpalika", "महा नगरपालिका", "म न पा"),
    "Upamahanagarpalika": ("sub metropolitan city", "sub-metropolitan", "upamahanagarpalika", "उप महानगरपालिका"),
    "Nagarpalika": ("municipality", "nagar palika", "nagarpalika", "नगरपालिका", "न पा"),
    "Gaunpalika": ("rural municipality", "gaunpalika", "gaupalika", "गाउँपालिका", "गा पा"),
}

LEGACY_VDC_ALIASES = ("vdc", "v d c", "ga vi sa", "गा वि स")


@dataclass(frozen=True)
class ProvinceUnit:
    code: str
    name_en: str
    name_np: str
    canonical_name: str


@dataclass(frozen=True)
class DistrictUnit:
    code: str
    name_en: str
    name_np: str
    province_code: str
    province_name: str


@dataclass(frozen=True)
class LocalLevelUnit:
    code: str
    name_en: str
    name_np: str
    key: str
    type: str
    district_code: str
    province_code: str
    province_name: str


@dataclass(frozen=True)
class LocationResolution:
    raw_text: str
    normalized_text: str
    status: str = "unresolved"
    confidence: float = 0.0
    province_code: Optional[str] = None
    province_name: Optional[str] = None
    district_code: Optional[str] = None
    district_name: Optional[str] = None
    district_name_np: Optional[str] = None
    local_level_code: Optional[str] = None
    local_level_name: Optional[str] = None
    local_level_name_np: Optional[str] = None
    local_level_key: Optional[str] = None
    local_level_type: Optional[str] = None
    ward: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_fields(self, prefix: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        if self.province_name:
            fields[f"{prefix}_province"] = self.province_name
        if self.district_name:
            fields[f"{prefix}_district"] = self.district_name
        if self.local_level_key:
            fields[f"{prefix}_local_level"] = self.local_level_key
        if self.local_level_name:
            fields[f"{prefix}_local_level_name"] = self.local_level_name
        if self.local_level_type:
            fields[f"{prefix}_local_level_type"] = self.local_level_type
        if self.ward:
            fields[f"{prefix}_ward"] = self.ward
        return fields

    def model_dump(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "status": self.status,
            "confidence": self.confidence,
            "province_code": self.province_code,
            "province_name": self.province_name,
            "district_code": self.district_code,
            "district_name": self.district_name,
            "district_name_np": self.district_name_np,
            "local_level_code": self.local_level_code,
            "local_level_name": self.local_level_name,
            "local_level_name_np": self.local_level_name_np,
            "local_level_key": self.local_level_key,
            "local_level_type": self.local_level_type,
            "ward": self.ward,
            "warnings": list(self.warnings),
            "reasons": list(self.reasons),
        }


class NepalLocationRegistry:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.metadata = payload.get("metadata", {})
        self.provinces = [
            ProvinceUnit(
                code=str(item["code"]),
                name_en=str(item["name_en"]),
                name_np=str(item["name_np"]),
                canonical_name=PRADESH_CANONICAL_NAMES.get(str(item["code"]), str(item["name_en"])),
            )
            for item in payload.get("provinces", [])
        ]
        self.districts = [
            DistrictUnit(
                code=str(item["code"]),
                name_en=_clean_display_name(str(item["name_en"])),
                name_np=str(item["name_np"]),
                province_code=str(item["province_code"]),
                province_name=PRADESH_CANONICAL_NAMES.get(str(item["province_code"]), str(item.get("province_name_en") or "")),
            )
            for item in payload.get("districts", [])
        ]
        self.local_levels = [
            LocalLevelUnit(
                code=str(item["code"]),
                name_en=_clean_display_name(str(item["name_en"])),
                name_np=str(item["name_np"]),
                key=str(item["key"]),
                type=str(item["type"] or ""),
                district_code=str(item["district_code"]),
                province_code=str(item["province_code"]),
                province_name=PRADESH_CANONICAL_NAMES.get(str(item["province_code"]), str(item.get("province_name_en") or "")),
            )
            for item in payload.get("local_levels", [])
        ]
        self.district_by_code = {district.code: district for district in self.districts}
        self.province_by_code = {province.code: province for province in self.provinces}
        self._district_aliases = self._build_district_aliases()
        self._local_aliases = self._build_local_aliases()

    def _build_district_aliases(self) -> list[tuple[str, DistrictUnit]]:
        aliases: list[tuple[str, DistrictUnit]] = []
        for district in self.districts:
            aliases.extend((_normalize_location_text(alias), district) for alias in _district_aliases(district))
        return sorted(_dedupe_aliases(aliases), key=lambda item: len(item[0]), reverse=True)

    def _build_local_aliases(self) -> list[tuple[str, LocalLevelUnit]]:
        aliases: list[tuple[str, LocalLevelUnit]] = []
        for local_level in self.local_levels:
            aliases.extend((_normalize_location_text(alias), local_level) for alias in _local_level_aliases(local_level))
        return sorted(_dedupe_aliases(aliases), key=lambda item: len(item[0]), reverse=True)

    def summary(self) -> dict[str, int]:
        return {
            "provinces": len(self.provinces),
            "districts": len(self.districts),
            "local_levels": len(self.local_levels),
        }

    def search(self, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        normalized_query = _normalize_location_text(query)
        limit = max(1, min(limit, 1000))
        scored: list[tuple[int, dict[str, object]]] = []
        for local_level in self.local_levels:
            district = self.district_by_code.get(local_level.district_code)
            haystack = _normalize_location_text(
                " ".join(
                    value
                    for value in (
                        local_level.key,
                        local_level.name_en,
                        local_level.name_np,
                        local_level.type,
                        district.name_en if district else "",
                        district.name_np if district else "",
                        local_level.province_name,
                    )
                    if value
                )
            )
            if normalized_query and normalized_query not in haystack:
                continue
            score = 0
            if normalized_query:
                if haystack.startswith(normalized_query):
                    score += 50
                if f" {normalized_query}" in haystack:
                    score += 25
                score += len(normalized_query)
            scored.append((score, _local_level_reference(local_level, district)))
        scored.sort(key=lambda item: (-item[0], str(item[1]["local_level_key"])))
        return [item for _, item in scored[:limit]]

    def resolve(self, text: str) -> LocationResolution:
        normalized = _normalize_location_text(text)
        district = _explicit_district_match(normalized, self._district_aliases) or _best_unit_match(
            normalized, self._district_aliases
        )
        local_level = _best_unit_match(normalized, self._local_aliases)
        ward = _extract_ward(normalized)

        reasons: list[str] = []
        warnings: list[str] = []
        if district:
            reasons.append("district_matched")
        if local_level:
            reasons.append("local_level_matched")
        if ward:
            reasons.append("ward_matched")
        if _has_legacy_vdc_term(normalized):
            reasons.append("legacy_vdc_term_detected")

        if district is None and local_level is not None:
            district = self.district_by_code.get(local_level.district_code)
            if district:
                reasons.append("district_inferred_from_local_level")

        province_code = district.province_code if district else local_level.province_code if local_level else None
        province_name = PRADESH_CANONICAL_NAMES.get(str(province_code), None) if province_code else None

        if district and local_level and district.code != local_level.district_code:
            warnings.append("district_local_level_mismatch")

        matched_count = sum(1 for value in (province_name, district, local_level, ward) if value)
        confidence = round(min(0.97, 0.42 + matched_count * 0.14), 2)
        if district and local_level:
            confidence = max(confidence, 0.90)
        if warnings:
            status = "needs_review"
            confidence = round(min(confidence, 0.72), 2)
        elif local_level or district:
            status = "matched"
        else:
            status = "unresolved"
            confidence = 0.20

        return LocationResolution(
            raw_text=text,
            normalized_text=normalized,
            status=status,
            confidence=confidence,
            province_code=province_code,
            province_name=province_name,
            district_code=district.code if district else None,
            district_name=district.name_en if district else None,
            district_name_np=district.name_np if district else None,
            local_level_code=local_level.code if local_level else None,
            local_level_name=local_level.name_en if local_level else None,
            local_level_name_np=local_level.name_np if local_level else None,
            local_level_key=local_level.key if local_level else None,
            local_level_type=local_level.type if local_level else None,
            ward=ward,
            warnings=warnings,
            reasons=reasons,
        )


def _clean_display_name(value: str) -> str:
    cleaned = value.replace("Metropolitian", "Metropolitan").strip()
    return DISPLAY_NAME_CORRECTIONS.get(cleaned, cleaned)


def _local_level_reference(local_level: LocalLevelUnit, district: DistrictUnit | None) -> dict[str, object]:
    return {
        "province_code": local_level.province_code,
        "province_name": local_level.province_name,
        "district_code": local_level.district_code,
        "district_name": district.name_en if district else None,
        "local_level_code": local_level.code,
        "local_level_key": local_level.key,
        "local_level_name": local_level.name_en,
        "local_level_name_np": local_level.name_np,
        "local_level_type": local_level.type,
    }


def _normalize_location_text(value: str) -> str:
    normalized = normalize_nepali_digits(value).lower()
    normalized = normalized.replace("metropolitian", "metropolitan")
    normalized = normalized.replace("sub-metropolitan", "sub metropolitan")
    for nepali, english in NEPALI_LOCATION_ALIASES.items():
        normalized = normalized.replace(nepali, english)
    normalized = re.sub(r"[।,;()\\[\\]{}]+", " ", normalized)
    normalized = re.sub(r"[:：./\\-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _dedupe_aliases(aliases: Iterable[tuple[str, Any]]) -> list[tuple[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, Any]] = []
    for alias, unit in aliases:
        alias = alias.strip()
        if len(alias) < 2:
            continue
        identity = (alias, getattr(unit, "code", ""))
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append((alias, unit))
    return deduped


def _district_aliases(district: DistrictUnit) -> list[str]:
    return [district.name_en, district.name_np]


def _strip_local_suffix(value: str) -> str:
    normalized = _normalize_location_text(value)
    suffixes = (
        "metropolitan city",
        "sub metropolitan city",
        "municipality",
        "rural municipality",
        "mahanagarpalika",
        "upamahanagarpalika",
        "nagarpalika",
        "gaunpalika",
        "महानगरपालिका",
        "उप महानगरपालिका",
        "नगरपालिका",
        "गाउँपालिका",
    )
    for suffix in suffixes:
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)].strip()
    return normalized


def _local_level_aliases(local_level: LocalLevelUnit) -> list[str]:
    base_names = {
        local_level.name_en,
        local_level.name_np,
        local_level.key,
        _strip_local_suffix(local_level.name_en),
        _strip_local_suffix(local_level.name_np),
    }
    aliases: set[str] = set()
    type_aliases = LOCAL_TYPE_ALIASES.get(local_level.type, ())
    for name in base_names:
        if not name:
            continue
        aliases.add(name)
        normalized_name = _normalize_location_text(name)
        for type_alias in type_aliases:
            aliases.add(f"{normalized_name} {type_alias}")
    return list(aliases)


def _best_unit_match(normalized_text: str, aliases: list[tuple[str, Any]]) -> Any | None:
    best: tuple[int, Any] | None = None
    for alias, unit in aliases:
        if not alias or alias not in normalized_text:
            continue
        score = len(alias)
        if re.search(rf"(?:^|\s){re.escape(alias)}(?:\s|$)", normalized_text):
            score += 25
        if best is None or score > best[0]:
            best = (score, unit)
    return best[1] if best else None


def _explicit_district_match(normalized_text: str, aliases: list[tuple[str, Any]]) -> Any | None:
    for marker in ("district", "जिल्ला"):
        for alias, unit in aliases:
            if re.search(rf"(?:^|\s){marker}\s+{re.escape(alias)}(?:\s|$)", normalized_text):
                return unit
    return None


def _extract_ward(normalized_text: str) -> Optional[str]:
    match = re.search(r"(?:ward\s*no|ward|वडा\s*नं|वडा\s*न|वडा)\s*([0-9]{1,2})", normalized_text)
    if not match:
        return None
    ward = int(match.group(1))
    if ward < 1 or ward > 35:
        return None
    return str(ward)


def _has_legacy_vdc_term(normalized_text: str) -> bool:
    return any(re.search(rf"(?:^|\s){re.escape(alias)}(?:\s|$)", normalized_text) for alias in LEGACY_VDC_ALIASES)


@lru_cache(maxsize=1)
def location_registry() -> NepalLocationRegistry:
    return NepalLocationRegistry(json.loads(DATA_PATH.read_text(encoding="utf-8")))


def resolve_nepal_location(text: str) -> LocationResolution:
    return location_registry().resolve(text)
