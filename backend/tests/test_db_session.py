from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, select

from app.db.models import CaseRecord
from app.db.session import build_engine, create_schema, session_scope, sqlalchemy_url


def test_sqlalchemy_url_uses_psycopg_driver_for_postgres():
    assert sqlalchemy_url("postgresql://user:pass@db/lipiocr").startswith("postgresql+psycopg://")
    assert sqlalchemy_url("sqlite:///tmp/lipiocr.db") == "sqlite:///tmp/lipiocr.db"


def test_create_schema_creates_domain_tables(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'lipiocr.db'}")
    create_schema(engine)
    names = set(inspect(engine).get_table_names())
    assert {"cases", "documents", "audit_events", "extracted_fields"}.issubset(names)


def test_session_scope_commits_and_closes(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'lipiocr.db'}")
    create_schema(engine)

    with session_scope(engine) as session:
        session.add(
            CaseRecord(
                id="case_1",
                tenant_id="tenant_1",
                case_type="individual_kyc",
                applicant_name="Sita Sharma",
                institution_id="tenant_1",
                status="created",
                risk_level="medium",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

    with session_scope(engine) as session:
        row = session.execute(select(CaseRecord).where(CaseRecord.id == "case_1")).scalar_one()
        assert row.tenant_id == "tenant_1"
