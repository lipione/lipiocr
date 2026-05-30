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
    seen: set[tuple[str, int]] = set()
    fields: list[TemplateProfileField] = []
    for field in extracted_fields:
        if field.key.startswith("ocr_line_") or field.source in {"full_page_ocr", "handwriting_ocr"}:
            continue
        page_number = field.evidence.source_page or 1
        identity = (field.key, page_number)
        if identity in seen:
            continue
        seen.add(identity)
        fields.append(_field_from_extraction(field, page_number))

    draft = TemplateDraft(name=name, document_type=document_type, pages=pages, fields=fields)
    _DRAFTS[draft.id] = draft
    _persist()
    return draft


def get_template_draft(draft_id: str) -> TemplateDraft:
    _load()
    draft = _DRAFTS.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Template draft not found")
    return draft


def update_template_draft(draft_id: str, update: TemplateDraftUpdate) -> TemplateDraft:
    draft = get_template_draft(draft_id)
    if update.name is not None:
        draft.name = update.name
    if update.document_type is not None:
        draft.document_type = update.document_type
    if update.fields is not None:
        draft.fields = update.fields
    draft.updated_at = datetime.utcnow()
    _DRAFTS[draft.id] = draft
    _persist()
    return draft


def publish_template_draft(draft_id: str) -> tuple[TemplateProfile, dict[str, object]]:
    draft = get_template_draft(draft_id)
    profile = TemplateProfile(
        name=draft.name,
        document_type=draft.document_type,
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
    )
    _persist()
    return profile, template_result


def list_template_profiles() -> list[TemplateProfile]:
    _load()
    return sorted(_PROFILES.values(), key=lambda item: item.updated_at, reverse=True)


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
            "updated_at": profile.updated_at.isoformat(),
        }
        for profile in list_template_profiles()
    ]
