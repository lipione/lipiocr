from datetime import datetime
from typing import Dict, Optional

from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.app_context import (
    UPLOAD_DIR,
    gemma_client as _gemma_client,
    object_storage,
    ocr_provider,
    repository,
    settings,
)
from app.jobs.models import JobStatus, JobType
from app.jobs.queue import job_queue
from app.jobs.worker import retry_failed_job, run_next_job
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
from app.routers import health_router, integration_manifest_router
from app.services.enterprise_extraction import process_enterprise_document
from app.services.extraction import extract_fields
from app.services.security import require_permission
from app.services.templates import get_template, list_templates
from app.services.validation import compute_overall_confidence, route_by_confidence, validate_field


app = FastAPI(title="LipiOCR Enterprise API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(integration_manifest_router)


@app.get("/api/integrations/profiles")
def integration_profiles():
    from app.services.integrations import list_integration_profiles

    return list_integration_profiles()


@app.post("/api/integrations/webhook/test")
def integration_webhook_test(http_request: Request, request: Dict[str, object] = Body(default_factory=dict)):
    from app.services.integrations import build_webhook_test_payload

    require_permission(settings, http_request, "export_case")
    case_id = str(request.get("case_id", ""))
    event = str(request.get("event", "case.approved"))
    case = repository.get_case(case_id)
    return build_webhook_test_payload(case=case, event=event)


@app.get("/api/admin/tenant")
def tenant_profile():
    from app.services.enterprise_controls import build_tenant_profile

    return build_tenant_profile(settings)


@app.get("/api/admin/rbac")
def rbac_matrix():
    from app.services.enterprise_controls import build_rbac_matrix

    return build_rbac_matrix()


@app.get("/api/admin/audit-integrity")
def audit_integrity():
    from app.services.enterprise_controls import build_audit_integrity_summary

    return build_audit_integrity_summary(repository.list_cases())


@app.get("/api/review/queue")
def review_queue():
    from app.services.enterprise_controls import build_review_queue

    return build_review_queue(repository.list_cases())


@app.get("/api/platform/status")
def platform_status():
    from app.services.production_readiness import build_platform_status

    return build_platform_status(settings, repository.list_cases())


@app.get("/api/ocr/pipeline")
def ocr_pipeline():
    from app.services.production_readiness import build_ocr_pipeline_profile

    return build_ocr_pipeline_profile(settings)


@app.get("/api/dashboard/operations")
def dashboard_operations():
    from app.services.production_readiness import build_operations_dashboard

    return build_operations_dashboard(repository.list_cases())


@app.get("/api/admin/templates/studio")
def template_studio():
    from app.services.production_readiness import build_template_studio

    return build_template_studio()


@app.post("/api/admin/templates/studio", status_code=201)
def upsert_template_studio(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.models import TemplateField
    from app.services.production_readiness import build_template_studio
    from app.services.templates import upsert_template

    require_permission(settings, http_request, "manage_templates")
    document_type = DocumentType(str(payload.get("document_type") or "unknown"))
    fields = [
        TemplateField(
            key=str(field.get("key") or ""),
            label=str(field.get("label") or field.get("key") or ""),
            required=bool(field.get("required", True)),
            bbox=list(field.get("bbox") or [0, 0, 0, 0]),
        )
        for field in list(payload.get("fields") or [])
    ]
    result = upsert_template(
        document_type=document_type,
        name=str(payload.get("name") or document_type.value.replace("_", " ").title()),
        fields=fields,
        validation_rules=list(payload.get("validation_rules") or []),
    )
    result["studio"] = build_template_studio()
    return result


@app.get("/api/integrations/operations")
def integration_operations():
    from app.services.integration_operations import integration_operations as build_operations

    return build_operations()


@app.post("/api/integrations/webhooks/configure", status_code=201)
def configure_integration_webhook(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.integration_operations import configure_webhook

    require_permission(settings, http_request, "manage_integrations")
    return configure_webhook(payload)


@app.post("/api/integrations/sftp/batch", status_code=202)
def queue_integration_batch(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.integration_operations import queue_sftp_batch

    require_permission(settings, http_request, "export_case")
    return queue_sftp_batch(payload)


@app.post("/api/integrations/retry/{event_id}")
def retry_integration_event(event_id: str, http_request: Request):
    from app.services.integration_operations import retry_event

    require_permission(settings, http_request, "manage_integrations")
    return retry_event(event_id)


@app.get("/api/verification/adapters")
def verification_adapters():
    from app.services.verification_registry import list_adapters

    return list_adapters()


@app.post("/api/verification/adapters/{adapter_key}/configure")
def configure_verification_adapter(
    adapter_key: str,
    http_request: Request,
    payload: Dict[str, object] = Body(default_factory=dict),
):
    from app.services.verification_registry import configure_adapter

    require_permission(settings, http_request, "manage_integrations")
    return configure_adapter(adapter_key, payload)


@app.get("/api/analytics/accuracy")
def accuracy_analytics():
    from app.services.accuracy_analytics import build_accuracy_analytics

    return build_accuracy_analytics(repository.list_cases())


@app.post("/api/analytics/corrections", status_code=201)
def record_accuracy_correction(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.accuracy_analytics import record_correction

    require_permission(settings, http_request, "edit_fields")
    case = repository.get_case(str(payload.get("case_id") or ""))
    result = record_correction(case, payload)
    repository.save_case(case)
    return result


@app.post("/api/cases", status_code=201)
def create_case(http_request: Request, request: CaseCreateRequest):
    require_permission(settings, http_request, "create_case")
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


@app.get("/api/review/workbench/{case_id}")
def review_workbench(case_id: str):
    from app.services.reviewer_workbench import build_workbench

    return build_workbench(repository.get_case(case_id))


@app.post("/api/cases/{case_id}/assign")
def assign_case(case_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.reviewer_workbench import assign_case as assign

    require_permission(settings, http_request, "review_case")
    case = repository.get_case(case_id)
    result = assign(case, payload)
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/comments", status_code=201)
def add_case_comment(case_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.reviewer_workbench import add_comment

    require_permission(settings, http_request, "review_case")
    case = repository.get_case(case_id)
    result = add_comment(case, payload)
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/rework")
def request_case_rework(case_id: str, http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.reviewer_workbench import request_rework

    require_permission(settings, http_request, "review_case")
    case = repository.get_case(case_id)
    request_rework(case, payload)
    return repository.save_case(case)


@app.get("/api/cases/{case_id}/intelligence")
def case_intelligence(case_id: str):
    from app.services.kyc_intelligence import build_case_intelligence

    return build_case_intelligence(repository.get_case(case_id))


@app.post("/api/cases/{case_id}/split-preview")
def case_split_preview(case_id: str):
    from app.services.kyc_intelligence import build_split_preview

    return build_split_preview(repository.get_case(case_id))


@app.post("/api/cases/{case_id}/classify")
def classify_case(case_id: str, http_request: Request):
    from app.services.kyc_intelligence import classify_case_documents

    require_permission(settings, http_request, "submit_review")
    case = repository.get_case(case_id)
    result = classify_case_documents(case)
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/validate")
def validate_case(case_id: str, http_request: Request):
    from app.services.kyc_intelligence import validate_case_consistency

    require_permission(settings, http_request, "submit_review")
    case = repository.get_case(case_id)
    result = validate_case_consistency(case)
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/embedded-review-link")
def embedded_review_link(case_id: str, http_request: Request):
    from app.services.integrations import build_embedded_review_link

    require_permission(settings, http_request, "export_case")
    return build_embedded_review_link(repository.get_case(case_id), settings)


@app.get("/api/cases/{case_id}/export-profile/{profile_key}")
def export_profile(case_id: str, profile_key: str, http_request: Request):
    from app.services.integrations import build_export_profile

    require_permission(settings, http_request, "export_case")
    return build_export_profile(repository.get_case(case_id), profile_key)


@app.post("/api/cases/{case_id}/verification/run")
def verification_run(case_id: str, http_request: Request):
    from app.services.advanced_verification import run_verification

    require_permission(settings, http_request, "submit_review")
    case = repository.get_case(case_id)
    result = run_verification(case, repository.list_cases())
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/verification/{adapter_key}/run")
def verification_adapter_run(case_id: str, adapter_key: str, http_request: Request):
    from app.services.verification_registry import run_adapter

    require_permission(settings, http_request, "submit_review")
    case = repository.get_case(case_id)
    result = run_adapter(case, adapter_key)
    repository.save_case(case)
    return result


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_case_document(
    http_request: Request,
    case_id: str,
    declared_document_type: DocumentType = Form(DocumentType.unknown),
    file: UploadFile = File(...),
):
    require_permission(settings, http_request, "upload_document")
    case = repository.get_case(case_id)
    contents = await file.read()
    stored_path = UPLOAD_DIR / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{file.filename}"
    stored_path.write_bytes(contents)
    storage_metadata = object_storage.put_upload(
        case_id=case.id,
        filename=file.filename or stored_path.name,
        content=contents,
        content_type=file.content_type or "application/octet-stream",
    )

    case.status = CaseStatus.processing
    case.audit_events.append(
        AuditEvent(
            action="document_uploaded",
            actor="uploader",
            note=file.filename or stored_path.name,
            metadata={
                "stored_path": stored_path.name,
                "declared_document_type": declared_document_type.value,
                "storage": storage_metadata,
            },
        )
    )
    if settings.async_jobs_enabled:
        job = job_queue.enqueue(
            job_type=JobType.case_document_upload,
            target_type="case",
            target_id=case.id,
            payload={
                "case_id": case.id,
                "filename": file.filename or stored_path.name,
                "declared_document_type": declared_document_type.value,
                "stored_path": stored_path.name,
                "storage": storage_metadata,
            },
        )
        repository.save_case(case)
        return JSONResponse(status_code=202, content=_job_envelope(job))

    document, fields, findings = await process_enterprise_document(
        case_type=case.case_type,
        filename=file.filename or stored_path.name,
        content=contents,
        declared_document_type=declared_document_type,
        gemma_client=_gemma_client(),
        source_path=stored_path,
        ocr_provider=ocr_provider(),
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
def review_case(case_id: str, review: ReviewRequest, http_request: Request):
    permission = "approve_case" if review.decision == "approve" else "review_case"
    require_permission(settings, http_request, permission)
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
def export_case(case_id: str, http_request: Request):
    require_permission(settings, http_request, "export_case")
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


def _job_envelope(job):
    return {
        "job_id": job.id,
        "status": job.status.value,
        "status_url": f"/api/jobs/{job.id}",
    }


@app.get("/api/jobs")
def list_jobs(http_request: Request, status: Optional[JobStatus] = None):
    require_permission(settings, http_request, "view_case")
    return [job.model_dump(mode="json") for job in job_queue.list_jobs(status=status)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, http_request: Request):
    require_permission(settings, http_request, "view_case")
    return job_queue.get(job_id)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str, http_request: Request):
    require_permission(settings, http_request, "upload_document")
    return retry_failed_job(job_queue, job_id)


@app.post("/api/jobs/run-next")
def run_next_queued_job(http_request: Request):
    require_permission(settings, http_request, "admin")
    job = run_next_job(job_queue, handlers={})
    if job is None:
        return {"status": "idle"}
    return job


@app.post("/api/documents/upload", status_code=201)
async def upload_document(
    http_request: Request,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
):
    require_permission(settings, http_request, "upload_document")
    stored_path = UPLOAD_DIR / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{file.filename}"
    contents = await file.read()
    stored_path.write_bytes(contents)

    if settings.async_jobs_enabled:
        storage_metadata = object_storage.put_upload(
            case_id="standalone",
            filename=file.filename or stored_path.name,
            content=contents,
            content_type=file.content_type or "application/octet-stream",
        )
        job = job_queue.enqueue(
            job_type=JobType.document_upload,
            target_type="document",
            target_id=stored_path.stem,
            payload={
                "filename": file.filename or stored_path.name,
                "declared_document_type": document_type.value,
                "stored_path": stored_path.name,
                "storage": storage_metadata,
            },
        )
        return JSONResponse(status_code=202, content=_job_envelope(job))

    template = get_template(document_type)
    provider = ocr_provider("mock")
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
