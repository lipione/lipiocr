from app.jobs.models import JobStatus, JobType
from app.jobs.queue import InMemoryJobQueue
from app.jobs.worker import retry_failed_job, run_next_job


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


def test_worker_completes_claimed_job_with_handler_result():
    queue = InMemoryJobQueue()
    job = queue.enqueue(JobType.document_upload, "document", "doc_1", {"filename": "doc.jpg"})

    completed = run_next_job(
        queue,
        handlers={JobType.document_upload: lambda claimed: {"document_id": claimed.target_id}},
    )

    assert completed is not None
    assert completed.id == job.id
    assert completed.status == JobStatus.completed
    assert completed.result == {"document_id": "doc_1"}


def test_worker_fails_job_with_safe_error_when_handler_raises():
    queue = InMemoryJobQueue()
    job = queue.enqueue(JobType.document_upload, "document", "doc_1", {})

    def broken_handler(_job):
        raise RuntimeError("remote OCR password leaked")

    failed = run_next_job(queue, handlers={JobType.document_upload: broken_handler})

    assert failed is not None
    assert failed.id == job.id
    assert failed.status == JobStatus.failed
    assert failed.error == {
        "code": "handler_failed",
        "message": "Document processing failed. Retry the job or send it to manual review.",
    }
    assert "password" not in str(failed.error).lower()


def test_worker_marks_unknown_job_type_failed():
    queue = InMemoryJobQueue()
    job = queue.enqueue(JobType.template_test, "template", "tpl_1", {})

    failed = run_next_job(queue, handlers={})

    assert failed is not None
    assert failed.id == job.id
    assert failed.status == JobStatus.failed
    assert failed.error == {"code": "unsupported_job_type", "message": "No worker is configured for template_test"}


def test_retry_failed_job_requeues_job():
    queue = InMemoryJobQueue()
    job = queue.enqueue(JobType.document_upload, "document", "doc_1", {})
    queue.claim_next()
    queue.fail(job.id, code="handler_failed", message="Document processing failed")

    retried = retry_failed_job(queue, job.id)

    assert retried.status == JobStatus.queued
    assert retried.attempts == 1
