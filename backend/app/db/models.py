"""SQLAlchemy declarations for LipiOCR production persistence."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


TENANT_SCOPED_TABLES = {
    "cases",
    "documents",
    "document_versions",
    "document_pages",
    "ocr_blocks",
    "extracted_fields",
    "field_corrections",
    "reviews",
    "exports",
    "jobs",
    "audit_events",
    "template_profiles",
    "template_versions",
    "integration_events",
}


class TenantRecord(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TenantScopedMixin:
    tenant_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False, default="demo-institution")


class CaseRecord(TenantScopedMixin, Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_type: Mapped[str] = mapped_column(String(80), nullable=False)
    applicant_name: Mapped[str] = mapped_column(String(240), nullable=False)
    institution_id: Mapped[str] = mapped_column(String(120), nullable=False)
    branch_code: Mapped[Optional[str]] = mapped_column(String(80))
    integration_ref: Mapped[Optional[str]] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    validation_findings: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentRecordRow(TenantScopedMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    declared_document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    validation_findings: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentVersionRecord(TenantScopedMixin, Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(80), ForeignKey("documents.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    fields_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentPageRecord(TenantScopedMixin, Base):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(80), ForeignKey("documents.id"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_uri: Mapped[Optional[str]] = mapped_column(Text)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class OcrBlockRecord(TenantScopedMixin, Base):
    __tablename__ = "ocr_blocks"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(80), ForeignKey("documents.id"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    block_type: Mapped[str] = mapped_column(String(60), nullable=False)
    language: Mapped[str] = mapped_column(String(40), nullable=False)


class ExtractedFieldRecord(TenantScopedMixin, Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(80), nullable=False)
    validation_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correction: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class FieldCorrectionRecord(TenantScopedMixin, Base):
    __tablename__ = "field_corrections"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    original_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrected_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReviewRecord(TenantScopedMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    reviewer: Mapped[Optional[str]] = mapped_column(String(160))
    decision: Mapped[Optional[str]] = mapped_column(String(80))
    note: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ExportRecord(TenantScopedMixin, Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    profile_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class JobRecord(TenantScopedMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditEventRecord(TenantScopedMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TemplateProfileRecord(TenantScopedMixin, Base):
    __tablename__ = "template_profiles"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    active_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TemplateVersionRecord(TenantScopedMixin, Base):
    __tablename__ = "template_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(120), ForeignKey("template_profiles.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    pages: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    fields: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IntegrationEventRecord(TenantScopedMixin, Base):
    __tablename__ = "integration_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[Optional[str]] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    mode: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_extracted_fields_case_key", ExtractedFieldRecord.case_id, ExtractedFieldRecord.field_key)
Index("ix_audit_events_entity_created", AuditEventRecord.entity_type, AuditEventRecord.entity_id, AuditEventRecord.created_at)


def all_domain_tables() -> Dict[str, object]:
    return dict(Base.metadata.tables)


__all__ = [
    "AuditEventRecord",
    "Base",
    "CaseRecord",
    "DocumentPageRecord",
    "DocumentRecordRow",
    "DocumentVersionRecord",
    "ExportRecord",
    "ExtractedFieldRecord",
    "FieldCorrectionRecord",
    "IntegrationEventRecord",
    "JobRecord",
    "OcrBlockRecord",
    "ReviewRecord",
    "TENANT_SCOPED_TABLES",
    "TemplateProfileRecord",
    "TemplateVersionRecord",
    "TenantRecord",
    "all_domain_tables",
]
