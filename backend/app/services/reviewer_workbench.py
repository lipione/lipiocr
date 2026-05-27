from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.models import AuditEvent, CaseStatus, KycCase


def _metadata_events(case: KycCase, action: str) -> List[Dict[str, object]]:
    return [event.metadata for event in case.audit_events if event.action == action]


def assign_case(case: KycCase, payload: Dict[str, object]) -> Dict[str, object]:
    assignment = {
        "reviewer": str(payload.get("reviewer") or "unassigned"),
        "queue": str(payload.get("queue") or "standard_kyc"),
        "priority": str(payload.get("priority") or "normal"),
        "assigned_at": datetime.utcnow().isoformat() + "Z",
    }
    case.review.reviewer = assignment["reviewer"]
    case.audit_events.append(
        AuditEvent(
            action="case_assigned",
            actor=str(payload.get("actor") or "workflow"),
            note=f"Assigned to {assignment['reviewer']}",
            metadata=assignment,
        )
    )
    return {"case_id": case.id, "assignment": assignment, "case": case}


def add_comment(case: KycCase, payload: Dict[str, object]) -> Dict[str, object]:
    comment = {
        "comment_id": f"comment_{len(_metadata_events(case, 'review_comment_added')) + 1:04d}",
        "author": str(payload.get("author") or "reviewer"),
        "message": str(payload.get("message") or ""),
        "field_key": payload.get("field_key"),
        "visibility": str(payload.get("visibility") or "internal"),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    case.audit_events.append(
        AuditEvent(
            action="review_comment_added",
            actor=comment["author"],
            note=comment["message"],
            metadata=comment,
        )
    )
    return {"case_id": case.id, "comment": comment}


def request_rework(case: KycCase, payload: Dict[str, object]) -> KycCase:
    rework = {
        "request_id": f"rework_{len(_metadata_events(case, 'rework_requested')) + 1:04d}",
        "requester": str(payload.get("requester") or "checker"),
        "reason": str(payload.get("reason") or "Rework requested"),
        "fields": list(payload.get("fields") or []),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "open",
    }
    case.status = CaseStatus.review_required
    case.audit_events.append(
        AuditEvent(action="rework_requested", actor=rework["requester"], note=rework["reason"], metadata=rework)
    )
    return case


def build_workbench(case: KycCase) -> Dict[str, object]:
    assignment_events = _metadata_events(case, "case_assigned")
    assignment = assignment_events[-1] if assignment_events else {
        "reviewer": case.review.reviewer or "unassigned",
        "queue": "standard_kyc",
        "priority": case.risk_level.value,
    }
    comments = _metadata_events(case, "review_comment_added")
    rework_requests = _metadata_events(case, "rework_requested")
    corrections = _metadata_events(case, "field_correction_recorded")
    approval_history = [
        {
            "action": event.action,
            "actor": event.actor,
            "note": event.note,
            "created_at": event.created_at.isoformat() + "Z",
        }
        for event in case.audit_events
        if event.action in {"review_saved", "case_approved", "case_rejected", "rework_requested"}
    ]
    evidence_crops = [
        {
            "field_key": field.key,
            "document_id": field.document_id,
            "source_page": field.evidence.source_page,
            "bbox": field.bbox or field.evidence.bbox or [80, 100, 920, 134],
            "evidence_text": field.evidence.evidence_text,
            "crop_uri": field.evidence.image_crop_uri or f"crop://{case.id}/{field.key}",
        }
        for field in case.extracted_fields
    ]
    return {
        "case_id": case.id,
        "assignment": assignment,
        "comments": comments,
        "rework_requests": rework_requests,
        "field_corrections": corrections,
        "approval_history": approval_history,
        "evidence_crops": evidence_crops,
        "editable_fields": case.extracted_fields,
    }
