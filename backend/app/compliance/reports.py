from __future__ import annotations

from collections import Counter
from typing import Iterable

from app.integrations.idempotency import list_delivery_receipts
from app.models import KycCase
from app.tenancy.service import tenant_registry


def access_review_report() -> dict[str, object]:
    tenants = tenant_registry.list_tenants()
    return {
        "report": "access_review",
        "tenant_count": len(tenants),
        "users": [
            {
                "tenant_id": tenant.tenant_id,
                "user_id": user.user_id,
                "role": user.role,
                "branch_code": user.branch_code,
                "status": user.status,
            }
            for tenant in tenants
            for user in tenant.users
        ],
        "status": "review_required" if any(tenant.users for tenant in tenants) else "no_users_configured",
    }


def audit_integrity_report(cases: Iterable[KycCase]) -> dict[str, object]:
    action_counts: Counter[str] = Counter()
    event_count = 0
    for case in cases:
        for event in case.audit_events:
            action_counts[event.action] += 1
            event_count += 1
    return {
        "report": "audit_integrity",
        "event_count": event_count,
        "action_counts": dict(sorted(action_counts.items())),
        "status": "available" if event_count else "empty",
    }


def export_delivery_report() -> dict[str, object]:
    receipts = list_delivery_receipts()
    return {
        "report": "export_delivery",
        "receipt_count": len(receipts),
        "queued": sum(1 for receipt in receipts if receipt.get("status") == "queued"),
        "failed": sum(1 for receipt in receipts if receipt.get("status") == "failed"),
        "receipts": receipts[-20:],
    }
