from datetime import datetime
import hashlib
import hmac
from pathlib import Path
import re
import time
import uuid
from typing import Dict, List, Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from app.app_context import UPLOAD_DIR, gemma_client as _gemma_client, object_storage, ocr_provider, repository, settings
from app.jobs.models import JobStatus, JobType
from app.jobs.queue import job_queue
from app.jobs.worker import retry_failed_job, run_next_job
from app.models import (
    AuditEvent,
    CaseCreateRequest,
    CaseStatus,
    CaseType,
    DocumentLinkRequest,
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    FinancialDocument,
    KycCase,
    ReviewRequest,
    TemplateDraftUpdate,
    ValidationStatus,
)
from app.routers import compliance_router, health_router, integration_manifest_router, templates_router, tenants_router
from app.services.calendar_intelligence import apply_calendar_intelligence
from app.services.enterprise_extraction import process_enterprise_document
from app.security.rbac import ROLE_PERMISSIONS, can_manage_system_templates
from app.security.sessions import SessionPrincipal, session_store_from_settings
from app.security.upload_policy import upload_policy_from_settings, validate_upload_policy
from app.services.security import require_any_permission, require_permission, resolve_principal
from app.services.templates import list_templates
from app.services.upload_pages import ExpandedUploadPage, expand_template_upload_pages
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
app.include_router(templates_router)
app.include_router(tenants_router)
app.include_router(compliance_router)


IMAGE_SUFFIXES = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def _is_previewable_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_SUFFIXES


def _safe_upload_name(filename: Optional[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix or ""):
        suffix = ".bin"
    return f"{uuid.uuid4().hex}{suffix}"


def _stored_upload_path(filename: Optional[str]) -> Path:
    return UPLOAD_DIR / _safe_upload_name(filename)


def _preview_secret() -> bytes:
    secret = settings.preview_token_secret or settings.api_keys or settings.app_name
    return secret.encode("utf-8")


def _preview_signature(stored_name: str, expires_at: int) -> str:
    message = f"{stored_name}:{expires_at}".encode("utf-8")
    return hmac.new(_preview_secret(), message, hashlib.sha256).hexdigest()


def _signed_upload_image_uri(stored_name: str) -> str:
    expires_at = int(time.time()) + max(60, settings.preview_token_ttl_seconds)
    signature = _preview_signature(stored_name, expires_at)
    return f"/api/uploads/{stored_name}?exp={expires_at}&sig={signature}"


def _is_valid_preview_token(stored_name: str, exp: Optional[str], sig: Optional[str]) -> bool:
    if not exp or not sig:
        return False
    try:
        expires_at = int(exp)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(_preview_signature(stored_name, expires_at), sig)


def _upload_image_uri(stored_name: str) -> str:
    return _signed_upload_image_uri(stored_name)


def _validate_upload(filename: Optional[str], content_type: Optional[str], contents: bytes) -> None:
    validate_upload_policy(filename, content_type, contents, upload_policy_from_settings(settings))


def _principal_payload(principal) -> Dict[str, Optional[str]]:
    return {
        "user_id": principal.user_id,
        "role": principal.role,
        "tenant_id": principal.tenant_id,
        "branch_code": principal.branch_code,
        "auth_method": principal.auth_method,
    }


@app.post("/api/auth/session", status_code=201)
def create_operator_session(response: Response, payload: Dict[str, object] = Body(default_factory=dict)):
    username = str(payload.get("username") or payload.get("user_id") or "operator").strip()
    role = str(payload.get("role") or "maker").strip()
    tenant_id = str(payload.get("tenant_id") or settings.default_tenant_id).strip()
    raw_branch = payload.get("branch_code")
    branch_code = str(raw_branch).strip() if raw_branch else None

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if role not in ROLE_PERMISSIONS or role == "system":
        raise HTTPException(status_code=400, detail="Unsupported operator role")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant is required")

    principal = SessionPrincipal(
        user_id=username,
        role=role,
        tenant_id=tenant_id,
        branch_code=branch_code,
        auth_method="session",
    )
    token = session_store_from_settings(settings).create(principal)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return {"principal": _principal_payload(principal)}


@app.get("/api/auth/me")
def current_operator_session(http_request: Request):
    return {"principal": _principal_payload(resolve_principal(settings, http_request))}


@app.post("/api/auth/logout")
def logout_operator_session(http_request: Request, response: Response):
    token = http_request.cookies.get(settings.session_cookie_name, "")
    auth_header = http_request.headers.get("Authorization", "")
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    session_store_from_settings(settings).revoke(token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"status": "signed_out"}


@app.get("/api/uploads/{stored_name}")
def preview_upload(stored_name: str, http_request: Request, exp: Optional[str] = None, sig: Optional[str] = None):
    if Path(stored_name).name != stored_name or stored_name.startswith("."):
        raise HTTPException(status_code=404, detail="Upload not found")
    if not _is_valid_preview_token(stored_name, exp, sig):
        require_any_permission(settings, http_request, {"view_case", "review_case", "export_case", "view_audit"})

    stored_path = UPLOAD_DIR / stored_name
    if not stored_path.exists() or not stored_path.is_file():
        raise HTTPException(status_code=404, detail="Upload not found")
    return FileResponse(stored_path)


def _attach_upload_image_uris(case: KycCase) -> KycCase:
    pending_uploads: list[str] = []
    document_sources: Dict[str, str] = {}

    for event in case.audit_events:
        stored_path = event.metadata.get("stored_path")
        if event.action == "document_uploaded" and isinstance(stored_path, str):
            pending_uploads.append(stored_path)
            continue

        document_id = event.metadata.get("document_id")
        if event.action in {"document_processed", "document_replaced"} and isinstance(document_id, str) and pending_uploads:
            document_sources[document_id] = pending_uploads.pop(0)

    for document in case.documents:
        stored_name = document_sources.get(document.id)
        if not stored_name or not _is_previewable_image(stored_name):
            continue
        image_uri = _upload_image_uri(stored_name)
        for page in document.pages:
            page.image_uri = image_uri

    return case


def _attach_document_record_image_uri(document: DocumentRecord, stored_name: Optional[str]) -> DocumentRecord:
    if not stored_name or not _is_previewable_image(stored_name):
        return document
    image_uri = _upload_image_uri(stored_name)
    for page in document.pages:
        page.image_uri = image_uri
    return document


def _stored_upload_name_from_document_record(document: DocumentRecord) -> Optional[str]:
    for event in reversed(document.audit_events):
        stored_path = event.metadata.get("stored_path")
        if event.action == "document_uploaded" and isinstance(stored_path, str):
            return stored_path
    return None


def _stored_upload_name_from_case_document(case: KycCase, document_id: str) -> Optional[str]:
    pending_uploads: list[str] = []
    document_sources: Dict[str, str] = {}

    for event in case.audit_events:
        stored_path = event.metadata.get("stored_path")
        if event.action == "document_uploaded" and isinstance(stored_path, str):
            pending_uploads.append(stored_path)
            continue

        processed_document_id = event.metadata.get("document_id")
        if event.action in {"document_processed", "document_replaced"} and isinstance(processed_document_id, str):
            if pending_uploads:
                document_sources[processed_document_id] = pending_uploads.pop(0)

    if document_id in document_sources:
        return document_sources[document_id]

    try:
        linked_document = repository.get(document_id)
    except HTTPException:
        return None
    return _stored_upload_name_from_document_record(linked_document)


def _attach_standalone_image_uri(document: DocumentRecord) -> DocumentRecord:
    _ensure_document_version_history(document)
    return _attach_document_record_image_uri(document, _stored_upload_name_from_document_record(document))


def _retarget_document_outputs(
    document_id: str,
    financial_document,
    fields,
    findings,
) -> None:
    financial_document.id = document_id
    if isinstance(getattr(financial_document, "intelligence", None), dict):
        financial_document.intelligence["document_id"] = document_id
    for field in fields:
        field.document_id = document_id
        field.evidence.document_id = document_id
    for finding in findings:
        if finding.document_id:
            finding.document_id = document_id


def _record_document_version(
    document: DocumentRecord,
    action: str,
    actor: str,
    note: str = "",
    created_at: Optional[datetime] = None,
) -> None:
    document.version_history.append(
        DocumentVersion(
            version=len(document.version_history) + 1,
            action=action,
            filename=document.filename,
            document_type=document.document_type,
            status=document.status,
            overall_confidence=document.overall_confidence,
            fields_count=len(document.fields),
            summary=document.summary,
            actor=actor,
            note=note,
            created_at=created_at or datetime.utcnow(),
        )
    )


def _ensure_document_version_history(document: DocumentRecord) -> DocumentRecord:
    if document.version_history:
        return document

    event_actions = {
        "document_uploaded": "uploaded",
        "document_reanalyzed": "reanalyzed",
        "document_replaced": "replaced",
        "document_linked_to_application": "linked_to_application",
        "document_archived": "archived",
    }
    for event in document.audit_events:
        action = event_actions.get(event.action)
        if action:
            _record_document_version(document, action, event.actor, event.note, event.created_at)
    if not document.version_history:
        _record_document_version(document, "uploaded", "system", "Imported existing document record.", document.created_at)
    return document


def _financial_document_from_record(document: DocumentRecord) -> FinancialDocument:
    return FinancialDocument(
        id=document.id,
        filename=document.filename,
        declared_document_type=document.declared_document_type,
        document_type=document.document_type,
        status=document.status,
        page_count=len(document.pages),
        pages=[page.model_copy(deep=True) for page in document.pages],
        summary=document.summary,
        document_variant=document.document_variant,
        assets=[asset.model_copy(deep=True) for asset in document.assets],
        document_sections=[section.model_copy(deep=True) for section in document.document_sections],
        evidence_ledger=[entry.model_copy(deep=True) for entry in document.evidence_ledger],
        intelligence=dict(document.intelligence),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def _analyze_standalone_upload(
    *,
    filename: str,
    contents: bytes,
    declared_document_type: DocumentType,
    stored_path: Path,
    tenant_id: str,
    existing_document_id: Optional[str] = None,
):
    financial_document, fields, findings = await process_enterprise_document(
        case_type=CaseType.document_digitization,
        filename=filename,
        content=contents,
        declared_document_type=declared_document_type,
        gemma_client=_gemma_client(),
        source_path=stored_path,
        ocr_provider=ocr_provider(),
        tenant_id=tenant_id,
    )
    if existing_document_id:
        _retarget_document_outputs(existing_document_id, financial_document, fields, findings)
    if _is_previewable_image(stored_path.name):
        for page in financial_document.pages:
            page.image_uri = _upload_image_uri(stored_path.name)

    overall_confidence = compute_overall_confidence([field.model_dump() for field in fields])
    if overall_confidence == 0.0 and fields:
        overall_confidence = round(sum(field.confidence for field in fields) / len(fields), 2)
    status = DocumentStatus(route_by_confidence(overall_confidence))
    return financial_document, fields, findings, overall_confidence, status


async def _analyze_case_upload(
    *,
    case: KycCase,
    filename: str,
    contents: bytes,
    declared_document_type: DocumentType,
    stored_path: Path,
    existing_document_id: Optional[str] = None,
):
    financial_document, fields, findings = await process_enterprise_document(
        case_type=case.case_type,
        filename=filename,
        content=contents,
        declared_document_type=declared_document_type,
        gemma_client=_gemma_client(),
        source_path=stored_path,
        ocr_provider=ocr_provider(),
        tenant_id=case.institution_id,
    )
    if existing_document_id:
        _retarget_document_outputs(existing_document_id, financial_document, fields, findings)
    if _is_previewable_image(stored_path.name):
        for page in financial_document.pages:
            page.image_uri = _upload_image_uri(stored_path.name)
    overall_confidence = compute_overall_confidence([field.model_dump() for field in fields])
    if overall_confidence == 0.0 and fields:
        overall_confidence = round(sum(field.confidence for field in fields) / len(fields), 2)
    financial_document.status = DocumentStatus(route_by_confidence(overall_confidence))
    financial_document.page_count = len(financial_document.pages)
    financial_document.updated_at = datetime.utcnow()
    return financial_document, fields, findings


def _replace_case_document_outputs(
    case: KycCase,
    document_id: str,
    financial_document: FinancialDocument,
    fields,
    findings,
) -> None:
    if not any(document.id == document_id for document in case.documents):
        raise HTTPException(status_code=404, detail="Document not found in case")

    case.documents = [financial_document if document.id == document_id else document for document in case.documents]
    case.extracted_fields = [
        field
        for field in case.extracted_fields
        if (field.document_id or field.evidence.document_id) != document_id
    ]
    case.extracted_fields.extend(fields)
    case.validation_findings = [finding for finding in case.validation_findings if finding.document_id != document_id]
    case.validation_findings.extend(findings)
    case.status = CaseStatus.review_required
    case.review = case.review.model_copy(update={"reviewer": None, "note": None, "reviewed_at": None})


@app.get("/api/integrations/profiles")
def integration_profiles(http_request: Request):
    from app.services.integrations import list_integration_profiles

    require_permission(settings, http_request, "export_case")
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
def tenant_profile(http_request: Request):
    from app.services.enterprise_controls import build_tenant_profile

    require_permission(settings, http_request, "view_audit")
    return build_tenant_profile(settings)


@app.get("/api/admin/rbac")
def rbac_matrix(http_request: Request):
    from app.services.enterprise_controls import build_rbac_matrix

    require_permission(settings, http_request, "view_audit")
    return build_rbac_matrix()


@app.get("/api/admin/audit-integrity")
def audit_integrity(http_request: Request):
    from app.services.enterprise_controls import build_audit_integrity_summary

    require_permission(settings, http_request, "view_audit")
    return build_audit_integrity_summary(repository.list_cases())


@app.get("/api/review/queue")
def review_queue(http_request: Request):
    from app.services.enterprise_controls import build_review_queue

    require_any_permission(settings, http_request, {"view_case", "review_case"})
    return build_review_queue(repository.list_cases())


@app.get("/api/platform/status")
def platform_status(http_request: Request):
    from app.services.production_readiness import build_platform_status

    require_permission(settings, http_request, "view_audit")
    return build_platform_status(settings, repository.list_cases())


@app.get("/api/ocr/pipeline")
def ocr_pipeline(http_request: Request):
    from app.services.production_readiness import build_ocr_pipeline_profile

    require_permission(settings, http_request, "view_audit")
    return build_ocr_pipeline_profile(settings)


@app.get("/api/dashboard/operations")
def dashboard_operations(http_request: Request):
    from app.services.production_readiness import build_operations_dashboard

    require_any_permission(settings, http_request, {"view_case", "review_case", "view_audit"})
    return build_operations_dashboard(repository.list_cases())


@app.get("/api/admin/templates/studio")
def template_studio(http_request: Request):
    from app.services.production_readiness import build_template_studio

    require_permission(settings, http_request, "view_audit")
    return build_template_studio()


@app.post("/api/admin/templates/studio", status_code=201)
def upsert_template_studio(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.models import TemplateField
    from app.services.production_readiness import build_template_studio
    from app.services.templates import upsert_template

    principal = require_permission(settings, http_request, "manage_templates")
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
        allow_system_override=can_manage_system_templates(principal),
    )
    result["studio"] = build_template_studio()
    return result


@app.post("/api/admin/templates/drafts", status_code=201)
async def create_template_draft_upload(
    http_request: Request,
    name: str = Form("Untitled Template"),
    document_type: str = Form("unknown"),
    files: List[UploadFile] = File(...),
):
    from app.services.template_profiles import build_template_pages, create_template_draft

    principal = require_permission(settings, http_request, "manage_templates")
    declared_type = DocumentType(document_type)
    template_pages = []
    extracted_fields = []
    page_offset = 0

    for file in files:
        contents = await file.read()
        _validate_upload(file.filename, file.content_type, contents)
        stored_path = _stored_upload_path(file.filename)
        stored_path.write_bytes(contents)
        object_storage.put_upload(
            case_id="template-studio",
            filename=file.filename or stored_path.name,
            content=contents,
            content_type=file.content_type or "application/octet-stream",
        )

        for upload_page in expand_template_upload_pages(
            stored_path,
            original_filename=file.filename or stored_path.name,
            content_type=file.content_type,
        ):
            if upload_page.stored_path != stored_path:
                object_storage.put_upload(
                    case_id="template-studio",
                    filename=upload_page.stored_path.name,
                    content=upload_page.content,
                    content_type=upload_page.content_type,
                )

            financial_document, fields, findings = await process_enterprise_document(
                case_type=CaseType.document_digitization,
                filename=upload_page.filename,
                content=upload_page.content,
                declared_document_type=declared_type,
                gemma_client=_gemma_client(),
                source_path=upload_page.stored_path,
                ocr_provider=ocr_provider(),
                tenant_id=principal.tenant_id,
            )
            del findings
            if _is_previewable_image(upload_page.stored_path.name):
                for page in financial_document.pages:
                    page.image_uri = _upload_image_uri(upload_page.stored_path.name)

            for page in financial_document.pages:
                page.page_number += page_offset
            for field in fields:
                field.evidence.source_page += page_offset

            template_pages.extend(
                build_template_pages(
                    financial_document.pages,
                    filename=upload_page.filename,
                    stored_name=upload_page.stored_path.name,
                    start_at=page_offset + 1,
                )
            )
            extracted_fields.extend(fields)
            page_offset += max(1, len(financial_document.pages))

    draft = create_template_draft(
        name=name,
        document_type=declared_type,
        pages=template_pages,
        extracted_fields=extracted_fields,
    )
    return {"draft": draft}


@app.patch("/api/admin/templates/drafts/{draft_id}")
def update_template_draft_endpoint(draft_id: str, update: TemplateDraftUpdate, http_request: Request):
    from app.services.template_profiles import update_template_draft

    require_permission(settings, http_request, "manage_templates")
    return {"draft": update_template_draft(draft_id, update)}


@app.post("/api/admin/templates/drafts/{draft_id}/publish", status_code=201)
def publish_template_draft_endpoint(draft_id: str, http_request: Request):
    from app.services.production_readiness import build_template_studio
    from app.services.template_profiles import publish_template_draft

    principal = require_permission(settings, http_request, "manage_templates")
    profile, template_result = publish_template_draft(
        draft_id,
        tenant_id=principal.tenant_id,
        actor=principal.user_id,
        allow_system_override=can_manage_system_templates(principal),
    )
    return {
        "profile": profile,
        "template": template_result["template"],
        "validation_rules": template_result["validation_rules"],
        "studio": build_template_studio(),
    }


@app.get("/api/integrations/operations")
def integration_operations(http_request: Request):
    from app.services.integration_operations import integration_operations as build_operations

    require_permission(settings, http_request, "view_audit")
    return build_operations()


@app.post("/api/integrations/webhooks/configure", status_code=201)
def configure_integration_webhook(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.integration_operations import configure_webhook

    require_permission(settings, http_request, "manage_integrations")
    return configure_webhook(payload)


@app.post("/api/integrations/webhooks/deliver", status_code=202)
def queue_integration_webhook(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.integration_operations import queue_webhook_delivery

    require_permission(settings, http_request, "export_case")
    return queue_webhook_delivery(payload)


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
def verification_adapters(http_request: Request):
    from app.services.verification_registry import list_adapters

    require_permission(settings, http_request, "view_audit")
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
def accuracy_analytics(http_request: Request):
    from app.services.accuracy_analytics import build_accuracy_analytics

    require_permission(settings, http_request, "view_audit")
    return build_accuracy_analytics(repository.list_cases())


@app.get("/api/analytics/benchmark")
def accuracy_benchmark(http_request: Request):
    from app.accuracy.dataset import load_active_benchmark_dataset
    from app.accuracy.report import build_benchmark_report

    require_permission(settings, http_request, "view_audit")
    return build_benchmark_report(load_active_benchmark_dataset(settings))


@app.get("/api/reference/nepal-locations")
def nepal_locations_reference(http_request: Request, q: str = "", limit: int = 50):
    from app.services.nepal_locations import location_registry

    require_permission(settings, http_request, "view_case")
    registry = location_registry()
    return {
        "summary": registry.summary(),
        "query": q,
        "results": registry.search(q, limit=limit),
    }


@app.post("/api/reference/nepal-locations/resolve")
def resolve_nepal_location_reference(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.nepal_locations import resolve_nepal_location

    require_permission(settings, http_request, "view_case")
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    return resolve_nepal_location(text).model_dump()


def _address_evidence_record_payload(payload: Dict[str, object], *, tenant_id: str, record_id: str = "") -> Dict[str, object]:
    from app.services.address_evidence_store import normalize_address_text

    record_payload = dict(payload)
    record_payload["tenant_id"] = tenant_id
    if record_id:
        record_payload["id"] = record_id
    if not str(record_payload.get("id") or "").strip():
        slug_parts = [
            tenant_id,
            str(record_payload.get("district_name") or record_payload.get("district") or ""),
            str(record_payload.get("local_level_name") or record_payload.get("local_level") or ""),
            str(record_payload.get("ward") or ""),
            str(record_payload.get("kind") or "area_or_tole"),
            str(record_payload.get("name_en") or record_payload.get("name_np") or uuid.uuid4().hex[:12]),
        ]
        slug = re.sub(r"[^0-9a-z]+", "_", normalize_address_text(" ".join(slug_parts))).strip("_")
        record_payload["id"] = f"addr_{slug or uuid.uuid4().hex}"
    return record_payload


def _address_evidence_record_for_tenant(store, record_id: str, *, tenant_id: str):
    record = store._records.get(record_id)
    if record is None or record.disabled or not store._is_visible_to_tenant(record, tenant_id):
        raise HTTPException(status_code=404, detail="Address evidence record not found")
    return record


def _address_evidence_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = (
        400
        if detail.startswith("Unsupported address evidence")
        or detail.startswith("limit must")
        or detail.startswith("confidence_weight must")
        else 403
    )
    return HTTPException(status_code=status_code, detail=detail)


@app.get("/api/reference/address-evidence")
def address_evidence_reference(
    http_request: Request,
    q: str = "",
    district: str = "",
    local_level: str = "",
    ward: str = "",
    limit: int = 10,
):
    from app.services.address_evidence_store import load_address_evidence_store

    principal = resolve_principal(settings, http_request)
    require_permission(settings, http_request, "view_case")
    store = load_address_evidence_store()
    try:
        results = store.search(
            q,
            tenant_id=principal.tenant_id,
            district=district,
            local_level=local_level,
            ward=ward,
            limit=limit,
        )
    except ValueError as exc:
        raise _address_evidence_error(exc) from exc
    return {
        "query": q,
        "results": results,
    }


@app.post("/api/reference/address-evidence/resolve")
def resolve_address_evidence_reference(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.address_intelligence import suggest_address_corrections

    principal = resolve_principal(settings, http_request)
    require_permission(settings, http_request, "view_case")
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    target_field = str(payload.get("target_field") or "address")
    return {
        "candidates": suggest_address_corrections(
            text,
            target_field=target_field,
            tenant_id=principal.tenant_id,
        )
    }


@app.post("/api/reference/address-evidence", status_code=201)
def create_address_evidence_reference(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.address_evidence_store import AddressEvidenceRecord, load_address_evidence_store

    principal = require_permission(settings, http_request, "manage_templates")
    store = load_address_evidence_store()
    try:
        record = AddressEvidenceRecord.from_payload(
            _address_evidence_record_payload(payload, tenant_id=principal.tenant_id)
        )
        return {"record": store.upsert(record)}
    except ValueError as exc:
        raise _address_evidence_error(exc) from exc


@app.post("/api/reference/address-evidence/import")
def import_address_evidence_reference(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.services.address_evidence_store import AddressEvidenceRecord, load_address_evidence_store

    principal = require_permission(settings, http_request, "manage_templates")
    store = load_address_evidence_store()
    records = []
    for item in list(payload.get("records") or []):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="records must contain objects")
        try:
            record = AddressEvidenceRecord.from_payload(
                _address_evidence_record_payload(item, tenant_id=principal.tenant_id)
            )
            records.append(store.upsert(record))
        except ValueError as exc:
            raise _address_evidence_error(exc) from exc
    return {"records": records, "count": len(records)}


@app.patch("/api/reference/address-evidence/{record_id}")
def update_address_evidence_reference(
    record_id: str,
    http_request: Request,
    payload: Dict[str, object] = Body(default_factory=dict),
):
    from app.services.address_evidence_store import AddressEvidenceRecord, load_address_evidence_store

    principal = require_permission(settings, http_request, "manage_templates")
    store = load_address_evidence_store()
    existing = _address_evidence_record_for_tenant(store, record_id, tenant_id=principal.tenant_id)
    record_payload = existing.model_dump()
    record_payload.update(payload)
    try:
        record = AddressEvidenceRecord.from_payload(
            _address_evidence_record_payload(record_payload, tenant_id=existing.tenant_id, record_id=record_id)
        )
        return {"record": store.upsert(record)}
    except ValueError as exc:
        raise _address_evidence_error(exc) from exc


@app.delete("/api/reference/address-evidence/{record_id}")
def delete_address_evidence_reference(record_id: str, http_request: Request):
    from app.services.address_evidence_store import load_address_evidence_store

    principal = require_permission(settings, http_request, "manage_templates")
    store = load_address_evidence_store()
    _address_evidence_record_for_tenant(store, record_id, tenant_id=principal.tenant_id)
    try:
        result = store.delete(record_id, tenant_id=principal.tenant_id)
    except ValueError as exc:
        raise _address_evidence_error(exc) from exc
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Address evidence record not found")
    result["status"] = "disabled"
    return result


@app.post("/api/analytics/benchmark/samples", status_code=201)
def upsert_accuracy_benchmark_sample(http_request: Request, payload: Dict[str, object] = Body(default_factory=dict)):
    from app.accuracy.dataset import BenchmarkSample, append_benchmark_sample
    from app.accuracy.report import build_benchmark_report

    require_permission(settings, http_request, "view_audit")
    dataset = append_benchmark_sample(BenchmarkSample.model_validate(payload), settings)
    return {"sample_count": len(dataset.samples), "benchmark": build_benchmark_report(dataset)}


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
    principal = require_permission(settings, http_request, "create_case")
    institution_id = (
        request.institution_id
        if can_manage_system_templates(principal) and request.institution_id
        else principal.tenant_id
    )
    case = KycCase(
        case_type=request.case_type,
        applicant_name=request.applicant_name,
        institution_id=institution_id,
        branch_code=request.branch_code or principal.branch_code,
        integration_ref=request.customer_ref,
        audit_events=[
            AuditEvent(
                action="case_created",
                actor="api",
                note=f"Created {request.case_type.value} case",
                metadata={"customer_ref": request.customer_ref, "tenant_id": institution_id},
            )
        ],
    )
    return repository.add_case(case)


@app.get("/api/cases")
def list_cases(http_request: Request):
    require_permission(settings, http_request, "view_case")
    return [_attach_upload_image_uris(case) for case in repository.list_cases()]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, http_request: Request):
    require_permission(settings, http_request, "view_case")
    return _attach_upload_image_uris(repository.get_case(case_id))


@app.get("/api/review/workbench/{case_id}")
def review_workbench(case_id: str, http_request: Request):
    from app.services.reviewer_workbench import build_workbench

    require_any_permission(settings, http_request, {"view_case", "review_case"})
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
def case_intelligence(case_id: str, http_request: Request):
    from app.services.kyc_intelligence import build_case_intelligence

    require_permission(settings, http_request, "view_case")
    return build_case_intelligence(repository.get_case(case_id))


@app.post("/api/cases/{case_id}/split-preview")
def case_split_preview(case_id: str, http_request: Request):
    from app.services.kyc_intelligence import build_split_preview

    require_permission(settings, http_request, "view_case")
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
    _validate_upload(file.filename, file.content_type, contents)
    stored_path = _stored_upload_path(file.filename)
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
                "tenant_id": case.institution_id,
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
        tenant_id=case.institution_id,
    )
    if _is_previewable_image(stored_path.name):
        for page in document.pages:
            page.image_uri = _upload_image_uri(stored_path.name)
    case.documents.append(document)
    case.extracted_fields.extend(fields)
    case.validation_findings.extend(findings)
    case.status = CaseStatus.review_required
    case.audit_events.append(
        AuditEvent(
            action="document_processed",
            actor="LipiCore",
            note=document.summary,
            metadata={"document_id": document.id, "document_type": document.document_type.value},
        )
    )
    return repository.save_case(case)


@app.post("/api/cases/{case_id}/documents/{document_id}/reanalyze")
async def reanalyze_case_document(http_request: Request, case_id: str, document_id: str):
    require_permission(settings, http_request, "upload_document")
    case = repository.get_case(case_id)
    current_document = next((document for document in case.documents if document.id == document_id), None)
    if current_document is None:
        raise HTTPException(status_code=404, detail="Document not found in case")

    stored_name = _stored_upload_name_from_case_document(case, document_id)
    if not stored_name:
        raise HTTPException(status_code=400, detail="Original upload is not available for reanalysis")
    stored_path = UPLOAD_DIR / stored_name
    if not stored_path.exists():
        raise HTTPException(status_code=404, detail="Original upload file not found")

    financial_document, fields, findings = await _analyze_case_upload(
        case=case,
        filename=current_document.filename,
        contents=stored_path.read_bytes(),
        declared_document_type=current_document.declared_document_type,
        stored_path=stored_path,
        existing_document_id=document_id,
    )
    financial_document.filename = current_document.filename
    financial_document.created_at = current_document.created_at
    _replace_case_document_outputs(case, document_id, financial_document, fields, findings)
    case.audit_events.append(
        AuditEvent(
            action="document_reanalyzed",
            actor="LipiCore",
            note=financial_document.summary,
            metadata={"document_id": document_id, "document_type": financial_document.document_type.value},
        )
    )
    return _attach_upload_image_uris(repository.save_case(case))


@app.post("/api/cases/{case_id}/documents/{document_id}/replace")
async def replace_case_document(
    http_request: Request,
    case_id: str,
    document_id: str,
    document_type: DocumentType = Form(DocumentType.unknown),
    declared_document_type: Optional[DocumentType] = Form(None),
    file: UploadFile = File(...),
):
    require_permission(settings, http_request, "upload_document")
    case = repository.get_case(case_id)
    current_document = next((document for document in case.documents if document.id == document_id), None)
    if current_document is None:
        raise HTTPException(status_code=404, detail="Document not found in case")

    declared_type = (
        declared_document_type
        or (document_type if document_type != DocumentType.unknown else current_document.declared_document_type)
        or DocumentType.unknown
    )
    stored_path = _stored_upload_path(file.filename)
    contents = await file.read()
    _validate_upload(file.filename, file.content_type, contents)
    stored_path.write_bytes(contents)
    storage_metadata = object_storage.put_upload(
        case_id=case.id,
        filename=file.filename or stored_path.name,
        content=contents,
        content_type=file.content_type or "application/octet-stream",
    )
    case.audit_events.append(
        AuditEvent(
            action="document_uploaded",
            actor="uploader",
            note=f"Replaced with {file.filename or stored_path.name}",
            metadata={
                "stored_path": stored_path.name,
                "declared_document_type": declared_type.value,
                "storage": storage_metadata,
            },
        )
    )

    financial_document, fields, findings = await _analyze_case_upload(
        case=case,
        filename=file.filename or stored_path.name,
        contents=contents,
        declared_document_type=declared_type,
        stored_path=stored_path,
        existing_document_id=document_id,
    )
    financial_document.filename = file.filename or stored_path.name
    financial_document.created_at = current_document.created_at
    _replace_case_document_outputs(case, document_id, financial_document, fields, findings)
    case.audit_events.append(
        AuditEvent(
            action="document_replaced",
            actor="uploader",
            note=financial_document.summary,
            metadata={"document_id": document_id, "document_type": financial_document.document_type.value},
        )
    )
    return _attach_upload_image_uris(repository.save_case(case))


@app.patch("/api/cases/{case_id}/review")
def review_case(case_id: str, review: ReviewRequest, http_request: Request):
    permission = "approve_case" if review.decision == "approve" else "review_case"
    require_permission(settings, http_request, permission)
    case = repository.get_case(case_id)

    fields_by_key = {field.key: field for field in case.extracted_fields}
    reviewer_document_id = review.document_id or (case.documents[0].id if len(case.documents) == 1 else None)
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
                evidence=EvidenceRef(document_id=reviewer_document_id, evidence_text="Reviewer-entered field"),
                extracted_by="reviewer",
                document_id=reviewer_document_id,
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

    apply_calendar_intelligence(case.extracted_fields)

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
def templates(http_request: Request):
    require_permission(settings, http_request, "view_case")
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
    document_type: DocumentType = Form(DocumentType.unknown),
    declared_document_type: Optional[DocumentType] = Form(None),
    file: UploadFile = File(...),
):
    principal = require_permission(settings, http_request, "upload_document")
    declared_type = declared_document_type or document_type or DocumentType.unknown
    stored_path = _stored_upload_path(file.filename)
    contents = await file.read()
    _validate_upload(file.filename, file.content_type, contents)
    stored_path.write_bytes(contents)
    storage_metadata = object_storage.put_upload(
        case_id="standalone",
        filename=file.filename or stored_path.name,
        content=contents,
        content_type=file.content_type or "application/octet-stream",
    )
    if settings.async_jobs_enabled:
        job = job_queue.enqueue(
            job_type=JobType.document_upload,
            target_type="document",
            target_id=stored_path.stem,
            payload={
                "filename": file.filename or stored_path.name,
                "declared_document_type": declared_type.value,
                "stored_path": stored_path.name,
                "storage": storage_metadata,
                "tenant_id": principal.tenant_id,
            },
        )
        return JSONResponse(status_code=202, content=_job_envelope(job))

    financial_document, fields, findings, overall_confidence, status = await _analyze_standalone_upload(
        filename=file.filename or stored_path.name,
        declared_document_type=declared_type,
        contents=contents,
        stored_path=stored_path,
        tenant_id=principal.tenant_id,
    )

    document = DocumentRecord(
        id=financial_document.id,
        filename=file.filename or stored_path.name,
        declared_document_type=declared_type,
        document_type=financial_document.document_type,
        status=status,
        overall_confidence=overall_confidence,
        pages=financial_document.pages,
        fields=fields,
        summary=financial_document.summary,
        document_variant=financial_document.document_variant,
        assets=financial_document.assets,
        document_sections=financial_document.document_sections,
        evidence_ledger=financial_document.evidence_ledger,
        intelligence=financial_document.intelligence,
        validation_findings=findings,
        audit_events=[
            AuditEvent(
                action="document_uploaded",
                actor="uploader",
                note=f"Stored {stored_path.name}",
                metadata={
                    "stored_path": stored_path.name,
                    "declared_document_type": declared_type.value,
                    "storage": storage_metadata,
                },
            ),
            AuditEvent(
                action="document_processed",
                actor="LipiCore",
                note=financial_document.summary,
                metadata={"document_id": financial_document.id, "document_type": financial_document.document_type.value},
            ),
        ],
    )
    _record_document_version(document, "uploaded", "uploader", financial_document.summary)
    return repository.add(document)


@app.get("/api/documents")
def list_documents(http_request: Request):
    require_permission(settings, http_request, "view_case")
    return [_attach_standalone_image_uri(document) for document in repository.list()]


@app.get("/api/documents/{document_id}")
def get_document(document_id: str, http_request: Request):
    require_permission(settings, http_request, "view_case")
    return _attach_standalone_image_uri(repository.get(document_id))


@app.post("/api/documents/{document_id}/reanalyze")
async def reanalyze_document(document_id: str, http_request: Request):
    principal = require_permission(settings, http_request, "upload_document")
    document = repository.get(document_id)
    _ensure_document_version_history(document)
    stored_name = _stored_upload_name_from_document_record(document)
    if not stored_name:
        raise HTTPException(status_code=400, detail="Original upload is not available for reanalysis")
    stored_path = UPLOAD_DIR / stored_name
    if not stored_path.exists():
        raise HTTPException(status_code=404, detail="Original upload file not found")

    financial_document, fields, findings, overall_confidence, status = await _analyze_standalone_upload(
        filename=document.filename,
        contents=stored_path.read_bytes(),
        declared_document_type=document.declared_document_type,
        stored_path=stored_path,
        tenant_id=principal.tenant_id,
        existing_document_id=document.id,
    )

    document.document_type = financial_document.document_type
    document.status = status
    document.overall_confidence = overall_confidence
    document.pages = financial_document.pages
    document.fields = fields
    document.summary = financial_document.summary
    document.document_variant = financial_document.document_variant
    document.assets = financial_document.assets
    document.document_sections = financial_document.document_sections
    document.evidence_ledger = financial_document.evidence_ledger
    document.intelligence = financial_document.intelligence
    document.validation_findings = findings
    document.audit_events.append(
        AuditEvent(
            action="document_reanalyzed",
            actor="LipiCore",
            note=financial_document.summary,
            metadata={"document_id": document.id, "document_type": document.document_type.value},
        )
    )
    _record_document_version(document, "reanalyzed", "LipiCore", financial_document.summary)
    return _attach_standalone_image_uri(repository.save(document))


@app.post("/api/documents/{document_id}/replace")
async def replace_document(
    document_id: str,
    http_request: Request,
    document_type: DocumentType = Form(DocumentType.unknown),
    declared_document_type: Optional[DocumentType] = Form(None),
    file: UploadFile = File(...),
):
    principal = require_permission(settings, http_request, "upload_document")
    document = repository.get(document_id)
    _ensure_document_version_history(document)
    declared_type = declared_document_type or document_type or document.declared_document_type or DocumentType.unknown
    stored_path = _stored_upload_path(file.filename)
    contents = await file.read()
    _validate_upload(file.filename, file.content_type, contents)
    stored_path.write_bytes(contents)
    storage_metadata = object_storage.put_upload(
        case_id="standalone",
        filename=file.filename or stored_path.name,
        content=contents,
        content_type=file.content_type or "application/octet-stream",
    )

    financial_document, fields, findings, overall_confidence, status = await _analyze_standalone_upload(
        filename=file.filename or stored_path.name,
        contents=contents,
        declared_document_type=declared_type,
        stored_path=stored_path,
        tenant_id=principal.tenant_id,
        existing_document_id=document.id,
    )

    document.filename = file.filename or stored_path.name
    document.declared_document_type = declared_type
    document.document_type = financial_document.document_type
    document.status = status
    document.overall_confidence = overall_confidence
    document.pages = financial_document.pages
    document.fields = fields
    document.summary = financial_document.summary
    document.document_variant = financial_document.document_variant
    document.assets = financial_document.assets
    document.document_sections = financial_document.document_sections
    document.evidence_ledger = financial_document.evidence_ledger
    document.intelligence = financial_document.intelligence
    document.validation_findings = findings
    document.review = document.review.model_copy(update={"reviewer": None, "note": None, "reviewed_at": None})
    document.audit_events.append(
        AuditEvent(
            action="document_uploaded",
            actor="uploader",
            note=f"Replaced with {stored_path.name}",
            metadata={
                "stored_path": stored_path.name,
                "declared_document_type": declared_type.value,
                "storage": storage_metadata,
            },
        )
    )
    document.audit_events.append(
        AuditEvent(
            action="document_replaced",
            actor="uploader",
            note=financial_document.summary,
            metadata={"document_id": document.id, "document_type": document.document_type.value},
        )
    )
    _record_document_version(document, "replaced", "uploader", financial_document.summary)
    return _attach_standalone_image_uri(repository.save(document))


@app.post("/api/documents/{document_id}/archive")
def archive_document(document_id: str, http_request: Request, payload: Dict[str, str] = Body(default_factory=dict)):
    require_permission(settings, http_request, "edit_fields")
    document = repository.get(document_id)
    _ensure_document_version_history(document)
    note = payload.get("note") or "Archived from document library."
    document.status = DocumentStatus.archived
    document.audit_events.append(AuditEvent(action="document_archived", actor="operator", note=note))
    _record_document_version(document, "archived", "operator", note)
    return repository.save(document)


@app.post("/api/documents/{document_id}/link-application")
def link_document_to_application(document_id: str, request: DocumentLinkRequest, http_request: Request):
    require_permission(settings, http_request, "upload_document")
    if request.mode not in {"copy", "move"}:
        raise HTTPException(status_code=400, detail="mode must be copy or move")

    document = repository.get(document_id)
    _ensure_document_version_history(document)
    case = repository.get_case(request.case_id)
    financial_document = _financial_document_from_record(document)
    linked_fields = [field.model_copy(deep=True) for field in document.fields]
    linked_findings = [finding.model_copy(deep=True) for finding in document.validation_findings]

    case.documents = [item for item in case.documents if item.id != document.id]
    case.documents.append(financial_document)
    case.extracted_fields = [field for field in case.extracted_fields if field.document_id != document.id]
    case.extracted_fields.extend(linked_fields)
    case.validation_findings = [finding for finding in case.validation_findings if finding.document_id != document.id]
    case.validation_findings.extend(linked_findings)
    case.status = CaseStatus.review_required
    action_label = "Copied" if request.mode == "copy" else "Moved"
    case.audit_events.append(
        AuditEvent(
            action="library_document_linked",
            actor="operator",
            note=f"{action_label} {document.filename} from document library.",
            metadata={"document_id": document.id, "mode": request.mode},
        )
    )

    note = f"{action_label} to {case.applicant_name}."
    if request.mode == "move":
        document.status = DocumentStatus.archived
        note = f"Moved to {case.applicant_name}."
    document.audit_events.append(
        AuditEvent(
            action="document_linked_to_application",
            actor="operator",
            note=note,
            metadata={"case_id": case.id, "case_ref": case.integration_ref, "mode": request.mode},
        )
    )
    if request.mode == "move":
        _record_document_version(document, "moved_to_application", "operator", note)

    saved_case = repository.save_case(case)
    saved_document = repository.save(document)
    return {
        "case": _attach_upload_image_uris(saved_case),
        "document": _attach_standalone_image_uri(saved_document),
        "mode": request.mode,
    }


@app.patch("/api/documents/{document_id}/review")
def review_document(document_id: str, review: ReviewRequest, http_request: Request):
    permission = "approve_case" if review.decision == "approve" else "review_case"
    require_permission(settings, http_request, permission)
    document = repository.get(document_id)
    updates = review.field_updates

    fields_by_key = {field.key: field for field in document.fields}
    for key, value in updates.items():
        field = fields_by_key.get(key)
        if field is None:
            from app.models import EvidenceRef, ExtractedField, ReviewStatus

            validation = validate_field(key, value, document.document_type.value)
            document.fields.append(
                ExtractedField(
                    key=key,
                    label=key.replace("_", " ").title(),
                    value=value,
                    confidence=1.0,
                    required=False,
                    source="reviewer_entry",
                    validation_status=ValidationStatus(validation["status"]),
                    validation_message=validation["message"],
                    evidence=EvidenceRef(document_id=document.id, evidence_text="Reviewer-entered field"),
                    extracted_by="reviewer",
                    review_status=ReviewStatus.verified,
                    document_id=document.id,
                )
            )
            continue

        from app.models import ReviewStatus

        field.value = value
        field.confidence = 1.0
        field.source = "reviewer_verified"
        field.extracted_by = "reviewer"
        field.review_status = ReviewStatus.verified
        validation = validate_field(field.key, field.value, document.document_type.value)
        field.validation_status = ValidationStatus(validation["status"])
        field.validation_message = validation["message"]

    apply_calendar_intelligence(document.fields)
    document.overall_confidence = compute_overall_confidence([field.model_dump() for field in document.fields])
    if document.overall_confidence == 0.0 and document.fields:
        document.overall_confidence = round(sum(field.confidence for field in document.fields) / len(document.fields), 2)

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
def export_document(document_id: str, http_request: Request):
    require_permission(settings, http_request, "export_case")
    document = repository.get(document_id)
    return {
        "document_id": document.id,
        "document_type": document.document_type,
        "status": document.status,
        "overall_confidence": document.overall_confidence,
        "summary": document.summary,
        "fields": {field.key: field.value for field in document.fields},
        "confidence": {field.key: field.confidence for field in document.fields},
        "evidence": {field.key: field.evidence for field in document.fields},
        "findings": document.validation_findings,
        "pages": document.pages,
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
