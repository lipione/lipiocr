from fastapi.testclient import TestClient

from app.jobs.queue import job_queue
from app.main import app, settings


client = TestClient(app)


def test_async_standalone_upload_returns_job_and_status_url():
    original_enabled = settings.async_jobs_enabled
    job_queue.clear()
    try:
        settings.async_jobs_enabled = True
        response = client.post(
            "/api/documents/upload",
            data={"document_type": "unknown", "declared_document_type": "unknown"},
            files={"file": ("queued.txt", b"Name: Queued Customer", "text/plain")},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["job_id"].startswith("job_")
        assert body["status_url"] == f"/api/jobs/{body['job_id']}"

        status = client.get(body["status_url"])
        assert status.status_code == 200
        assert status.json()["id"] == body["job_id"]
        assert status.json()["payload"]["filename"] == "queued.txt"
    finally:
        settings.async_jobs_enabled = original_enabled
        job_queue.clear()


def test_retry_failed_job_endpoint_requeues_failed_job():
    job_queue.clear()
    try:
        job = job_queue.enqueue(
            job_type="document_upload",
            target_type="document",
            target_id="doc_pending",
            payload={"filename": "failed.txt"},
        )
        job_queue.claim_next()
        job_queue.fail(job.id, code="handler_failed", message="Document processing failed")

        response = client.post(f"/api/jobs/{job.id}/retry")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert body["attempts"] == 1
    finally:
        job_queue.clear()
