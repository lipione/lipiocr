# Production Readiness Phase 2 Database And Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SQL JSON-payload persistence with normalized tenant-scoped domain tables and immutable audit storage while preserving the current repository API.

**Architecture:** Keep `InMemoryEnterpriseRepository` for demos/tests that do not configure SQL. For `repository_backend=sql`, route persistence through focused SQLAlchemy repositories backed by production tables. The first cut stores normalized scalar/domain rows plus small JSON metadata/evidence columns where the product model is intentionally flexible; it must not use a single case/document payload column as the primary storage model.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, pytest, SQLite test database, Postgres-compatible schema.

---

## File Structure

- Create `backend/app/db/__init__.py`: exports database helpers.
- Create `backend/app/db/models.py`: SQLAlchemy declarative models for production tables.
- Create `backend/app/db/session.py`: URL normalization, engine/session factories, schema creation helper.
- Create `backend/app/repositories/__init__.py`: repository package marker.
- Create `backend/app/repositories/audit.py`: immutable hash-chained audit repository.
- Create `backend/app/repositories/cases.py`: SQL case repository with normalized case/document/field/audit persistence.
- Create `backend/app/repositories/documents.py`: SQL standalone document repository.
- Modify `backend/app/services/repository.py`: keep memory repository; replace SQL JSON blob repository with the normalized repositories.
- Modify `backend/pyproject.toml`: add Alembic dependency.
- Create `backend/alembic.ini`: Alembic config.
- Create `backend/migrations/env.py`: Alembic environment loading `app.db.models.Base.metadata`.
- Create `backend/migrations/script.py.mako`: migration template.
- Create `backend/migrations/versions/20260530_0001_initial_production_schema.py`: initial production schema migration.
- Create `backend/tests/test_database_models.py`: verifies required tables and tenant columns.
- Create `backend/tests/test_db_session.py`: verifies schema creation and SQLAlchemy URL handling.
- Create `backend/tests/test_audit_repository.py`: verifies append-only hash chain behavior.
- Create `backend/tests/test_database_repository.py`: verifies normalized SQL repository round trips cases/documents/fields/audit.
- Create `backend/tests/test_alembic_migration.py`: verifies Alembic can upgrade a SQLite database to the initial schema.

## Required Domain Tables

Every table below that stores institution data must include `tenant_id`:

- `cases`
- `documents`
- `document_versions`
- `document_pages`
- `ocr_blocks`
- `extracted_fields`
- `field_corrections`
- `reviews`
- `exports`
- `jobs`
- `audit_events`
- `template_profiles`
- `template_versions`
- `integration_events`

The schema may also include `tenants`, which does not require a parent `tenant_id` because it is the tenant registry itself.

## Task 1: Production Database Model Contract

**Files:**

- Create: `backend/tests/test_database_models.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/models.py`

- [ ] **Step 1: Write failing table contract tests**

Create `backend/tests/test_database_models.py`:

```python
from app.db.models import Base, TENANT_SCOPED_TABLES, all_domain_tables


REQUIRED_TABLES = {
    "tenants",
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


def test_production_domain_tables_are_declared():
    assert REQUIRED_TABLES.issubset(set(all_domain_tables()))
    assert REQUIRED_TABLES.issubset(set(Base.metadata.tables))


def test_tenant_scoped_tables_have_tenant_id():
    for table_name in TENANT_SCOPED_TABLES:
        table = Base.metadata.tables[table_name]
        assert "tenant_id" in table.c, table_name
        assert table.c.tenant_id.index is True


def test_audit_table_supports_immutable_hash_chain():
    audit = Base.metadata.tables["audit_events"]
    for column_name in ["id", "tenant_id", "entity_type", "entity_id", "action", "actor", "previous_hash", "record_hash"]:
        assert column_name in audit.c
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`.

- [ ] **Step 3: Add SQLAlchemy model declarations**

Create `backend/app/db/__init__.py`:

```python
"""Database models and session helpers for production persistence."""
```

Create `backend/app/db/models.py` with these public names:

```python
from datetime import datetime
from typing import Dict

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
    branch_code: Mapped[str | None] = mapped_column(String(80))
    integration_ref: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentRecordRow(TenantScopedMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    declared_document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DocumentVersionRecord(TenantScopedMixin, Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
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
    document_id: Mapped[str] = mapped_column(String(80), ForeignKey("documents.id"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_uri: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class OcrBlockRecord(TenantScopedMixin, Base):
    __tablename__ = "ocr_blocks"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
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
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(80), nullable=False)
    validation_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    correction: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FieldCorrectionRecord(TenantScopedMixin, Base):
    __tablename__ = "field_corrections"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    original_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrected_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReviewRecord(TenantScopedMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    reviewer: Mapped[str | None] = mapped_column(String(160))
    decision: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ExportRecord(TenantScopedMixin, Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("documents.id"), index=True)
    profile_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class JobRecord(TenantScopedMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditEventRecord(TenantScopedMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
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
    pages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IntegrationEventRecord(TenantScopedMixin, Base):
    __tablename__ = "integration_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True)
    mode: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    target: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_extracted_fields_case_key", ExtractedFieldRecord.case_id, ExtractedFieldRecord.field_key)
Index("ix_audit_events_entity_created", AuditEventRecord.entity_type, AuditEventRecord.entity_id, AuditEventRecord.created_at)


def all_domain_tables() -> Dict[str, object]:
    return dict(Base.metadata.tables)
```

- [ ] **Step 4: Run the database model tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/db backend/tests/test_database_models.py
git commit -m "feat: add production database models"
```

## Task 2: Session Factory And Schema Creation

**Files:**

- Create: `backend/app/db/session.py`
- Create: `backend/tests/test_db_session.py`

- [ ] **Step 1: Write failing session tests**

Create `backend/tests/test_db_session.py`:

```python
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
                created_at=__import__("datetime").datetime.utcnow(),
                updated_at=__import__("datetime").datetime.utcnow(),
            )
        )

    with session_scope(engine) as session:
        assert session.execute(select(CaseRecord).where(CaseRecord.id == "case_1")).scalar_one().tenant_id == "tenant_1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_db_session.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement session helpers**

Create `backend/app/db/session.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


def sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def build_engine(database_url: str) -> Engine:
    return create_engine(
        sqlalchemy_url(database_url),
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 4: Run session tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_db_session.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/db/session.py backend/tests/test_db_session.py
git commit -m "feat: add database session helpers"
```

## Task 3: Alembic Baseline Migration

**Files:**

- Modify: `backend/pyproject.toml`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/20260530_0001_initial_production_schema.py`
- Create: `backend/tests/test_alembic_migration.py`

- [ ] **Step 1: Add Alembic dependency and install local backend package**

In `backend/pyproject.toml`, add Alembic to dependencies:

```toml
"alembic>=1.13,<2.0",
```

Run:

```bash
cd backend && .venv/bin/python -m pip install -e '.[test]'
```

Expected: `Successfully installed` or `Successfully built` output including `alembic`.

- [ ] **Step 2: Write failing Alembic test**

Create `backend/tests/test_alembic_migration.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_initial_schema(tmp_path: Path):
    db_path = tmp_path / "alembic.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    names = set(inspect(engine).get_table_names())
    assert {"cases", "documents", "audit_events", "ocr_blocks", "jobs"}.issubset(names)
```

- [ ] **Step 3: Run the Alembic test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_alembic_migration.py -q
```

Expected: FAIL with missing Alembic config or migration folder.

- [ ] **Step 4: Add Alembic config and migration**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = sqlite:///storage/lipiocr.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa

${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/migrations/versions/20260530_0001_initial_production_schema.py`:

```python
"""initial production schema

Revision ID: 20260530_0001
Revises:
Create Date: 2026-05-30
"""
from alembic import op

from app.db.models import Base

revision = "20260530_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
```

- [ ] **Step 5: Run Alembic test**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_alembic_migration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/pyproject.toml backend/alembic.ini backend/migrations backend/tests/test_alembic_migration.py
git commit -m "feat: add alembic production schema baseline"
```

## Task 4: Immutable Audit Repository

**Files:**

- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/audit.py`
- Create: `backend/tests/test_audit_repository.py`

- [ ] **Step 1: Write failing audit repository tests**

Create `backend/tests/test_audit_repository.py`:

```python
from pathlib import Path

from app.db.session import build_engine, create_schema
from app.repositories.audit import AuditRepository


def test_audit_repository_appends_hash_chain(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    create_schema(engine)
    repository = AuditRepository(engine)

    first = repository.append_event(
        tenant_id="tenant_1",
        entity_type="case",
        entity_id="case_1",
        action="case_created",
        actor="maker.one",
        note="Created case",
        metadata={"branch": "KTM"},
    )
    second = repository.append_event(
        tenant_id="tenant_1",
        entity_type="case",
        entity_id="case_1",
        action="review_saved",
        actor="checker.one",
        note="Reviewed",
        metadata={},
    )

    assert first.previous_hash == ""
    assert len(first.record_hash) == 64
    assert second.previous_hash == first.record_hash
    assert second.record_hash != first.record_hash

    events = repository.list_events(tenant_id="tenant_1", entity_type="case", entity_id="case_1")
    assert [event.action for event in events] == ["case_created", "review_saved"]


def test_audit_repository_scopes_by_tenant(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    create_schema(engine)
    repository = AuditRepository(engine)
    repository.append_event("tenant_1", "case", "case_1", "case_created", "maker.one", "", {})
    repository.append_event("tenant_2", "case", "case_1", "case_created", "maker.two", "", {})

    assert len(repository.list_events("tenant_1", "case", "case_1")) == 1
    assert repository.list_events("tenant_1", "case", "case_1")[0].actor == "maker.one"
```

- [ ] **Step 2: Run the audit tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_audit_repository.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories'`.

- [ ] **Step 3: Implement audit repository**

Create `backend/app/repositories/__init__.py`:

```python
"""SQL repository implementations for production persistence."""
```

Create `backend/app/repositories/audit.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Engine, select

from app.db.models import AuditEventRecord
from app.db.session import session_scope


def _canonical_payload(*, tenant_id: str, entity_type: str, entity_id: str, action: str, actor: str, note: str, metadata: dict, previous_hash: str, created_at: datetime) -> str:
    return json.dumps(
        {
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "note": note,
            "metadata": metadata,
            "previous_hash": previous_hash,
            "created_at": created_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class AuditRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def append_event(
        self,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        note: str,
        metadata: dict,
    ) -> AuditEventRecord:
        with session_scope(self.engine) as session:
            previous = session.execute(
                select(AuditEventRecord)
                .where(AuditEventRecord.tenant_id == tenant_id)
                .where(AuditEventRecord.entity_type == entity_type)
                .where(AuditEventRecord.entity_id == entity_id)
                .order_by(AuditEventRecord.created_at.desc())
            ).scalars().first()
            created_at = datetime.utcnow()
            previous_hash = previous.record_hash if previous else ""
            payload = _canonical_payload(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=actor,
                note=note,
                metadata=metadata,
                previous_hash=previous_hash,
                created_at=created_at,
            )
            record = AuditEventRecord(
                id=f"audit_{uuid4().hex}",
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor=actor,
                note=note,
                metadata_json=metadata,
                previous_hash=previous_hash,
                record_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                created_at=created_at,
            )
            session.add(record)
            session.flush()
            session.refresh(record)
            return record

    def list_events(self, tenant_id: str, entity_type: str, entity_id: str) -> list[AuditEventRecord]:
        with session_scope(self.engine) as session:
            return list(
                session.execute(
                    select(AuditEventRecord)
                    .where(AuditEventRecord.tenant_id == tenant_id)
                    .where(AuditEventRecord.entity_type == entity_type)
                    .where(AuditEventRecord.entity_id == entity_id)
                    .order_by(AuditEventRecord.created_at.asc())
                ).scalars()
            )
```

- [ ] **Step 4: Run audit tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_audit_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/repositories backend/tests/test_audit_repository.py
git commit -m "feat: add immutable audit repository"
```

## Task 5: Normalized SQL Case Repository

**Files:**

- Create: `backend/app/repositories/cases.py`
- Test: `backend/tests/test_database_repository.py`

- [ ] **Step 1: Write failing SQL case repository test**

Create `backend/tests/test_database_repository.py`:

```python
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.db.models import AuditEventRecord, CaseRecord, DocumentPageRecord, DocumentRecordRow, ExtractedFieldRecord, OcrBlockRecord
from app.db.session import build_engine, create_schema, session_scope
from app.models import AuditEvent, CaseType, ExtractedField, EvidenceRef, FinancialDocument, KycCase, OcrBlock, OcrPage
from app.repositories.cases import SqlCaseRepository


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
                evidence=EvidenceRef(document_id="doc_1", source_page=1, bbox=[10, 20, 200, 60], evidence_text="Sita Sharma"),
                document_id="doc_1",
            )
        ],
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

    with session_scope(engine) as session:
        assert session.execute(select(CaseRecord)).scalars().one().tenant_id == "tenant_1"
        assert session.execute(select(DocumentRecordRow)).scalars().one().tenant_id == "tenant_1"
        assert session.execute(select(DocumentPageRecord)).scalars().one().document_id == "doc_1"
        assert session.execute(select(OcrBlockRecord)).scalars().one().text == "Sita Sharma"
        assert session.execute(select(ExtractedFieldRecord)).scalars().one().field_key == "full_name"
        assert session.execute(select(AuditEventRecord)).scalars().one().record_hash


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_repository.py -q
```

Expected: FAIL with missing `app.repositories.cases`.

- [ ] **Step 3: Implement `SqlCaseRepository`**

Create `backend/app/repositories/cases.py` with:

- `SqlCaseRepository(engine)`
- `add_case(case: KycCase) -> KycCase`
- `save_case(case: KycCase, update_timestamp: bool = True) -> KycCase`
- `list_cases() -> list[KycCase]`
- `get_case(case_id: str) -> KycCase`
- private helpers that upsert `CaseRecord`, delete/replace child rows for that case, persist case documents/pages/blocks/fields/review/audit events, and reconstruct `KycCase`.

Implementation requirements:

```python
tenant_id = case.institution_id or "demo-institution"
```

Field row IDs must be deterministic:

```python
field_id = f"{case.id}:{field.document_id or field.evidence.document_id or 'case'}:{index}:{field.key}"
```

Audit rows must use the same hash-chain pattern as `AuditRepository`; do not store audit only inside a JSON case payload.

- [ ] **Step 4: Run SQL case repository tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/repositories/cases.py backend/tests/test_database_repository.py
git commit -m "feat: add normalized sql case repository"
```

## Task 6: Normalized SQL Standalone Document Repository

**Files:**

- Create: `backend/app/repositories/documents.py`
- Modify: `backend/tests/test_database_repository.py`

- [ ] **Step 1: Add failing standalone document tests**

Append to `backend/tests/test_database_repository.py`:

```python
from app.models import DocumentRecord, DocumentStatus, DocumentType
from app.repositories.documents import SqlDocumentRepository


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
        audit_events=[AuditEvent(action="document_uploaded", actor="uploader", note="Uploaded")],
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
    assert repository.list()[0].id == "standalone_1"
```

- [ ] **Step 2: Run the repository tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_repository.py -q
```

Expected: FAIL with missing `app.repositories.documents`.

- [ ] **Step 3: Implement document repository**

Create `backend/app/repositories/documents.py` with:

- `SqlDocumentRepository(engine, tenant_id: str = "demo-institution")`
- `add(document: DocumentRecord) -> DocumentRecord`
- `save(document: DocumentRecord, update_timestamp: bool = True) -> DocumentRecord`
- `list() -> list[DocumentRecord]`
- `get(document_id: str) -> DocumentRecord`

Reuse the same table mapping conventions from `SqlCaseRepository`; standalone documents must store `case_id=None`.

- [ ] **Step 4: Run repository tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/repositories/documents.py backend/tests/test_database_repository.py
git commit -m "feat: add normalized sql document repository"
```

## Task 7: Wire SQL Backend Into Existing Repository Service

**Files:**

- Modify: `backend/app/services/repository.py`
- Modify: `backend/tests/test_production_foundations.py`

- [ ] **Step 1: Add failing durable normalized repository test**

Append to `backend/tests/test_production_foundations.py`:

```python
def test_sql_repository_backend_uses_normalized_tables(tmp_path, monkeypatch):
    from sqlalchemy import inspect

    from app.core.config import get_settings
    from app.models import CaseType, KycCase
    from app.services.repository import build_repository

    db_path = tmp_path / "production.db"
    monkeypatch.setenv("LIPIOCR_REPOSITORY_BACKEND", "sql")
    monkeypatch.setenv("LIPIOCR_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        repository = build_repository(get_settings())
        repository.add_case(KycCase(case_type=CaseType.individual_kyc, applicant_name="Durable", institution_id="tenant_1"))

        engine = repository.engine
        names = set(inspect(engine).get_table_names())
        assert {"cases", "documents", "audit_events", "extracted_fields"}.issubset(names)
        assert "kyc_cases" not in names
        assert repository.list_cases()[0].applicant_name == "Durable"
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_production_foundations.py::test_sql_repository_backend_uses_normalized_tables -q
```

Expected: FAIL because current SQL repository uses `kyc_cases` and `legacy_documents` JSON tables.

- [ ] **Step 3: Replace SQL JSON repository adapter**

Modify `backend/app/services/repository.py`:

- Keep `InMemoryEnterpriseRepository` unchanged.
- Remove `SQLAlchemyEnterpriseRepository` JSON table implementation.
- Add a new `SQLAlchemyEnterpriseRepository` that composes `SqlCaseRepository` and `SqlDocumentRepository`.
- Expose `engine` for tests.

Expected public shape:

```python
class SQLAlchemyEnterpriseRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required for SQLAlchemyEnterpriseRepository")
        self.engine = build_engine(database_url)
        create_schema(self.engine)
        self.cases = SqlCaseRepository(self.engine)
        self.documents = SqlDocumentRepository(self.engine)

    def add_case(self, case: KycCase) -> KycCase:
        return self.cases.add_case(case)

    def list_cases(self) -> List[KycCase]:
        return self.cases.list_cases()

    def get_case(self, case_id: str) -> KycCase:
        return self.cases.get_case(case_id)

    def save_case(self, case: KycCase, update_timestamp: bool = True) -> KycCase:
        return self.cases.save_case(case, update_timestamp=update_timestamp)

    def add(self, document: DocumentRecord) -> DocumentRecord:
        return self.documents.add(document)

    def list(self) -> List[DocumentRecord]:
        return self.documents.list()

    def get(self, document_id: str) -> DocumentRecord:
        return self.documents.get(document_id)

    def save(self, document: DocumentRecord, update_timestamp: bool = True) -> DocumentRecord:
        return self.documents.save(document, update_timestamp=update_timestamp)
```

- [ ] **Step 4: Run repository and production foundation tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_repository.py tests/test_audit_repository.py tests/test_production_foundations.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/repository.py backend/tests/test_production_foundations.py
git commit -m "refactor: use normalized sql repository backend"
```

## Task 8: Phase 2 Verification

**Files:**

- Modify: no production files unless verification exposes a defect.

- [ ] **Step 1: Run database/audit focused tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_database_models.py tests/test_db_session.py tests/test_alembic_migration.py tests/test_audit_repository.py tests/test_database_repository.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run:

```bash
make test
```

Expected:

- Backend tests pass.
- Frontend tests pass.
- ESLint passes.
- Next production build passes.

- [ ] **Step 3: Verify no legacy SQL JSON tables are primary**

Run:

```bash
cd backend && .venv/bin/python - <<'PY'
from sqlalchemy import inspect
from app.db.session import build_engine, create_schema

engine = build_engine("sqlite:///:memory:")
create_schema(engine)
tables = set(inspect(engine).get_table_names())
print(sorted(table for table in tables if table in {"kyc_cases", "legacy_documents"}))
assert "kyc_cases" not in tables
assert "legacy_documents" not in tables
PY
```

Expected: prints `[]`.

- [ ] **Step 4: Commit verification notes only if this plan is updated**

If adding notes to this plan, run:

```bash
git add docs/superpowers/plans/2026-05-30-production-readiness-phase-2-database-audit.md
git commit -m "docs: record phase 2 verification"
```

If no files changed after verification, do not create an empty commit.

## Phase 2 Completion Criteria

- `make test` passes.
- SQL backend creates normalized production tables instead of `kyc_cases` and `legacy_documents` JSON-payload tables.
- All institution-data tables include `tenant_id`.
- Case, document, page, OCR block, extracted field, review, export/job placeholder, template, integration, and audit tables exist.
- SQL case and standalone document repositories can round-trip current Pydantic API models.
- Audit events are append-only and hash chained per tenant/entity.
- Existing in-memory demo behavior remains available.

## Verification Log

- 2026-05-30: `cd backend && .venv/bin/python -m pytest tests/test_database_models.py tests/test_db_session.py tests/test_alembic_migration.py tests/test_audit_repository.py tests/test_database_repository.py -q` passed with `12 passed`.
- 2026-05-30: in-memory schema check printed `[]` for legacy `kyc_cases` and `legacy_documents` tables.
- 2026-05-30: `make test` passed with backend `87 passed`, frontend Node tests `10 passed`, ESLint clean, and Next production build successful.
