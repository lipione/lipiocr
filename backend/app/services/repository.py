from datetime import datetime
from typing import Dict, List

from fastapi import HTTPException

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


repository = InMemoryEnterpriseRepository()
