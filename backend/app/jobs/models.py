from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    retry_scheduled = "retry_scheduled"


class JobType(str, Enum):
    document_upload = "document_upload"
    document_reanalyze = "document_reanalyze"
    document_replace = "document_replace"
    case_document_upload = "case_document_upload"
    case_document_reanalyze = "case_document_reanalyze"
    case_document_replace = "case_document_replace"
    template_test = "template_test"
    export_delivery = "export_delivery"


class ProcessingJob(BaseModel):
    id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:16]}")
    job_type: JobType
    status: JobStatus = JobStatus.queued
    target_type: str
    target_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[Dict[str, str]] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


__all__ = ["JobStatus", "JobType", "ProcessingJob"]
