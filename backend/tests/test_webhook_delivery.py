from fastapi.testclient import TestClient

from app.integrations.webhook_delivery import create_webhook_delivery, sign_payload
from app.main import app


client = TestClient(app)


def test_webhook_payload_is_signed_and_idempotent():
    payload = {"case_id": "case_1", "status": "approved"}
    first = create_webhook_delivery(
        tenant_id="tenant-a",
        url="https://bank.example/webhook",
        event="case.approved",
        payload=payload,
        secret="secret",
    )
    second = create_webhook_delivery(
        tenant_id="tenant-a",
        url="https://bank.example/webhook",
        event="case.approved",
        payload=payload,
        secret="secret",
    )

    assert first["signature"] == sign_payload(payload, "secret")
    assert first["idempotency_key"] == second["idempotency_key"]
    assert second["duplicate"] is True


def test_webhook_and_sftp_delivery_receipts_are_visible():
    webhook = client.post(
        "/api/integrations/webhooks/deliver",
        json={
            "tenant_id": "tenant-a",
            "url": "https://bank.example/webhook",
            "event": "case.approved",
            "payload": {"case_id": "case_2"},
            "secret": "secret",
        },
    )
    sftp = client.post(
        "/api/integrations/sftp/batch",
        json={"tenant_id": "tenant-a", "target": "sftp://bank/drop", "profile_key": "cbs_standard", "case_ids": ["case_2"]},
    )
    operations = client.get("/api/integrations/operations")

    assert webhook.status_code == 202
    assert sftp.status_code == 202
    assert operations.status_code == 200
    assert any(receipt.get("mode") == "webhook" for receipt in operations.json()["delivery_receipts"])
    assert any(receipt.get("mode") == "sftp" for receipt in operations.json()["delivery_receipts"])
