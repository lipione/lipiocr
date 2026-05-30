from app.integrations.idempotency import build_idempotency_key, remember_delivery


def test_idempotency_key_is_stable_for_same_payload():
    payload = {"case_id": "case_1", "status": "approved"}

    first = build_idempotency_key(tenant_id="tenant-a", target="webhook", payload=payload)
    second = build_idempotency_key(tenant_id="tenant-a", target="webhook", payload={"status": "approved", "case_id": "case_1"})

    assert first == second


def test_delivery_receipt_is_returned_for_duplicate_key():
    key = build_idempotency_key(tenant_id="tenant-a", target="sftp", payload={"case_ids": ["case_1"]})

    created, first = remember_delivery(key, {"status": "queued"})
    duplicate, second = remember_delivery(key, {"status": "queued_again"})

    assert created is True
    assert duplicate is False
    assert second == first
