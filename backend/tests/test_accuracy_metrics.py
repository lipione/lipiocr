from pathlib import Path

from app.accuracy.dataset import load_benchmark_manifest
from app.accuracy.metrics import character_error_rate, field_classification, word_error_rate
from app.accuracy.report import build_benchmark_report


def test_text_error_rates_are_normalized():
    assert character_error_rate("Rudra Man Isuwa", "Rudra M Isuwa") > 0
    assert word_error_rate("Sita Sharma", "Sita Sharma") == 0


def test_field_precision_recall_and_f1():
    result = field_classification(
        {"name": "Sita Sharma", "citizenship_number": "27-01-78-12345"},
        {"name": "Sita Sharma", "extra": "noise"},
    )

    assert result.true_positive == 1
    assert result.false_positive == 1
    assert result.false_negative == 1
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.f1 == 0.5


def test_benchmark_report_breaks_down_printed_and_handwriting():
    dataset = load_benchmark_manifest(Path("tests/fixtures/accuracy/manifest.json"))
    report = build_benchmark_report(dataset)

    assert report["sample_count"] == 2
    assert "citizenship" in report["by_document_type"]
    assert "handwriting" in report["by_mode"]
    assert report["by_mode"]["handwriting"]["reviewer_correction_rate"] == 2
    assert report["by_field"]["full_name"]["precision"] == 1.0
