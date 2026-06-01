from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Iterable

from app.accuracy.dataset import load_active_benchmark_dataset
from app.accuracy.report import build_benchmark_report, dataset_from_cases
from app.models import AuditEvent, KycCase
from app.services.document_intelligence import build_correction_memory


def record_correction(case: KycCase, payload: Dict[str, object]) -> Dict[str, object]:
    correction = {
        "correction_id": f"corr_{len([e for e in case.audit_events if e.action == 'field_correction_recorded']) + 1:04d}",
        "case_id": case.id,
        "field_key": str(payload.get("field_key") or ""),
        "old_value": str(payload.get("old_value") or ""),
        "new_value": str(payload.get("new_value") or ""),
        "corrected_by": str(payload.get("corrected_by") or "reviewer"),
        "document_type": str(payload.get("document_type") or "unknown"),
        "document_variant": str(payload.get("document_variant") or f"{payload.get('document_type') or 'unknown'}_unclassified_variant"),
        "block_type": str(payload.get("block_type") or ""),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    for field in case.extracted_fields:
        if field.key == correction["field_key"]:
            field.value = correction["new_value"]
            field.confidence = 1.0
            field.extracted_by = "reviewer"
            field.source = "reviewer_correction"
            break
    case.audit_events.append(
        AuditEvent(
            action="field_correction_recorded",
            actor=correction["corrected_by"],
            note=f"{correction['field_key']} corrected",
            metadata=correction,
        )
    )
    return {"correction": correction, "case": case}


def build_accuracy_analytics(cases: Iterable[KycCase]) -> Dict[str, object]:
    cases_list = list(cases)
    corrections = []
    field_counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()
    confidence_totals: defaultdict[str, float] = defaultdict(float)
    confidence_counts: Counter[str] = Counter()
    for case in cases_list:
        for field in case.extracted_fields:
            field_counts[field.key] += 0
            confidence_totals[field.key] += field.confidence
            confidence_counts[field.key] += 1
        for document in case.documents:
            document_counts[document.document_type.value] += 0
        for event in case.audit_events:
            if event.action == "field_correction_recorded":
                correction = event.metadata
                corrections.append(correction)
                field_counts[str(correction.get("field_key") or "unknown")] += 1
                document_counts[str(correction.get("document_type") or "unknown")] += 1

    field_accuracy = {}
    for field_key in set(field_counts) | set(confidence_counts):
        count = field_counts[field_key]
        observed = confidence_counts[field_key]
        avg_conf = round(confidence_totals[field_key] / observed, 2) if observed else 0.0
        field_accuracy[field_key] = {
            "corrections": count,
            "observed": observed,
            "average_confidence": avg_conf,
            "estimated_accuracy": max(0.0, round(1 - (count / max(observed, 1)), 2)),
        }

    document_type_performance = {
        document_type: {
            "corrections": count,
            "status": "needs_attention" if count else "stable",
        }
        for document_type, count in document_counts.items()
    }
    benchmark_dataset = load_active_benchmark_dataset()
    if not benchmark_dataset.samples:
        benchmark_dataset = dataset_from_cases(cases_list)

    return {
        "correction_count": len(corrections),
        "field_accuracy": field_accuracy,
        "document_type_performance": document_type_performance,
        "benchmark": build_benchmark_report(benchmark_dataset),
        "confidence_drift": [
            {
                "field_key": field_key,
                "average_confidence": field_accuracy[field_key]["average_confidence"],
                "corrections": field_accuracy[field_key]["corrections"],
            }
            for field_key in sorted(field_accuracy)
        ],
        "recent_corrections": corrections[-10:],
        "correction_memory": build_correction_memory(cases_list),
    }
