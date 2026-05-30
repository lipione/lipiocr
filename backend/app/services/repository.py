from datetime import datetime
from typing import Dict, List

from fastapi import HTTPException

from app.core.config import get_settings
from app.db.session import build_engine, create_schema
from app.models import DocumentRecord, KycCase
from app.repositories.cases import SqlCaseRepository
from app.repositories.documents import SqlDocumentRepository


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


def build_repository(settings=None):
    active_settings = settings or get_settings()
    backend = active_settings.repository_backend
    if backend == "auto":
        backend = "sql" if active_settings.database_url else "memory"
    if backend == "sql":
        return SQLAlchemyEnterpriseRepository(active_settings.database_url)
    return InMemoryEnterpriseRepository()


repository = build_repository()
