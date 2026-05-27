import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException

from app.core.config import get_settings
from app.models import DocumentRecord, KycCase


class InMemoryEnterpriseRepository:
    def __init__(self) -> None:
        self._cases: Dict[str, KycCase] = {}
        self._documents: Dict[str, DocumentRecord] = {}

    def add_case(self, case: KycCase) -> KycCase:
        self._cases[case.id] = case
        return case

    def list_cases(self) -> List[KycCase]:
        return sorted(self._cases.values(), key=lambda item: item.created_at, reverse=True)

    def get_case(self, case_id: str) -> KycCase:
        case = self._cases.get(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    def save_case(self, case: KycCase) -> KycCase:
        case.updated_at = datetime.utcnow()
        self._cases[case.id] = case
        return case

    def add(self, document: DocumentRecord) -> DocumentRecord:
        self._documents[document.id] = document
        return document

    def list(self) -> List[DocumentRecord]:
        return sorted(self._documents.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, document_id: str) -> DocumentRecord:
        document = self._documents.get(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return document

    def save(self, document: DocumentRecord) -> DocumentRecord:
        document.updated_at = datetime.utcnow()
        self._documents[document.id] = document
        return document


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class SQLAlchemyEnterpriseRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url is required for SQLAlchemyEnterpriseRepository")
        try:
            from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, select
        except ImportError as exc:
            raise RuntimeError("Install SQL dependencies: pip install -e '.[test]'") from exc

        self._select = select
        self._engine = create_engine(
            _sqlalchemy_url(database_url),
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
            pool_pre_ping=True,
        )
        metadata = MetaData()
        self._cases = Table(
            "kyc_cases",
            metadata,
            Column("id", String(80), primary_key=True),
            Column("updated_at", DateTime, nullable=False),
            Column("payload", Text, nullable=False),
        )
        self._documents = Table(
            "legacy_documents",
            metadata,
            Column("id", String(80), primary_key=True),
            Column("updated_at", DateTime, nullable=False),
            Column("payload", Text, nullable=False),
        )
        metadata.create_all(self._engine)

    def _dump(self, model) -> str:
        return json.dumps(model.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)

    def add_case(self, case: KycCase) -> KycCase:
        self.save_case(case, update_timestamp=False)
        return case

    def list_cases(self) -> List[KycCase]:
        with self._engine.begin() as connection:
            rows = connection.execute(
                self._select(self._cases.c.payload).order_by(self._cases.c.updated_at.desc())
            ).all()
        return [KycCase.model_validate(json.loads(row.payload)) for row in rows]

    def get_case(self, case_id: str) -> KycCase:
        with self._engine.begin() as connection:
            row = connection.execute(
                self._select(self._cases.c.payload).where(self._cases.c.id == case_id)
            ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return KycCase.model_validate(json.loads(row.payload))

    def save_case(self, case: KycCase, update_timestamp: bool = True) -> KycCase:
        if update_timestamp:
            case.updated_at = datetime.utcnow()
        payload = self._dump(case)
        with self._engine.begin() as connection:
            existing = connection.execute(
                self._select(self._cases.c.id).where(self._cases.c.id == case.id)
            ).first()
            if existing:
                connection.execute(
                    self._cases.update()
                    .where(self._cases.c.id == case.id)
                    .values(updated_at=case.updated_at, payload=payload)
                )
            else:
                connection.execute(
                    self._cases.insert().values(id=case.id, updated_at=case.updated_at, payload=payload)
                )
        return case

    def add(self, document: DocumentRecord) -> DocumentRecord:
        self.save(document, update_timestamp=False)
        return document

    def list(self) -> List[DocumentRecord]:
        with self._engine.begin() as connection:
            rows = connection.execute(
                self._select(self._documents.c.payload).order_by(self._documents.c.updated_at.desc())
            ).all()
        return [DocumentRecord.model_validate(json.loads(row.payload)) for row in rows]

    def get(self, document_id: str) -> DocumentRecord:
        with self._engine.begin() as connection:
            row = connection.execute(
                self._select(self._documents.c.payload).where(self._documents.c.id == document_id)
            ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentRecord.model_validate(json.loads(row.payload))

    def save(self, document: DocumentRecord, update_timestamp: bool = True) -> DocumentRecord:
        if update_timestamp:
            document.updated_at = datetime.utcnow()
        payload = self._dump(document)
        with self._engine.begin() as connection:
            existing = connection.execute(
                self._select(self._documents.c.id).where(self._documents.c.id == document.id)
            ).first()
            if existing:
                connection.execute(
                    self._documents.update()
                    .where(self._documents.c.id == document.id)
                    .values(updated_at=document.updated_at, payload=payload)
                )
            else:
                connection.execute(
                    self._documents.insert().values(id=document.id, updated_at=document.updated_at, payload=payload)
                )
        return document


def build_repository(settings=None):
    active_settings = settings or get_settings()
    backend = active_settings.repository_backend
    if backend == "auto":
        backend = "sql" if active_settings.database_url else "memory"
    if backend == "sql":
        return SQLAlchemyEnterpriseRepository(active_settings.database_url)
    return InMemoryEnterpriseRepository()


repository = build_repository()
