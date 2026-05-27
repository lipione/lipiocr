from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models import (
    AuditEvent,
    CaseCreateRequest,
    CaseStatus,
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    KycCase,
    ReviewRequest,
    ValidationStatus,
)
from app.services.enterprise_extraction import process_enterprise_document
from app.services.extraction import extract_fields
from app.services.gemma import GemmaReasoningClient
from app.services.ocr import get_ocr_provider
from app.services.repository import repository
from app.services.templates import get_template, list_templates
from app.services.validation import compute_overall_confidence, route_by_confidence, validate_field


settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(settings.upload_dir)
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LipiOCR Enterprise API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _gemma_client() -> GemmaReasoningClient:
    return GemmaReasoningClient(settings)


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": "lipiocr-enterprise",
        "environment": settings.environment,
    }


@app.get("/api/ai/health")
def ai_health():
    return _gemma_client().health()


@app.get("/api/integrations/manifest")
def integration_manifest():
    return {
        "product": "LipiOCR Enterprise",
        "country": "Nepal",
        "modes": ["manual_export", "rest_api", "webhooks", "sftp", "embedded_review"],
        "events": [
            "case.created",
            "document.processed",
            "review.required",
            "case.approved",
            "case.rejected",
            "export.completed",
        ],
        "core_endpoints": [
            "POST /api/cases",
            "POST /api/cases/{case_id}/documents",
            "GET /api/cases/{case_id}/export",
        ],
    }


@app.post("/api/cases", status_code=201)
def create_case(request: CaseCreateRequest):
    case = KycCase(
        case_type=request.case_type,
        applicant_name=request.applicant_name,
        institution_id=request.institution_id,
        branch_code=request.branch_code,
        integration_ref=request.customer_ref,
        audit_events=[
            AuditEvent(
                action="case_created",
                actor="api",
                note=f"Created {request.case_type.value} case",
                metadata={"customer_ref": request.customer_ref},
            )
        ],
    )
    return repository.add_case(case)


@app.get("/api/cases")
def list_cases():
    return repository.list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return repository.get_case(case_id)


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_case_document(
    case_id: str,
    declared_document_type: DocumentType = Form(DocumentType.unknown),
    file: UploadFile = File(...),
):
    case = repository.get_case(case_id)
    contents = await file.read()
    stored_path = UPLOAD_DIR / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{file.filename}"
    stored_path.write_bytes(contents)

    case.status = CaseStatus.processing
    case.audit_events.append(
        AuditEvent(
            action="document_uploaded",
            actor="uploader",
            note=file.filename or stored_path.name,
            metadata={"stored_path": stored_path.name, "declared_document_type": declared_document_type.value},
        )
    )

    document, fields, findings = await process_enterprise_document(
        case_type=case.case_type,
        filename=file.filename or stored_path.name,
        content=contents,
        declared_document_type=declared_document_type,
        gemma_client=_gemma_client(),
    )
    case.documents.append(document)
    case.extracted_fields.extend(fields)
    case.validation_findings.extend(findings)
    case.status = CaseStatus.review_required
    case.audit_events.append(
        AuditEvent(
            action="document_processed",
            actor="gemma-4-26b",
            note=document.summary,
            metadata={"document_id": document.id, "document_type": document.document_type.value},
        )
    )
    return repository.save_case(case)


@app.patch("/api/cases/{case_id}/review")
def review_case(case_id: str, review: ReviewRequest):
    case = repository.get_case(case_id)

    fields_by_key = {field.key: field for field in case.extracted_fields}
    for key, value in review.field_updates.items():
        field = fields_by_key.get(key)
        if field is None:
            from app.models import ExtractedField, EvidenceRef

            new_field = ExtractedField(
                key=key,
                label=key.replace("_", " ").title(),
                value=value,
                confidence=1.0,
                source="reviewer_entry",
                validation_status=ValidationStatus.valid,
                validation_message="Entered by reviewer",
                evidence=EvidenceRef(evidence_text="Reviewer-entered field"),
                extracted_by="reviewer",
            )
            case.extracted_fields.append(new_field)
            continue
        field.value = value
        field.confidence = 1.0
        field.source = "reviewer_verified"
        field.extracted_by = "reviewer"
        validation = validate_field(field.key, field.value, "enterprise_kyc")
        field.validation_status = ValidationStatus(validation["status"])
        field.validation_message = validation["message"]

    case.review.reviewer = review.reviewer
    case.review.note = review.note
    case.review.reviewed_at = datetime.utcnow()

    if review.decision == "approve":
        case.status = CaseStatus.approved
        action = "case_approved"
    elif review.decision == "reject":
        case.status = CaseStatus.rejected
        action = "case_rejected"
    else:
        case.status = CaseStatus.review_required
        action = "review_saved"

    case.audit_events.append(AuditEvent(action=action, actor=review.reviewer, note=review.note))
    return repository.save_case(case)


@app.get("/api/cases/{case_id}/export")
def export_case(case_id: str):
    case = repository.get_case(case_id)
    case.audit_events.append(AuditEvent(action="export_generated", actor="api", note="JSON export generated"))
    repository.save_case(case)
    return {
        "case_id": case.id,
        "case_type": case.case_type,
        "integration_ref": case.integration_ref,
        "institution_id": case.institution_id,
        "branch_code": case.branch_code,
        "status": case.status,
        "risk_level": case.risk_level,
        "fields": {field.key: field.value for field in case.extracted_fields},
        "confidence": {field.key: field.confidence for field in case.extracted_fields},
        "evidence": {field.key: field.evidence for field in case.extracted_fields},
        "findings": case.validation_findings,
        "documents": case.documents,
        "review": case.review,
        "audit_events": case.audit_events,
    }


@app.get("/api/templates")
def templates():
    return list_templates()


@app.post("/api/documents/upload", status_code=201)
async def upload_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
):
    stored_path = UPLOAD_DIR / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{file.filename}"
    contents = await file.read()
    stored_path.write_bytes(contents)

    template = get_template(document_type)
    provider = get_ocr_provider("mock")
    observations = provider.read(stored_path, document_type)
    fields = extract_fields(template, observations)
    overall_confidence = compute_overall_confidence([field.model_dump() for field in fields])
    status = DocumentStatus(route_by_confidence(overall_confidence))

    document = DocumentRecord(
        filename=file.filename or stored_path.name,
        document_type=document_type,
        status=status,
        overall_confidence=overall_confidence,
        fields=fields,
        audit_events=[
            AuditEvent(action="document_uploaded", actor="uploader", note=f"Stored {stored_path.name}"),
            AuditEvent(action="ocr_completed", actor=provider.name, note=f"Template: {template.name}"),
        ],
    )
    return repository.add(document)


@app.get("/api/documents")
def list_documents():
    return repository.list()


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    return repository.get(document_id)


@app.patch("/api/documents/{document_id}/review")
def review_document(document_id: str, review: ReviewRequest):
    document = repository.get(document_id)
    updates = review.field_updates

    for field in document.fields:
        if field.key in updates:
            field.value = updates[field.key]
            field.confidence = 1.0
            validation = validate_field(field.key, field.value, document.document_type.value)
            field.validation_status = ValidationStatus(validation["status"])
            field.validation_message = validation["message"]

    document.review.reviewer = review.reviewer
    document.review.note = review.note
    document.review.reviewed_at = datetime.utcnow()

    if review.decision == "approve":
        document.status = DocumentStatus.approved
        action = "review_approved"
    elif review.decision == "reject":
        document.status = DocumentStatus.rejected
        action = "review_rejected"
    else:
        document.status = DocumentStatus.review_required
        action = "review_saved"

    document.audit_events.append(AuditEvent(action=action, actor=review.reviewer, note=review.note))
    return repository.save(document)


@app.get("/api/documents/{document_id}/export")
def export_document(document_id: str):
    document = repository.get(document_id)
    return {
        "document_id": document.id,
        "document_type": document.document_type,
        "status": document.status,
        "overall_confidence": document.overall_confidence,
        "fields": {field.key: field.value for field in document.fields},
        "confidence": {field.key: field.confidence for field in document.fields},
        "validation": {
            field.key: {
                "status": field.validation_status,
                "message": field.validation_message,
            }
            for field in document.fields
        },
        "review": document.review,
        "audit_events": document.audit_events,
    }
