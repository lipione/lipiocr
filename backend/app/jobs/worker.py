from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Optional

from app.jobs.models import JobType, ProcessingJob
from app.jobs.queue import InMemoryJobQueue

JobHandler = Callable[[ProcessingJob], dict]


def run_next_job(queue: InMemoryJobQueue, handlers: Mapping[JobType, JobHandler]) -> Optional[ProcessingJob]:
    job = queue.claim_next()
    if job is None:
        return None

    handler = handlers.get(job.job_type)
    if handler is None:
        return queue.fail(
            job.id,
            code="unsupported_job_type",
            message=f"No worker is configured for {job.job_type.value}",
        )

    try:
        result = handler(job)
    except Exception:
        return queue.fail(
            job.id,
            code="handler_failed",
            message="Document processing failed. Retry the job or send it to manual review.",
        )

    return queue.complete(job.id, result)


def retry_failed_job(queue: InMemoryJobQueue, job_id: str) -> ProcessingJob:
    return queue.retry(job_id)


__all__ = ["JobHandler", "retry_failed_job", "run_next_job"]
