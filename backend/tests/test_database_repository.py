from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.db.models import (
    AuditEventRecord,
    CaseRecord,
    DocumentPageRecord,
    DocumentRecordRow,
    DocumentVersionRecord,
    ExtractedFieldRecord,
    OcrBlockRecord,
    ReviewRecord,
)
from app.db.session import build_engine, create_schema, session_scope
from app.models import (
    AuditEvent,
    CaseType,
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    ExtractedField,
    EvidenceRef,
    FinancialDocument,
    KycCase,
    OcrBlock,
    OcrPage,
    ReviewState,
    ValidationFinding,
)
from app.repositories.cases import SqlCaseRepository
from app.repositories.documents import SqlDocumentRepository


def build_case() -> KycCase:
    document = FinancialDocument(
        id="doc_1",
        filename="citizenship.jpg",
        document_type="citizenship",
        declared_document_type="citizenship",
        page_count=1,
        pages=[
            OcrPage(
                page_number=1,
                width=1000,
                height=700,
                blocks=[OcrBlock(text="Sita Sharma", bbox=[10, 20, 200, 60], confidence=0.91, language="eng")],
                ocr_confidence=0.91,
            )
        ],
        summary="Citizenship",
    )
    return KycCase(
        id="case_1",
        case_type=CaseType.individual_kyc,
        applicant_name="Sita Sharma",
        institution_id="tenant_1",
        branch_code="KTM",
        integration_ref="CBS-1",
        documents=[document],
        extracted_fields=[
            ExtractedField(
                key="full_name",
                label="Full Name",
                value="Sita Sharma",
                confidence=0.93,
                evidence=EvidenceRef(
                    document_id="doc_1",
                    source_page=1,
                    bbox=[10, 20, 200, 60],
                    evidence_text="Sita Sharma",
                ),
                document_id="doc_1",
            )
        ],
        validation_findings=[
            ValidationFinding(
                severity="warning",
                code="manual_review",
                message="Reviewer should confirm citizenship number.",
                document_id="doc_1",
            )
        ],
        review=ReviewState(reviewer="checker.one", note="Looks consistent", reviewed_at=datetime.utcnow()),
        audit_events=[AuditEvent(action="case_created", actor="maker.one", note="Created", created_at=datetime.utcnow())],
    )


def test_sql_case_repository_writes_normalized_rows(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'cases.db'}")
    create_schema(engine)
    repository = SqlCaseRepository(engine)

    saved = repository.add_case(build_case())
    loaded = repository.get_case(saved.id)

    assert loaded.applicant_name == "Sita Sharma"
    assert loaded.documents[0].pages[0].blocks[0].text == "Sita Sharma"
    assert loaded.extracted_fields[0].evidence.document_id == "doc_1"
    assert loaded.validation_findings[0].code == "manual_review"
    assert loaded.review.reviewer == "checker.one"

    with session_scope(engine) as session:
        assert session.execute(select(CaseRecord)).scalars().one().tenant_id == "tenant_1"
        assert session.execute(select(DocumentRecordRow)).scalars().one().tenant_id == "tenant_1"
        assert session.execute(select(DocumentPageRecord)).scalars().one().case_id == "case_1"
        block = session.execute(select(OcrBlockRecord)).scalars().one()
        assert block.case_id == "case_1"
        assert block.text == "Sita Sharma"
        assert session.execute(select(ExtractedFieldRecord)).scalars().one().field_key == "full_name"
        audit = session.execute(select(AuditEventRecord)).scalars().one()
        assert audit.case_id == "case_1"
        assert audit.record_hash


def test_sql_case_repository_updates_existing_case(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'cases.db'}")
    create_schema(engine)
    repository = SqlCaseRepository(engine)
    case = repository.add_case(build_case())
    case.applicant_name = "Sita Sharma Verified"
    case.extracted_fields[0].value = "Sita Sharma Verified"

    repository.save_case(case)
    loaded = repository.get_case(case.id)

    assert loaded.applicant_name == "Sita Sharma Verified"
    assert loaded.extracted_fields[0].value == "Sita Sharma Verified"
    assert len(repository.list_cases()) == 1
    assert len(loaded.audit_events) == 1


def build_document() -> DocumentRecord:
    return DocumentRecord(
        id="standalone_1",
        filename="passport.jpg",
        declared_document_type=DocumentType.passport,
        document_type=DocumentType.passport,
        status=DocumentStatus.review_required,
        overall_confidence=0.82,
        pages=[
            OcrPage(
                page_number=1,
                width=900,
                height=1200,
                blocks=[OcrBlock(text="Passport", bbox=[0, 0, 200, 40], confidence=0.8)],
                ocr_confidence=0.8,
            )
        ],
        fields=[
            ExtractedField(
                key="passport_number",
                label="Passport Number",
                value="1234567",
                confidence=0.85,
                evidence=EvidenceRef(document_id="standalone_1", source_page=1, evidence_text="1234567"),
                document_id="standalone_1",
            )
        ],
        validation_findings=[
            ValidationFinding(
                severity="warning",
                code="review_passport",
                message="Review passport number manually.",
                document_id="standalone_1",
            )
        ],
        review=ReviewState(reviewer="checker.two", note="Needs passport confirmation", reviewed_at=datetime.utcnow()),
        audit_events=[AuditEvent(action="document_uploaded", actor="uploader", note="Uploaded")],
        version_history=[
            DocumentVersion(
                version=1,
                action="uploaded",
                filename="passport.jpg",
                document_type=DocumentType.passport,
                status=DocumentStatus.review_required,
                overall_confidence=0.82,
                fields_count=1,
                actor="uploader",
            )
        ],
    )


def test_sql_document_repository_writes_normalized_rows(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'documents.db'}")
    create_schema(engine)
    repository = SqlDocumentRepository(engine)

    repository.add(build_document())
    loaded = repository.get("standalone_1")

    assert loaded.filename == "passport.jpg"
    assert loaded.pages[0].blocks[0].text == "Passport"
    assert loaded.fields[0].key == "passport_number"
    assert loaded.validation_findings[0].code == "review_passport"
    assert loaded.review.reviewer == "checker.two"
    assert loaded.version_history[0].action == "uploaded"
    assert repository.list()[0].id == "standalone_1"

    with session_scope(engine) as session:
        assert session.execute(select(DocumentRecordRow)).scalars().one().case_id is None
        assert session.execute(select(DocumentPageRecord)).scalars().one().case_id is None
        assert session.execute(select(OcrBlockRecord)).scalars().one().case_id is None
        assert session.execute(select(ExtractedFieldRecord)).scalars().one().case_id is None
        assert session.execute(select(ReviewRecord)).scalars().one().case_id is None
        assert session.execute(select(DocumentVersionRecord)).scalars().one().case_id is None
        assert session.execute(select(AuditEventRecord)).scalars().one().case_id is None
