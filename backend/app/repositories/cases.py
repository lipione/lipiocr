from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEventRecord,
    CaseRecord,
    DocumentPageRecord,
    DocumentRecordRow,
    ExtractedFieldRecord,
    FieldCorrectionRecord,
    IntegrationEventRecord,
    OcrBlockRecord,
    ReviewRecord,
)
from app.db.session import session_scope
from app.models import (
    AuditEvent,
    EvidenceRef,
    ExtractedField,
    FinancialDocument,
    IntegrationEvent,
    KycCase,
    OcrBlock,
    OcrPage,
    ReviewState,
    ValidationFinding,
)
from app.repositories.audit import _canonical_payload


def _value(value: object) -> str:
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value) if value is not None else ""


def _model_json(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if isinstance(model, dict):
        return model
    return {}


def _field_record_id(case_id: Optional[str], document_id: Optional[str], index: int, key: str) -> str:
    raw = f"{case_id or 'standalone'}:{document_id or 'case'}:{index}:{key}"
    if len(raw) <= 160:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{case_id or 'standalone'}:{document_id or 'case'}:{index}:{digest}"


def _page_record_id(document_id: str, page_number: int) -> str:
    return f"{document_id}:page:{page_number}"


def _block_record_id(document_id: str, page_number: int, sequence: int) -> str:
    return f"{document_id}:page:{page_number}:block:{sequence}"


def _document_confidence(document: FinancialDocument) -> float:
    if document.pages:
        return round(sum(page.ocr_confidence for page in document.pages) / len(document.pages), 4)
    return 0.0


def _audit_key(action: str, actor: str, note: str, created_at: datetime) -> tuple[str, str, str, str]:
    return (action, actor, note, created_at.isoformat())


def _correction_payload(field: ExtractedField) -> dict:
    return {
        "bbox": field.bbox,
        "extracted_by": field.extracted_by,
        "original_ocr_value": field.original_ocr_value,
        "corrected_value": field.corrected_value,
        "source_field_used": field.source_field_used,
        "correction_confidence": field.correction_confidence,
        "audit_reason": field.audit_reason,
    }


def _field_from_row(row: ExtractedFieldRecord) -> ExtractedField:
    correction = row.correction or {}
    return ExtractedField(
        key=row.field_key,
        label=row.label,
        value=row.value,
        confidence=row.confidence,
        required=row.required,
        source=row.source,
        validation_status=row.validation_status,
        validation_message=row.validation_message,
        bbox=correction.get("bbox"),
        evidence=EvidenceRef.model_validate(row.evidence or {}),
        extracted_by=correction.get("extracted_by") or "deterministic-fallback",
        review_status=row.review_status,
        document_id=row.document_id,
        original_ocr_value=correction.get("original_ocr_value"),
        corrected_value=correction.get("corrected_value"),
        source_field_used=correction.get("source_field_used"),
        correction_confidence=correction.get("correction_confidence"),
        audit_reason=correction.get("audit_reason"),
    )


def _audit_event_from_row(row: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        action=row.action,
        actor=row.actor,
        note=row.note,
        metadata=row.metadata_json or {},
        created_at=row.created_at,
    )


def _document_from_row(session: Session, row: DocumentRecordRow) -> FinancialDocument:
    page_rows = list(
        session.execute(
            select(DocumentPageRecord)
            .where(DocumentPageRecord.document_id == row.id)
            .order_by(DocumentPageRecord.page_number.asc())
        ).scalars()
    )
    pages: list[OcrPage] = []
    for page_row in page_rows:
        block_rows = list(
            session.execute(
                select(OcrBlockRecord)
                .where(OcrBlockRecord.document_id == row.id)
                .where(OcrBlockRecord.page_number == page_row.page_number)
                .order_by(OcrBlockRecord.sequence.asc())
            ).scalars()
        )
        pages.append(
            OcrPage(
                page_number=page_row.page_number,
                width=page_row.width,
                height=page_row.height,
                image_uri=page_row.image_uri,
                ocr_confidence=page_row.ocr_confidence,
                blocks=[
                    OcrBlock(
                        text=block.text,
                        bbox=block.bbox,
                        confidence=block.confidence,
                        block_type=block.block_type,
                        language=block.language,
                    )
                    for block in block_rows
                ],
            )
        )
    return FinancialDocument(
        id=row.id,
        filename=row.filename,
        declared_document_type=row.declared_document_type,
        document_type=row.document_type,
        status=row.status,
        page_count=len(pages),
        pages=pages,
        summary=row.summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlCaseRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def add_case(self, case: KycCase) -> KycCase:
        return self.save_case(case, update_timestamp=False)

    def save_case(self, case: KycCase, update_timestamp: bool = True) -> KycCase:
        if update_timestamp:
            case.updated_at = datetime.utcnow()
        tenant_id = case.institution_id or "demo-institution"
        with session_scope(self.engine) as session:
            self._delete_replaceable_case_rows(session, case.id)
            session.merge(
                CaseRecord(
                    id=case.id,
                    tenant_id=tenant_id,
                    case_type=_value(case.case_type),
                    applicant_name=case.applicant_name,
                    institution_id=case.institution_id,
                    branch_code=case.branch_code,
                    integration_ref=case.integration_ref,
                    status=_value(case.status),
                    risk_level=_value(case.risk_level),
                    validation_findings=[_model_json(finding) for finding in case.validation_findings],
                    created_at=case.created_at,
                    updated_at=case.updated_at,
                )
            )
            self._insert_documents(session, tenant_id, case.id, case.documents)
            self._insert_fields(session, tenant_id, case.id, case.extracted_fields)
            self._insert_review(session, tenant_id, case.id, case.review)
            self._insert_integration_events(session, tenant_id, case.id, case.integration_events)
            self._append_new_audit_events(session, tenant_id, "case", case.id, case.audit_events)
        return case

    def list_cases(self) -> list[KycCase]:
        with session_scope(self.engine) as session:
            rows = list(session.execute(select(CaseRecord).order_by(CaseRecord.created_at.desc())).scalars())
            return [self._case_from_row(session, row) for row in rows]

    def get_case(self, case_id: str) -> KycCase:
        with session_scope(self.engine) as session:
            row = session.execute(select(CaseRecord).where(CaseRecord.id == case_id)).scalars().first()
            if row is None:
                raise HTTPException(status_code=404, detail="Case not found")
            return self._case_from_row(session, row)

    def _delete_replaceable_case_rows(self, session: Session, case_id: str) -> None:
        existing_document_ids = list(
            session.execute(select(DocumentRecordRow.id).where(DocumentRecordRow.case_id == case_id)).scalars()
        )
        if existing_document_ids:
            session.execute(delete(OcrBlockRecord).where(OcrBlockRecord.document_id.in_(existing_document_ids)))
            session.execute(delete(DocumentPageRecord).where(DocumentPageRecord.document_id.in_(existing_document_ids)))
        session.execute(delete(FieldCorrectionRecord).where(FieldCorrectionRecord.case_id == case_id))
        session.execute(delete(ExtractedFieldRecord).where(ExtractedFieldRecord.case_id == case_id))
        session.execute(delete(ReviewRecord).where(ReviewRecord.case_id == case_id))
        session.execute(delete(IntegrationEventRecord).where(IntegrationEventRecord.case_id == case_id))
        session.execute(delete(DocumentRecordRow).where(DocumentRecordRow.case_id == case_id))

    def _insert_documents(
        self,
        session: Session,
        tenant_id: str,
        case_id: str,
        documents: Iterable[FinancialDocument],
    ) -> None:
        for document in documents:
            pages = list(document.pages)
            session.add(
                DocumentRecordRow(
                    id=document.id,
                    tenant_id=tenant_id,
                    case_id=case_id,
                    filename=document.filename,
                    declared_document_type=_value(document.declared_document_type),
                    document_type=_value(document.document_type),
                    status=_value(document.status),
                    overall_confidence=_document_confidence(document),
                    summary=document.summary,
                    validation_findings=[],
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )
            )
            for page in pages:
                session.add(
                    DocumentPageRecord(
                        id=_page_record_id(document.id, page.page_number),
                        tenant_id=tenant_id,
                        document_id=document.id,
                        page_number=page.page_number,
                        width=page.width,
                        height=page.height,
                        image_uri=page.image_uri,
                        ocr_confidence=page.ocr_confidence,
                    )
                )
                for sequence, block in enumerate(page.blocks):
                    session.add(
                        OcrBlockRecord(
                            id=_block_record_id(document.id, page.page_number, sequence),
                            tenant_id=tenant_id,
                            document_id=document.id,
                            page_number=page.page_number,
                            sequence=sequence,
                            text=block.text,
                            bbox=block.bbox,
                            confidence=block.confidence,
                            block_type=block.block_type,
                            language=block.language,
                        )
                    )

    def _insert_fields(
        self,
        session: Session,
        tenant_id: str,
        case_id: str,
        fields: Iterable[ExtractedField],
    ) -> None:
        for index, field in enumerate(fields):
            document_id = field.document_id or field.evidence.document_id
            field_id = _field_record_id(case_id, document_id, index, field.key)
            session.add(
                ExtractedFieldRecord(
                    id=field_id,
                    tenant_id=tenant_id,
                    case_id=case_id,
                    document_id=document_id,
                    field_key=field.key,
                    label=field.label,
                    value=field.value,
                    confidence=field.confidence,
                    required=field.required,
                    source=field.source,
                    validation_status=_value(field.validation_status),
                    validation_message=field.validation_message,
                    review_status=_value(field.review_status),
                    evidence=_model_json(field.evidence),
                    correction=_correction_payload(field),
                )
            )
            if field.original_ocr_value is not None or field.corrected_value is not None:
                session.add(
                    FieldCorrectionRecord(
                        id=f"{field_id}:correction",
                        tenant_id=tenant_id,
                        case_id=case_id,
                        document_id=document_id,
                        field_key=field.key,
                        original_value=field.original_ocr_value or "",
                        corrected_value=field.corrected_value or field.value,
                        actor="system",
                        reason=field.audit_reason or "",
                        created_at=datetime.utcnow(),
                    )
                )

    def _insert_review(self, session: Session, tenant_id: str, case_id: str, review: ReviewState) -> None:
        if review.reviewer is None and review.note is None and review.reviewed_at is None:
            return
        session.add(
            ReviewRecord(
                id=f"{case_id}:review",
                tenant_id=tenant_id,
                case_id=case_id,
                document_id=None,
                reviewer=review.reviewer,
                decision=None,
                note=review.note,
                reviewed_at=review.reviewed_at,
            )
        )

    def _insert_integration_events(
        self,
        session: Session,
        tenant_id: str,
        case_id: str,
        events: Iterable[IntegrationEvent],
    ) -> None:
        for index, event in enumerate(events):
            session.add(
                IntegrationEventRecord(
                    id=f"{case_id}:integration:{index}",
                    tenant_id=tenant_id,
                    case_id=case_id,
                    mode=event.mode,
                    status=event.status,
                    target=event.target,
                    payload={},
                    created_at=event.created_at,
                )
            )

    def _append_new_audit_events(
        self,
        session: Session,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        events: Iterable[AuditEvent],
    ) -> None:
        existing_rows = list(
            session.execute(
                select(AuditEventRecord)
                .where(AuditEventRecord.tenant_id == tenant_id)
                .where(AuditEventRecord.entity_type == entity_type)
                .where(AuditEventRecord.entity_id == entity_id)
                .order_by(AuditEventRecord.created_at.asc())
            ).scalars()
        )
        existing_keys = {_audit_key(row.action, row.actor, row.note, row.created_at) for row in existing_rows}
        previous_hash = existing_rows[-1].record_hash if existing_rows else ""
        for event in events:
            key = _audit_key(event.action, event.actor, event.note, event.created_at)
            if key in existing_keys:
                continue
            payload = _canonical_payload(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=event.action,
                actor=event.actor,
                note=event.note,
                metadata=event.metadata,
                previous_hash=previous_hash,
                created_at=event.created_at,
            )
            record_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            session.add(
                AuditEventRecord(
                    id=f"audit_{uuid4().hex}",
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action=event.action,
                    actor=event.actor,
                    note=event.note,
                    metadata_json=event.metadata,
                    previous_hash=previous_hash,
                    record_hash=record_hash,
                    created_at=event.created_at,
                )
            )
            previous_hash = record_hash

    def _case_from_row(self, session: Session, row: CaseRecord) -> KycCase:
        documents = [
            _document_from_row(session, document_row)
            for document_row in session.execute(
                select(DocumentRecordRow)
                .where(DocumentRecordRow.case_id == row.id)
                .order_by(DocumentRecordRow.created_at.asc())
            ).scalars()
        ]
        fields = [
            _field_from_row(field_row)
            for field_row in session.execute(
                select(ExtractedFieldRecord)
                .where(ExtractedFieldRecord.case_id == row.id)
                .order_by(ExtractedFieldRecord.id.asc())
            ).scalars()
        ]
        review_row = session.execute(
            select(ReviewRecord)
            .where(ReviewRecord.case_id == row.id)
            .where(ReviewRecord.document_id.is_(None))
        ).scalars().first()
        audit_events = [
            _audit_event_from_row(audit_row)
            for audit_row in session.execute(
                select(AuditEventRecord)
                .where(AuditEventRecord.tenant_id == row.tenant_id)
                .where(AuditEventRecord.entity_type == "case")
                .where(AuditEventRecord.entity_id == row.id)
                .order_by(AuditEventRecord.created_at.asc())
            ).scalars()
        ]
        integration_events = [
            IntegrationEvent(
                mode=event.mode,
                status=event.status,
                target=event.target,
                created_at=event.created_at,
            )
            for event in session.execute(
                select(IntegrationEventRecord)
                .where(IntegrationEventRecord.case_id == row.id)
                .order_by(IntegrationEventRecord.created_at.asc())
            ).scalars()
        ]
        return KycCase(
            id=row.id,
            case_type=row.case_type,
            applicant_name=row.applicant_name,
            institution_id=row.institution_id,
            branch_code=row.branch_code,
            integration_ref=row.integration_ref,
            status=row.status,
            risk_level=row.risk_level,
            documents=documents,
            extracted_fields=fields,
            validation_findings=[
                ValidationFinding.model_validate(finding) for finding in (row.validation_findings or [])
            ],
            review=ReviewState(
                reviewer=review_row.reviewer if review_row else None,
                note=review_row.note if review_row else None,
                reviewed_at=review_row.reviewed_at if review_row else None,
            ),
            audit_events=audit_events,
            integration_events=integration_events,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


__all__ = ["SqlCaseRepository"]
