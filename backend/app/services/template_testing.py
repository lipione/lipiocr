from __future__ import annotations

from typing import Iterable

from app.models import ExtractedField, TemplateProfile


def test_template_profile(profile: TemplateProfile, fields: Iterable[ExtractedField | dict[str, object]]) -> dict[str, object]:
    extracted_keys = {
        field.key if isinstance(field, ExtractedField) else str(field.get("key") or "")
        for field in fields
    }
    required_keys = {field.key for field in profile.fields if field.required}
    optional_keys = {field.key for field in profile.fields if not field.required}
    matched_required = required_keys.intersection(extracted_keys)
    matched_optional = optional_keys.intersection(extracted_keys)
    missing_required = sorted(required_keys - matched_required)
    coverage = len(matched_required) / len(required_keys) if required_keys else 1.0

    return {
        "profile_id": profile.id,
        "profile_version": profile.version,
        "status": "pass" if not missing_required else "needs_mapping",
        "required_coverage": round(coverage, 4),
        "matched_required": sorted(matched_required),
        "matched_optional": sorted(matched_optional),
        "missing_required": missing_required,
        "extracted_count": len(extracted_keys),
    }
