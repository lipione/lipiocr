from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException


@dataclass(frozen=True)
class UploadPolicy:
    max_bytes: int = 25 * 1024 * 1024
    allowed_mime_types: set[str] | None = None
    allowed_extensions: set[str] | None = None

    def __post_init__(self) -> None:
        if self.allowed_mime_types is None:
            object.__setattr__(
                self,
                "allowed_mime_types",
                {
                    "application/pdf",
                    "image/avif",
                    "image/bmp",
                    "image/gif",
                    "image/jpeg",
                    "image/png",
                    "image/tiff",
                    "image/webp",
                    "text/plain",
                },
            )
        if self.allowed_extensions is None:
            object.__setattr__(
                self,
                "allowed_extensions",
                {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff", ".txt", ".webp"},
            )


def _split_csv(value: str | Iterable[str]) -> set[str]:
    if isinstance(value, str):
        return {item.strip().lower() for item in value.split(",") if item.strip()}
    return {str(item).strip().lower() for item in value if str(item).strip()}


def upload_policy_from_settings(settings) -> UploadPolicy:
    return UploadPolicy(
        max_bytes=int(getattr(settings, "max_upload_bytes", UploadPolicy.max_bytes)),
        allowed_mime_types=_split_csv(getattr(settings, "allowed_upload_mime_types", "")) or None,
        allowed_extensions=_split_csv(getattr(settings, "allowed_upload_extensions", "")) or None,
    )


def validate_upload_policy(
    filename: str | None,
    content_type: str | None,
    content: bytes,
    policy: UploadPolicy,
) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="Upload file is empty")
    if len(content) > policy.max_bytes:
        raise HTTPException(status_code=413, detail="Upload file is too large")

    suffix = Path(filename or "").suffix.lower()
    if not suffix or suffix not in (policy.allowed_extensions or set()):
        raise HTTPException(status_code=415, detail="Upload file extension is not supported")

    normalized_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_type not in (policy.allowed_mime_types or set()):
        raise HTTPException(status_code=415, detail="Upload content type is not supported")
