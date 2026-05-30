from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.jobs.models import JobStatus, JobType, ProcessingJob


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._jobs: Dict[str, ProcessingJob] = {}
        self._queue: deque[str] = deque()

    def enqueue(
        self,
        job_type: JobType,
        target_type: str,
        target_id: str,
        payload: Dict[str, Any],
        max_attempts: int = 3,
    ) -> ProcessingJob:
        job = ProcessingJob(
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            max_attempts=max_attempts,
        )
        self._jobs[job.id] = job
        self._queue.append(job.id)
        return job

    def get(self, job_id: str) -> ProcessingJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def list_jobs(self, status: Optional[JobStatus] = None) -> list[ProcessingJob]:
        jobs = sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)
        if status is None:
            return jobs
        return [job for job in jobs if job.status == status]

    def claim_next(self) -> Optional[ProcessingJob]:
        while self._queue:
            job_id = self._queue.popleft()
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.queued:
                continue
            updated = job.model_copy(
                update={
                    "status": JobStatus.processing,
                    "started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "error": None,
                }
            )
            self._jobs[job_id] = updated
            return updated
        return None

    def complete(self, job_id: str, result: Dict[str, Any]) -> ProcessingJob:
        job = self.get(job_id)
        updated = job.model_copy(
            update={
                "status": JobStatus.completed,
                "result": result,
                "error": None,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )
        self._jobs[job_id] = updated
        return updated

    def fail(self, job_id: str, code: str, message: str) -> ProcessingJob:
        job = self.get(job_id)
        updated = job.model_copy(
            update={
                "status": JobStatus.failed,
                "error": {"code": code, "message": message},
                "updated_at": datetime.utcnow(),
            }
        )
        self._jobs[job_id] = updated
        return updated

    def retry(self, job_id: str) -> ProcessingJob:
        job = self.get(job_id)
        if job.status != JobStatus.failed:
            raise HTTPException(status_code=400, detail="Only failed jobs can be retried")
        if job.attempts >= job.max_attempts:
            raise HTTPException(status_code=400, detail="Job retry limit reached")
        updated = job.model_copy(
            update={
                "status": JobStatus.queued,
                "attempts": job.attempts + 1,
                "error": None,
                "updated_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
            }
        )
        self._jobs[job_id] = updated
        self._queue.append(job_id)
        return updated


job_queue = InMemoryJobQueue()


__all__ = ["InMemoryJobQueue", "job_queue"]
