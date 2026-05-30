from pathlib import Path

from app.accuracy.dataset import BenchmarkDataset, BenchmarkSample, load_benchmark_manifest
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


def test_benchmark_report_tracks_language_handwriting_confidence_and_weak_fields():
    dataset = BenchmarkDataset(
        samples=[
            BenchmarkSample(
                sample_id="citizenship-handwriting-ne-001",
                document_type="citizenship",
                mode="handwriting",
                language="ne",
                expected_fields={
                    "name_ne": "रुद्रमान इसुवा",
                    "citizenship_number": "२७१०६०",
                },
                actual_fields={
                    "name_ne": "रुद्र इसुवा",
                    "citizenship_number": "२७१०६०",
                },
                field_modes={"name_ne": "handwriting", "citizenship_number": "printed"},
                field_languages={"name_ne": "ne", "citizenship_number": "ne"},
                field_confidences={"name_ne": 0.72, "citizenship_number": 0.97},
                reviewer_corrections=1,
            ),
            BenchmarkSample(
                sample_id="asba-printed-en-001",
                document_type="asba_application",
                mode="printed",
                language="en",
                expected_fields={"full_name_en": "Rudra Man Isuwa"},
                actual_fields={"full_name_en": "Rudra Man Isuwa"},
                field_modes={"full_name_en": "printed"},
                field_languages={"full_name_en": "en"},
                field_confidences={"full_name_en": 0.94},
            ),
        ]
    )

    report = build_benchmark_report(dataset)

    assert report["by_language"]["ne"]["field_count"] == 2
    assert report["handwriting"]["sample_count"] == 1
    assert report["handwriting"]["nepali_field_count"] == 1
    assert report["confidence_buckets"]["manual_entry"]["field_count"] == 1
    assert report["by_field"]["name_ne"]["f1"] == 0.0
    assert report["weak_fields"][0]["field_key"] == "name_ne"
