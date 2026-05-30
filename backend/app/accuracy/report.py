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
    by_language: dict[str, dict[str, int]] = defaultdict(lambda: {"expected": 0, "extracted": 0, "matched": 0, "reviewer_corrections": 0})
    by_field: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "expected": 0,
            "extracted": 0,
            "matched": 0,
            "cer_values": [],
            "confidences": [],
            "document_types": set(),
            "modes": set(),
            "languages": set(),
            "reviewer_corrections": 0,
        }
    )
    confidence_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"field_count": 0, "matched": 0})
    handwriting_sample_count = 0
    handwriting_field_count = 0
    nepali_handwriting_field_count = 0

    for sample, row in zip(dataset.samples, sample_rows):
        by_document[sample.document_type].append(row)
        by_mode[sample.mode].append(row)
        if sample.mode in {"handwriting", "mixed"}:
            handwriting_sample_count += 1
        for key, expected_value in sample.expected_fields.items():
            field_mode = sample.field_modes.get(key, sample.mode)
            field_language = sample.field_languages.get(key, sample.language)
            field_confidence = sample.field_confidences.get(key)
            counts = by_field[key]
            counts["expected"] = int(counts["expected"]) + 1
            counts["document_types"].add(sample.document_type)  # type: ignore[union-attr]
            counts["modes"].add(field_mode)  # type: ignore[union-attr]
            counts["languages"].add(field_language)  # type: ignore[union-attr]
            by_language[field_language]["expected"] += 1
            by_language[field_language]["reviewer_corrections"] += sample.reviewer_corrections
            if field_confidence is not None:
                counts["confidences"].append(field_confidence)  # type: ignore[union-attr]
            if field_mode in {"handwriting", "mixed"}:
                handwriting_field_count += 1
                if field_language == "ne":
                    nepali_handwriting_field_count += 1
            actual_value = sample.actual_fields.get(key)
            if actual_value is not None:
                counts["extracted"] = int(counts["extracted"]) + 1
                by_language[field_language]["extracted"] += 1
                cer = character_error_rate(expected_value, actual_value)
                counts["cer_values"].append(cer)  # type: ignore[union-attr]
                matched = cer <= 0.08
                if matched:
                    counts["matched"] = int(counts["matched"]) + 1
                    by_language[field_language]["matched"] += 1
                bucket = _confidence_bucket(field_confidence)
                confidence_buckets[bucket]["field_count"] += 1
                if matched:
                    confidence_buckets[bucket]["matched"] += 1
        for key in sample.actual_fields:
            if key not in sample.expected_fields:
                by_field[key]["extracted"] = int(by_field[key]["extracted"]) + 1

    by_field_report = {
        key: _field_report(key, counts)
        for key, counts in sorted(by_field.items())
    }
    weak_fields = sorted(
        [
            {
                "field_key": key,
                "f1": row["f1"],
                "recall": row["recall"],
                "average_character_error_rate": row["average_character_error_rate"],
                "expected": row["expected"],
            }
            for key, row in by_field_report.items()
            if row["expected"] and (float(row["f1"]) < 0.95 or float(row["average_character_error_rate"]) > 0.05)
        ],
        key=lambda item: (float(item["f1"]), -float(item["average_character_error_rate"]), str(item["field_key"])),
    )

    return {
        "name": dataset.name,
        "version": dataset.version,
        "sample_count": len(dataset.samples),
        "overall": _aggregate(sample_rows),
        "by_document_type": {key: _aggregate(rows) for key, rows in sorted(by_document.items())},
        "by_mode": {key: _aggregate(rows) for key, rows in sorted(by_mode.items())},
        "by_language": {key: _field_language_report(counts) for key, counts in sorted(by_language.items())},
        "by_field": by_field_report,
        "confidence_buckets": {
            key: {
                **counts,
                "precision": round(counts["matched"] / counts["field_count"], 4) if counts["field_count"] else 0.0,
            }
            for key, counts in sorted(confidence_buckets.items())
        },
        "handwriting": {
            "sample_count": handwriting_sample_count,
            "field_count": handwriting_field_count,
            "nepali_field_count": nepali_handwriting_field_count,
            "weak_fields": [
                item
                for item in weak_fields
                if "handwriting" in by_field_report[str(item["field_key"])]["modes"]
                or "mixed" in by_field_report[str(item["field_key"])]["modes"]
            ][:8],
        },
        "weak_fields": weak_fields[:12],
        "dataset_readiness": {
            "document_type_count": len(by_document),
            "handwriting_sample_count": handwriting_sample_count,
            "nepali_field_count": sum(
                1
                for sample in dataset.samples
                for key in sample.expected_fields
                if sample.field_languages.get(key, sample.language) == "ne"
            ),
            "status": "ready" if len(dataset.samples) >= 30 and handwriting_sample_count >= 5 else "pilot_dataset",
            "gaps": _dataset_gaps(len(dataset.samples), len(by_document), handwriting_sample_count),
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


def _field_report(key: str, counts: dict[str, object]) -> dict[str, object]:
    expected = int(counts["expected"])
    extracted = int(counts["extracted"])
    matched = int(counts["matched"])
    precision = round(matched / extracted, 4) if extracted else 0.0
    recall = round(matched / expected, 4) if expected else 0.0
    f1 = round((2 * precision * recall) / (precision + recall), 4) if precision + recall else 0.0
    return {
        "field_key": key,
        "expected": expected,
        "extracted": extracted,
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "average_character_error_rate": average(float(value) for value in counts["cer_values"]),  # type: ignore[index]
        "average_confidence": average(float(value) for value in counts["confidences"]),  # type: ignore[index]
        "document_types": sorted(counts["document_types"]),  # type: ignore[arg-type]
        "modes": sorted(counts["modes"]),  # type: ignore[arg-type]
        "languages": sorted(counts["languages"]),  # type: ignore[arg-type]
        "reviewer_corrections": int(counts["reviewer_corrections"]),
    }


def _field_language_report(counts: dict[str, int]) -> dict[str, object]:
    precision = round(counts["matched"] / counts["extracted"], 4) if counts["extracted"] else 0.0
    recall = round(counts["matched"] / counts["expected"], 4) if counts["expected"] else 0.0
    f1 = round((2 * precision * recall) / (precision + recall), 4) if precision + recall else 0.0
    return {
        "field_count": counts["expected"],
        "field_precision": precision,
        "field_recall": recall,
        "field_f1": f1,
        "reviewer_correction_rate": round(counts["reviewer_corrections"] / counts["expected"], 4) if counts["expected"] else 0.0,
    }


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.95:
        return "auto_accept"
    if confidence >= 0.8:
        return "reviewer_check"
    return "manual_entry"


def _dataset_gaps(sample_count: int, document_type_count: int, handwriting_sample_count: int) -> list[str]:
    gaps: list[str] = []
    if sample_count < 30:
        gaps.append("Collect at least 30 institution-approved benchmark samples before production claims.")
    if document_type_count < 3:
        gaps.append("Cover at least three Nepal financial document families.")
    if handwriting_sample_count < 5:
        gaps.append("Add Nepali handwriting samples before claiming handwriting performance.")
    return gaps


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
