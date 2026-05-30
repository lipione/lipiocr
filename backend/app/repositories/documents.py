from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    DocumentPageRecord,
    DocumentRecordRow,
    DocumentVersionRecord,
    ExtractedFieldRecord,
    FieldCorrectionRecord,
    OcrBlockRecord,
    ReviewRecord,
)
from app.db.session import session_scope
from app.models import DocumentRecord, DocumentVersion
from app.repositories.cases import (
    _block_record_id,
    _correction_payload,
    _field_record_id,
    _model_json,
    _page_record_id,
    _value,
    document_record_from_row,
    SqlCaseRepository,
)


class SqlDocumentRepository:
    def __init__(self, engine: Engine, tenant_id: str = "demo-institution") -> None:
        self.engine = engine
        self.tenant_id = tenant_id
        self._case_repository = SqlCaseRepository(engine)

    def add(self, document: DocumentRecord) -> DocumentRecord:
        return self.save(document, update_timestamp=False)

    def save(self, document: DocumentRecord, update_timestamp: bool = True) -> DocumentRecord:
        if update_timestamp:
            document.updated_at = datetime.utcnow()
        with session_scope(self.engine) as session:
            self._delete_replaceable_document_rows(session, document.id)
            session.merge(
                DocumentRecordRow(
                    id=document.id,
                    tenant_id=self.tenant_id,
                    case_id=None,
                    filename=document.filename,
                    declared_document_type=_value(document.declared_document_type),
                    document_type=_value(document.document_type),
                    status=_value(document.status),
                    overall_confidence=document.overall_confidence,
                    summary=document.summary,
                    validation_findings=[_model_json(finding) for finding in document.validation_findings],
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )
            )
            self._insert_pages(session, document)
            self._insert_fields(session, document)
            self._insert_versions(session, document)
            self._insert_review(session, document)
            self._case_repository._append_new_audit_events(
                session,
                self.tenant_id,
                "document",
                document.id,
                document.audit_events,
            )
        return document

    def list(self) -> list[DocumentRecord]:
        with session_scope(self.engine) as session:
            rows = list(
                session.execute(
                    select(DocumentRecordRow)
                    .where(DocumentRecordRow.case_id.is_(None))
                    .order_by(DocumentRecordRow.created_at.desc())
                ).scalars()
            )
            return [document_record_from_row(session, row) for row in rows]

    def get(self, document_id: str) -> DocumentRecord:
        with session_scope(self.engine) as session:
            row = session.execute(
                select(DocumentRecordRow)
                .where(DocumentRecordRow.id == document_id)
                .where(DocumentRecordRow.case_id.is_(None))
            ).scalars().first()
            if row is None:
                raise HTTPException(status_code=404, detail="Document not found")
            return document_record_from_row(session, row)

    def _delete_replaceable_document_rows(self, session: Session, document_id: str) -> None:
        session.execute(delete(OcrBlockRecord).where(OcrBlockRecord.document_id == document_id))
        session.execute(delete(DocumentPageRecord).where(DocumentPageRecord.document_id == document_id))
        session.execute(
            delete(FieldCorrectionRecord)
            .where(FieldCorrectionRecord.document_id == document_id)
            .where(FieldCorrectionRecord.case_id.is_(None))
        )
        session.execute(
            delete(ExtractedFieldRecord)
            .where(ExtractedFieldRecord.document_id == document_id)
            .where(ExtractedFieldRecord.case_id.is_(None))
        )
        session.execute(
            delete(ReviewRecord)
            .where(ReviewRecord.document_id == document_id)
            .where(ReviewRecord.case_id.is_(None))
        )
        session.execute(delete(DocumentVersionRecord).where(DocumentVersionRecord.document_id == document_id))

    def _insert_pages(self, session: Session, document: DocumentRecord) -> None:
        for page in document.pages:
            session.add(
                DocumentPageRecord(
                    id=_page_record_id(document.id, page.page_number),
                    tenant_id=self.tenant_id,
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
                        tenant_id=self.tenant_id,
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

    def _insert_fields(self, session: Session, document: DocumentRecord) -> None:
        for index, field in enumerate(document.fields):
            document_id = field.document_id or field.evidence.document_id or document.id
            field_id = _field_record_id(None, document_id, index, field.key)
            session.add(
                ExtractedFieldRecord(
                    id=field_id,
                    tenant_id=self.tenant_id,
                    case_id=None,
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
                        tenant_id=self.tenant_id,
                        case_id=None,
                        document_id=document_id,
                        field_key=field.key,
                        original_value=field.original_ocr_value or "",
                        corrected_value=field.corrected_value or field.value,
                        actor="system",
                        reason=field.audit_reason or "",
                        created_at=datetime.utcnow(),
                    )
                )

    def _insert_versions(self, session: Session, document: DocumentRecord) -> None:
        for version in document.version_history:
            self._insert_version(session, document.id, version)

    def _insert_version(self, session: Session, document_id: str, version: DocumentVersion) -> None:
        session.add(
            DocumentVersionRecord(
                id=f"{document_id}:version:{version.version}",
                tenant_id=self.tenant_id,
                document_id=document_id,
                version=version.version,
                action=version.action,
                filename=version.filename,
                document_type=_value(version.document_type),
                status=_value(version.status),
                overall_confidence=version.overall_confidence,
                fields_count=version.fields_count,
                summary=version.summary,
                actor=version.actor,
                note=version.note,
                created_at=version.created_at,
            )
        )

    def _insert_review(self, session: Session, document: DocumentRecord) -> None:
        review = document.review
        if review.reviewer is None and review.note is None and review.reviewed_at is None:
            return
        session.add(
            ReviewRecord(
                id=f"{document.id}:review",
                tenant_id=self.tenant_id,
                case_id=None,
                document_id=document.id,
                reviewer=review.reviewer,
                decision=None,
                note=review.note,
                reviewed_at=review.reviewed_at,
            )
        )


__all__ = ["SqlDocumentRepository"]
