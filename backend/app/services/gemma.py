import json
import re
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models import (
    CaseType,
    DocumentType,
    EvidenceRef,
    ExtractedField,
    OcrPage,
    ValidationFinding,
)


JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


class GemmaExtractionResult(BaseModel):
    document_type: DocumentType = DocumentType.unknown
    summary: str = ""
    fields: List[ExtractedField] = Field(default_factory=list)
    findings: List[ValidationFinding] = Field(default_factory=list)


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    cleaned = JSON_FENCE_RE.sub("", cleaned).strip()
    if cleaned.startswith("Here is"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    return cleaned


def _field_from_gemma(raw: Dict[str, Any]) -> ExtractedField:
    bbox = raw.get("bbox")
    evidence = EvidenceRef(
        source_page=int(raw.get("source_page") or 1),
        bbox=bbox if isinstance(bbox, list) else None,
        evidence_text=str(raw.get("evidence_text") or raw.get("value") or ""),
    )
    return ExtractedField(
        key=str(raw.get("key") or raw.get("field") or "unknown"),
        label=str(raw.get("label") or raw.get("key") or "Unknown"),
        value=str(raw.get("value") or ""),
        confidence=round(float(raw.get("confidence") or 0.0), 2),
        required=bool(raw.get("required", True)),
        source="gemma_reasoning",
        bbox=evidence.bbox,
        evidence=evidence,
        extracted_by="gemma-4-26b-4bit",
    )


def parse_gemma_extraction(content: str) -> GemmaExtractionResult:
    payload = json.loads(_clean_json_content(content))
    document_type = DocumentType(payload.get("document_type") or "unknown")
    fields = [_field_from_gemma(item) for item in payload.get("fields", [])]
    findings = [
        ValidationFinding(
            severity=str(item.get("severity") or "warning"),
            code=str(item.get("code") or "gemma_finding"),
            message=str(item.get("message") or ""),
            field_key=item.get("field_key"),
        )
        for item in payload.get("findings", [])
    ]
    return GemmaExtractionResult(
        document_type=document_type,
        summary=str(payload.get("summary") or ""),
        fields=fields,
        findings=findings,
    )


def _pages_as_text(pages: List[OcrPage]) -> str:
    chunks: List[str] = []
    for page in pages:
        chunks.append(f"PAGE {page.page_number} ({page.width}x{page.height})")
        for index, block in enumerate(page.blocks, start=1):
            chunks.append(
                f"[{index}] bbox={block.bbox} conf={block.confidence:.2f} type={block.block_type}: {block.text}"
            )
    return "\n".join(chunks)


def build_extraction_messages(
    *,
    case_type: CaseType,
    expected_document_type: DocumentType,
    pages: List[OcrPage],
) -> List[Dict[str, Any]]:
    system = (
        "You are LipiOCR's Gemma 4 26B reasoning engine for Nepal financial KYC. "
        "Extract only evidence-backed data from OCR/page evidence. Return JSON only. "
        "Do not invent values. If a field is unclear, lower confidence and add a finding. "
        "Use Nepal financial institution context: KYC, KYB, onboarding, PAN/VAT, citizenship, "
        "National ID, account opening forms, cheque, bank statement, company registration, "
        "board resolution, tax clearance, nominee, signature, photo, and branch documents. "
        "JSON schema: {document_type, summary, fields:[{key,label,value,confidence,required,source_page,evidence_text,bbox}], "
        "findings:[{severity,code,message,field_key}]}."
    )
    user = (
        f"Case type: {case_type.value}\n"
        f"Expected document type: {expected_document_type.value}\n\n"
        f"OCR evidence:\n{_pages_as_text(pages)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": [{"type": "text", "text": user}]},
    ]


class GemmaReasoningClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def health(self) -> Dict[str, object]:
        return {
            "provider": "vllm-openai-compatible",
            "model": self.settings.gemma_model,
            "api_base": self.settings.gemma_api_base,
            "enabled": self.settings.gemma_enabled,
            "strict_json": self.settings.gemma_require_json,
            "retries": self.settings.gemma_retries,
        }

    async def extract(
        self,
        *,
        case_type: CaseType,
        expected_document_type: DocumentType,
        pages: List[OcrPage],
    ) -> Optional[GemmaExtractionResult]:
        if not self.settings.gemma_enabled:
            return None

        payload: Dict[str, Any] = {
            "model": self.settings.gemma_model,
            "messages": build_extraction_messages(
                case_type=case_type,
                expected_document_type=expected_document_type,
                pages=pages,
            ),
            "temperature": 0,
            "max_tokens": self.settings.gemma_max_tokens,
        }
        if self.settings.gemma_require_json:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for _attempt in range(max(1, self.settings.gemma_retries + 1)):
            try:
                async with httpx.AsyncClient(timeout=self.settings.gemma_timeout_seconds) as client:
                    response = await client.post(
                        f"{self.settings.gemma_api_base.rstrip('/')}/chat/completions",
                        json=payload,
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    return parse_gemma_extraction(content)
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        return None
