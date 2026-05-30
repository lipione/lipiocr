from app.jobs.models import JobStatus, JobType
from app.jobs.queue import InMemoryJobQueue


def test_job_queue_enqueues_and_completes_job():
    queue = InMemoryJobQueue()

    job = queue.enqueue(
        job_type=JobType.document_upload,
        target_type="document",
        target_id="doc_1",
        payload={"filename": "citizenship.jpg"},
    )

    assert job.status == JobStatus.queued
    assert job.attempts == 0

    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.processing
    assert claimed.started_at is not None

    completed = queue.complete(job.id, {"document_id": "doc_1", "status": "review_required"})
    assert completed.status == JobStatus.completed
    assert completed.result["document_id"] == "doc_1"
    assert completed.completed_at is not None


def test_job_queue_records_safe_failure_and_retries():
    queue = InMemoryJobQueue()
    job = queue.enqueue(
        job_type=JobType.document_reanalyze,
        target_type="document",
        target_id="doc_2",
        payload={},
    )
    queue.claim_next()

    failed = queue.fail(job.id, code="ocr_failed", message="OCR engine could not read this page")

    assert failed.status == JobStatus.failed
    assert failed.error == {"code": "ocr_failed", "message": "OCR engine could not read this page"}
    assert "Traceback" not in str(failed.error)

    retried = queue.retry(job.id)
    assert retried.status == JobStatus.queued
    assert retried.error is None
    assert retried.attempts == 1
    assert queue.claim_next().id == job.id


def test_job_queue_lists_by_status():
    queue = InMemoryJobQueue()
    queued = queue.enqueue(JobType.document_upload, "document", "doc_1", {})
    failed = queue.enqueue(JobType.document_upload, "document", "doc_2", {})
    queue.claim_next()
    queue.fail(queued.id, code="failed", message="Failed")
    queue.claim_next()
    queue.fail(failed.id, code="failed", message="Failed")
    queue.retry(failed.id)

    failed_jobs = queue.list_jobs(status=JobStatus.failed)
    queued_jobs = queue.list_jobs(status=JobStatus.queued)

    assert [job.id for job in failed_jobs] == [queued.id]
    assert [job.id for job in queued_jobs] == [failed.id]
