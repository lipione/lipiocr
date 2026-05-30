from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.accuracy.dataset import BenchmarkDataset, BenchmarkSample
from app.accuracy.metrics import average, character_error_rate, field_classification, word_error_rate
from app.models import KycCase


def _sample_metrics(sample: BenchmarkSample) -> dict[str, object]:
    classification = field_classification(sample.expected_fields, sample.actual_fields)
    return {
        "sample_id": sample.sample_id,
        "document_type": sample.document_type,
        "mode": sample.mode,
        "character_error_rate": character_error_rate(sample.expected_text, sample.actual_text),
        "word_error_rate": word_error_rate(sample.expected_text, sample.actual_text),
        "field_precision": classification.precision,
        "field_recall": classification.recall,
        "field_f1": classification.f1,
        "reviewer_corrections": sample.reviewer_corrections,
    }


def build_benchmark_report(dataset: BenchmarkDataset) -> dict[str, object]:
    sample_rows = [_sample_metrics(sample) for sample in dataset.samples]
    by_document: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_mode: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_field: dict[str, dict[str, int]] = defaultdict(lambda: {"expected": 0, "extracted": 0, "matched": 0})

    for sample, row in zip(dataset.samples, sample_rows):
        by_document[sample.document_type].append(row)
        by_mode[sample.mode].append(row)
        for key, expected_value in sample.expected_fields.items():
            by_field[key]["expected"] += 1
            actual_value = sample.actual_fields.get(key)
            if actual_value is not None:
                by_field[key]["extracted"] += 1
                if character_error_rate(expected_value, actual_value) <= 0.08:
                    by_field[key]["matched"] += 1
        for key in sample.actual_fields:
            by_field[key]["extracted"] += 0

    return {
        "name": dataset.name,
        "version": dataset.version,
        "sample_count": len(dataset.samples),
        "overall": _aggregate(sample_rows),
        "by_document_type": {key: _aggregate(rows) for key, rows in sorted(by_document.items())},
        "by_mode": {key: _aggregate(rows) for key, rows in sorted(by_mode.items())},
        "by_field": {
            key: {
                "expected": counts["expected"],
                "extracted": counts["extracted"],
                "matched": counts["matched"],
                "precision": round(counts["matched"] / counts["extracted"], 4) if counts["extracted"] else 0.0,
                "recall": round(counts["matched"] / counts["expected"], 4) if counts["expected"] else 0.0,
            }
            for key, counts in sorted(by_field.items())
        },
        "samples": sample_rows,
    }


def _aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "character_error_rate": average(float(row["character_error_rate"]) for row in rows),
        "word_error_rate": average(float(row["word_error_rate"]) for row in rows),
        "field_precision": average(float(row["field_precision"]) for row in rows),
        "field_recall": average(float(row["field_recall"]) for row in rows),
        "field_f1": average(float(row["field_f1"]) for row in rows),
        "reviewer_correction_rate": round(
            sum(int(row["reviewer_corrections"]) for row in rows) / len(rows), 4
        )
        if rows
        else 0.0,
    }


def dataset_from_cases(cases: Iterable[KycCase]) -> BenchmarkDataset:
    samples: list[BenchmarkSample] = []
    for case in cases:
        for document in case.documents:
            fields = {
                field.key: field.value
                for field in case.extracted_fields
                if (field.document_id or field.evidence.document_id) == document.id
            }
            text = "\n".join(block.text for page in document.pages for block in page.blocks)
            corrections = sum(1 for event in case.audit_events if event.action == "field_correction_recorded")
            mode = "handwriting" if any(block.block_type == "handwriting" for page in document.pages for block in page.blocks) else "printed"
            samples.append(
                BenchmarkSample(
                    sample_id=document.id,
                    document_type=document.document_type.value,
                    mode=mode,
                    expected_text=text,
                    actual_text=text,
                    expected_fields=fields,
                    actual_fields=fields,
                    reviewer_corrections=corrections,
                )
            )
    return BenchmarkDataset(samples=samples)
