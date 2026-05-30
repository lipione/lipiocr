from __future__ import annotations

from typing import Any, Callable, Dict

from app.jobs.models import JobType, ProcessingJob
from app.models import DocumentRecord, KycCase


class DocumentJobProcessor:
    def process_standalone_upload(self, payload: Dict[str, Any]) -> DocumentRecord:
        raise NotImplementedError

    def process_case_document_upload(self, case: KycCase, payload: Dict[str, Any]) -> KycCase:
        raise NotImplementedError


def _document_result(document: DocumentRecord) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "document_type": document.document_type.value,
        "status": document.status.value,
        "summary": document.summary,
        "review_url": f"/documents/{document.id}",
    }


def _case_result(case: KycCase) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "status": case.status.value,
        "document_count": len(case.documents),
        "review_url": f"/cases/{case.id}",
    }


def _standalone_upload_handler(repository, processor) -> Callable[[ProcessingJob], dict[str, Any]]:
    def handler(job: ProcessingJob) -> dict[str, Any]:
        document = processor.process_standalone_upload(job.payload)
        repository.add(document)
        return _document_result(document)

    return handler


def _case_document_upload_handler(repository, processor) -> Callable[[ProcessingJob], dict[str, Any]]:
    def handler(job: ProcessingJob) -> dict[str, Any]:
        case_id = str(job.payload.get("case_id") or job.target_id)
        case = repository.get_case(case_id)
        updated_case = processor.process_case_document_upload(case, job.payload)
        repository.save_case(updated_case)
        return _case_result(updated_case)

    return handler


def build_document_job_handlers(
    *,
    repository,
    processor,
    object_storage=None,
    upload_dir=None,
    ocr_provider_factory=None,
    gemma_client_factory=None,
) -> dict[JobType, Callable[[ProcessingJob], dict[str, Any]]]:
    return {
        JobType.document_upload: _standalone_upload_handler(repository, processor),
        JobType.case_document_upload: _case_document_upload_handler(repository, processor),
    }


__all__ = ["DocumentJobProcessor", "build_document_job_handlers"]
