import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import HTTPException

from app.core.config import get_settings
from app.models import (
    DocumentType,
    ExtractedField,
    OcrPage,
    TemplateDraft,
    TemplateDraftUpdate,
    TemplateField,
    TemplateProfile,
    TemplateProfileField,
    TemplateProfilePage,
)
from app.services.template_intelligence import (
    infer_template_document_type,
    score_template_quality,
    suggest_label_fields,
    suggest_preset_fields,
)
from app.services.templates import upsert_template


_DRAFTS: dict[str, TemplateDraft] = {}
_PROFILES: dict[str, TemplateProfile] = {}
_LOADED = False


def _store_enabled() -> bool:
    configured = os.getenv("LIPIOCR_LOAD_TEMPLATE_STORE", "").strip().lower()
    if configured:
        return configured in {"1", "true", "yes", "on"}
    if os.getenv("LIPIOCR_TEMPLATE_PROFILE_STORE"):
        return True
    return get_settings().environment.lower() in {"production", "staging"}


def _store_path() -> Path:
    configured = os.getenv("LIPIOCR_TEMPLATE_PROFILE_STORE", "").strip()
    if configured:
        return Path(configured)
    return Path(get_settings().upload_dir) / "_template_profiles.json"


def _load() -> None:
    global _LOADED
    if _LOADED or not _store_enabled():
        return
    _LOADED = True
    path = _store_path()
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for raw_draft in payload.get("drafts", []):
        try:
            draft = TemplateDraft.model_validate(raw_draft)
        except Exception:
            continue
        _DRAFTS[draft.id] = draft

    for raw_profile in payload.get("profiles", []):
        try:
            profile = TemplateProfile.model_validate(raw_profile)
        except Exception:
            continue
        _PROFILES[profile.id] = profile


def _persist() -> None:
    if not _store_enabled():
        return
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "drafts": [draft.model_dump(mode="json") for draft in _DRAFTS.values()],
        "profiles": [profile.model_dump(mode="json") for profile in _PROFILES.values()],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def infer_template_field_type(key: str, value: str = "") -> str:
    normalized = f"{key} {value}".lower()
    if any(token in normalized for token in ("date", "dob", "मिति")):
        return "date"
    if any(token in normalized for token in ("amount", "रकम", "rs.")):
        return "amount"
    if any(token in normalized for token in ("mobile", "phone", "contact")):
        return "phone"
    if "email" in normalized or "@" in value:
        return "email"
    if any(token in normalized for token in ("name", "नाम")):
        return "name"
    if any(token in normalized for token in ("address", "ठेगाना")):
        return "address"
    if any(token in normalized for token in ("photo", "image")):
        return "photo"
    if "signature" in normalized or "दस्तखत" in normalized:
        return "signature"
    if re.fullmatch(r"[\d\s,./:-]+", value.strip()):
        return "number"
    return "text"


def _field_from_extraction(field: ExtractedField, page_number: int) -> TemplateProfileField:
    bbox = field.evidence.bbox or field.bbox or [80, 100, 420, 140]
    return TemplateProfileField(
        key=field.key,
        label=field.label,
        page_number=page_number,
        bbox=[int(value) for value in bbox[:4]],
        type=infer_template_field_type(field.key, field.value),
        required=field.required,
        language_hint="ne" if field.key.endswith(("_np", "_ne")) else "en" if field.key.endswith("_en") else "mixed",
        validation_rule=field.validation_status.value if field.validation_status else None,
        extraction_hint=field.evidence.evidence_text,
        confidence=field.confidence,
        detection_source="extraction",
        detection_reason=f"Suggested from extracted field '{field.label}' with OCR evidence.",
    )


def build_template_pages(
    pages: Iterable[OcrPage],
    *,
    filename: str,
    stored_name: Optional[str],
    start_at: int,
) -> List[TemplateProfilePage]:
    output: list[TemplateProfilePage] = []
    for offset, page in enumerate(pages):
        output.append(
            TemplateProfilePage(
                page_number=start_at + offset,
                filename=filename,
                stored_name=stored_name,
                image_uri=page.image_uri,
                width=page.width,
                height=page.height,
                ocr_confidence=page.ocr_confidence,
                blocks=page.blocks,
            )
        )
    return output


def create_template_draft(
    *,
    name: str,
    document_type: DocumentType,
    pages: List[TemplateProfilePage],
    extracted_fields: List[ExtractedField],
) -> TemplateDraft:
    _load()
    detected_type, type_confidence, type_reason = infer_template_document_type(pages, document_type)
    fields_by_identity: dict[tuple[str, int], TemplateProfileField] = {}
    label_fields = suggest_label_fields(pages)
    for field in label_fields:
        identity = (field.key, field.page_number)
        previous = fields_by_identity.get(identity)
        if previous is not None and previous.confidence > field.confidence:
            continue
        fields_by_identity[identity] = field

    preset_fields = suggest_preset_fields(pages, detected_type)
    pages_by_number = {page.page_number: page for page in pages}
    for field in preset_fields:
        identity = (field.key, field.page_number)
        previous = fields_by_identity.get(identity)
        page = pages_by_number.get(field.page_number)
        if (
            previous is not None
            and previous.confidence >= field.confidence
            and not _is_synthetic_wide_label_field(previous, page)
        ):
            continue
        fields_by_identity[identity] = field

    if not fields_by_identity:
        for field in extracted_fields:
            if field.key.startswith("ocr_line_") or field.source in {"full_page_ocr", "handwriting_ocr"}:
                continue
            page_number = field.evidence.source_page or 1
            identity = (field.key, page_number)
            if identity in fields_by_identity:
                continue
            fields_by_identity[identity] = _field_from_extraction(field, page_number)

    fields = sorted(fields_by_identity.values(), key=lambda item: (item.page_number, item.bbox[1], item.bbox[0], item.key))
    quality_score, quality_checks = score_template_quality(fields, pages)
    draft = TemplateDraft(
        name=name,
        document_type=detected_type,
        document_type_confidence=type_confidence,
        document_type_reason=type_reason,
        quality_score=quality_score,
        quality_checks=quality_checks,
        pages=pages,
        fields=fields,
    )
    _DRAFTS[draft.id] = draft
    _persist()
    return draft


def get_template_draft(draft_id: str) -> TemplateDraft:
    _load()
    draft = _DRAFTS.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Template draft not found")
    return draft


def _is_synthetic_wide_label_field(field: TemplateProfileField, page: Optional[TemplateProfilePage]) -> bool:
    if page is None or field.detection_source != "label_intelligence" or len(field.bbox) < 4:
        return False
    if (
        not page.image_uri
        and (page.filename.lower().endswith(".txt") or bool(page.stored_name and page.stored_name.lower().endswith(".txt")))
    ):
        return False
    width = max(0, field.bbox[2] - field.bbox[0])
    return width >= page.width * 0.70


def update_template_draft(draft_id: str, update: TemplateDraftUpdate) -> TemplateDraft:
    draft = get_template_draft(draft_id)
    if update.name is not None:
        draft.name = update.name
    if update.document_type is not None:
        draft.document_type = update.document_type
    if update.fields is not None:
        draft.fields = update.fields
        draft.quality_score, draft.quality_checks = score_template_quality(draft.fields, draft.pages)
    draft.updated_at = datetime.utcnow()
    _DRAFTS[draft.id] = draft
    _persist()
    return draft


def publish_template_draft(
    draft_id: str,
    *,
    tenant_id: str = "demo-institution",
    actor: str = "system",
    allow_system_override: bool = False,
) -> tuple[TemplateProfile, dict[str, object]]:
    draft = get_template_draft(draft_id)
    profile = TemplateProfile(
        name=draft.name,
        document_type=draft.document_type,
        tenant_id=tenant_id,
        approval_status="approved",
        approved_by=actor,
        approved_at=datetime.utcnow(),
        quality_score=draft.quality_score,
        quality_checks=draft.quality_checks,
        pages=draft.pages,
        fields=draft.fields,
    )
    draft.status = "published"
    draft.updated_at = datetime.utcnow()
    _DRAFTS[draft.id] = draft
    _PROFILES[profile.id] = profile

    template_result = upsert_template(
        document_type=profile.document_type,
        name=profile.name,
        fields=[
            TemplateField(key=field.key, label=field.label, required=field.required, bbox=field.bbox)
            for field in profile.fields
        ],
        validation_rules=[
            {"field_key": field.key, "rule": field.validation_rule or field.type, "severity": "warning"}
            for field in profile.fields
            if field.validation_rule or field.type
        ],
        allow_system_override=allow_system_override,
    )
    _persist()
    return profile, template_result


def list_template_profiles(*, tenant_id: Optional[str] = None) -> list[TemplateProfile]:
    _load()
    profiles = list(_PROFILES.values())
    if tenant_id:
        profiles = [profile for profile in profiles if profile.tenant_id == tenant_id]
    return sorted(profiles, key=lambda item: item.updated_at, reverse=True)


def get_template_profile(profile_id: str) -> TemplateProfile:
    _load()
    profile = _PROFILES.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Template profile not found")
    return profile


def approve_template_profile(profile_id: str, *, actor: str) -> TemplateProfile:
    profile = get_template_profile(profile_id)
    profile.approval_status = "approved"
    profile.approved_by = actor
    profile.approved_at = datetime.utcnow()
    profile.status = "published"
    profile.updated_at = datetime.utcnow()
    _PROFILES[profile.id] = profile
    _persist()
    return profile


def rollback_template_profile(profile_id: str, *, target_version: int, actor: str) -> TemplateProfile:
    profile = get_template_profile(profile_id)
    if target_version < 1 or target_version > profile.version:
        raise HTTPException(status_code=400, detail="Target version is outside template history")
    profile.version += 1
    profile.rollback_of = target_version
    profile.approval_status = "approved"
    profile.approved_by = actor
    profile.approved_at = datetime.utcnow()
    profile.status = "published"
    profile.updated_at = datetime.utcnow()
    _PROFILES[profile.id] = profile
    _persist()
    return profile


def export_template_profile(profile_id: str) -> dict[str, object]:
    profile = get_template_profile(profile_id)
    return {
        "format": "lipiocr.template-profile.v1",
        "profile": profile.model_dump(mode="json"),
    }


def import_template_profile(payload: dict[str, object], *, tenant_id: str, actor: str) -> TemplateProfile:
    raw_profile = payload.get("profile") if payload.get("format") else payload
    if not isinstance(raw_profile, dict):
        raise HTTPException(status_code=400, detail="Template profile payload is invalid")
    profile = TemplateProfile.model_validate(raw_profile)
    profile.id = f"tpl_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    profile.tenant_id = tenant_id
    profile.version = max(1, int(profile.version))
    profile.status = "published"
    profile.approval_status = "approved"
    profile.approved_by = actor
    profile.approved_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()
    _PROFILES[profile.id] = profile
    _persist()
    return profile


def template_profile_summaries() -> list[dict[str, object]]:
    return [
        {
            "id": profile.id,
            "name": profile.name,
            "document_type": profile.document_type.value,
            "version": profile.version,
            "status": profile.status,
            "page_count": len(profile.pages),
            "field_count": len(profile.fields),
            "quality_score": profile.quality_score,
            "updated_at": profile.updated_at.isoformat(),
        }
        for profile in list_template_profiles()
    ]
