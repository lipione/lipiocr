from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CaseType, DocumentType, KycCase


client = TestClient(app)


def test_sql_repository_durably_reloads_cases(tmp_path: Path):
    from app.services.repository import SQLAlchemyEnterpriseRepository

    db_url = f"sqlite:///{tmp_path / 'lipiocr.db'}"
    first = SQLAlchemyEnterpriseRepository(db_url)
    case = first.add_case(
        KycCase(
            case_type=CaseType.individual_kyc,
            applicant_name="Durable Customer",
            institution_id="demo-bank",
            branch_code="KTM-DB",
            integration_ref="CBS-DURABLE",
        )
    )

    second = SQLAlchemyEnterpriseRepository(db_url)

    assert second.get_case(case.id).applicant_name == "Durable Customer"
    assert second.list_cases()[0].integration_ref == "CBS-DURABLE"


def test_local_object_storage_writes_upload_and_metadata(tmp_path: Path):
    from app.services.storage import LocalObjectStorage

    storage = LocalObjectStorage(tmp_path)

    result = storage.put_upload(
        case_id="case_storage",
        filename="citizenship.txt",
        content=b"Name: Storage Customer",
        content_type="text/plain",
    )

    assert result["backend"] == "local"
    assert result["object_key"].startswith("cases/case_storage/original/")
    assert (tmp_path / result["object_key"]).read_bytes() == b"Name: Storage Customer"
    assert result["uri"].startswith("local://")


def test_binary_upload_uses_configured_ocr_provider(tmp_path: Path):
    from app.services.enterprise_extraction import build_pages_from_upload
    from app.services.ocr import OcrObservation

    class FakeProvider:
        name = "fake"

        def read(self, file_path: Path, document_type: DocumentType):
            assert file_path.exists()
            assert document_type == DocumentType.citizenship
            return [OcrObservation(field_key="raw_text", text="Binary OCR Name", confidence=0.74)]

    source_path = tmp_path / "scan.bin"
    source_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    pages = build_pages_from_upload(
        b"\x89PNG\r\n\x1a\n",
        "scan.bin",
        ocr_provider=FakeProvider(),
        source_path=source_path,
        document_type=DocumentType.citizenship,
    )

    assert pages[0].blocks[0].text == "Binary OCR Name"
    assert pages[0].blocks[0].confidence == 0.74


def test_auth_rbac_enforces_api_key_when_enabled():
    from app.main import settings

    original_enabled = settings.api_auth_enabled
    original_keys = settings.api_keys
    try:
        settings.api_auth_enabled = True
        settings.api_keys = "maker-secret:maker,checker-secret:checker"

        denied = client.post(
            "/api/cases",
            json={"case_type": "individual_kyc", "applicant_name": "Blocked Customer"},
        )
        assert denied.status_code == 401

        allowed = client.post(
            "/api/cases",
            headers={"X-LipiOCR-API-Key": "maker-secret"},
            json={"case_type": "individual_kyc", "applicant_name": "Allowed Customer"},
        )
        assert allowed.status_code == 201
    finally:
        settings.api_auth_enabled = original_enabled
        settings.api_keys = original_keys


def test_checker_permission_required_for_approval_when_auth_enabled():
    from app.main import settings

    original_enabled = settings.api_auth_enabled
    original_keys = settings.api_keys
    try:
        settings.api_auth_enabled = True
        settings.api_keys = "maker-secret:maker,checker-secret:checker"
        created = client.post(
            "/api/cases",
            headers={"X-LipiOCR-API-Key": "maker-secret"},
            json={"case_type": "individual_kyc", "applicant_name": "Review Customer"},
        ).json()

        denied = client.patch(
            f"/api/cases/{created['id']}/review",
            headers={"X-LipiOCR-API-Key": "maker-secret"},
            json={"reviewer": "maker.one", "decision": "approve", "field_updates": {}, "note": "try"},
        )
        assert denied.status_code == 403

        allowed = client.patch(
            f"/api/cases/{created['id']}/review",
            headers={"X-LipiOCR-API-Key": "checker-secret"},
            json={"reviewer": "checker.one", "decision": "approve", "field_updates": {}, "note": "ok"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "approved"
    finally:
        settings.api_auth_enabled = original_enabled
        settings.api_keys = original_keys


def test_sql_repository_backend_uses_normalized_tables(tmp_path, monkeypatch):
    from sqlalchemy import inspect

    from app.core.config import Settings, get_settings
    from app.models import CaseType, KycCase
    from app.services.repository import build_repository

    db_path = tmp_path / "production.db"
    get_settings.cache_clear()
    try:
        repository = build_repository(Settings(repository_backend="sql", database_url=f"sqlite:///{db_path}"))
        repository.add_case(
            KycCase(
                case_type=CaseType.individual_kyc,
                applicant_name="Durable",
                institution_id="tenant_1",
            )
        )

        engine = repository.engine
        names = set(inspect(engine).get_table_names())
        assert {"cases", "documents", "audit_events", "extracted_fields"}.issubset(names)
        assert "kyc_cases" not in names
        assert "legacy_documents" not in names
        assert repository.list_cases()[0].applicant_name == "Durable"
    finally:
        get_settings.cache_clear()
