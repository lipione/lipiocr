from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import HTTPException


@dataclass(frozen=True)
class ExpandedUploadPage:
    filename: str
    stored_path: Path
    content: bytes
    content_type: str


def _is_pdf_upload(path: Path, content_type: Optional[str]) -> bool:
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    return path.suffix.lower() == ".pdf" or normalized_type == "application/pdf"


def expand_template_upload_pages(
    stored_path: Path,
    *,
    original_filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> list[ExpandedUploadPage]:
    if not _is_pdf_upload(stored_path, content_type):
        return [
            ExpandedUploadPage(
                filename=original_filename or stored_path.name,
                stored_path=stored_path,
                content=stored_path.read_bytes(),
                content_type=content_type or "application/octet-stream",
            )
        ]

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="Multipage PDF template mapping requires PyMuPDF. Install backend dependency 'pymupdf'.",
        ) from exc

    try:
        document = fitz.open(str(stored_path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF could not be opened for template mapping") from exc

    try:
        if len(document) == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages to map")

        base_name = Path(original_filename or stored_path.name).name
        output: list[ExpandedUploadPage] = []
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            page_path = stored_path.with_name(f"{stored_path.stem}-page-{index:03d}.png")
            pixmap.save(str(page_path))
            output.append(
                ExpandedUploadPage(
                    filename=f"{base_name} page {index}",
                    stored_path=page_path,
                    content=page_path.read_bytes(),
                    content_type="image/png",
                )
            )
        return output
    finally:
        document.close()
