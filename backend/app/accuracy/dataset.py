from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings


class BenchmarkSample(BaseModel):
    sample_id: str
    document_type: str
    mode: Literal["printed", "handwriting", "mixed"] = "printed"
    language: Literal["ne", "en", "mixed"] = "mixed"
    approved_reference: Optional[str] = None
    expected_text: str = ""
    actual_text: str = ""
    expected_fields: Dict[str, str] = Field(default_factory=dict)
    actual_fields: Dict[str, str] = Field(default_factory=dict)
    field_modes: Dict[str, Literal["printed", "handwriting", "mixed"]] = Field(default_factory=dict)
    field_languages: Dict[str, Literal["ne", "en", "mixed"]] = Field(default_factory=dict)
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    reviewer_corrections: int = 0


class BenchmarkDataset(BaseModel):
    name: str = "LipiOCR Nepal Financial Document Benchmark"
    version: str = "1"
    samples: List[BenchmarkSample] = Field(default_factory=list)


def load_benchmark_manifest(path: str | Path) -> BenchmarkDataset:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return BenchmarkDataset.model_validate(payload)


def save_benchmark_manifest(path: str | Path, dataset: BenchmarkDataset) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def default_manifest_path() -> Optional[Path]:
    path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "accuracy" / "manifest.json"
    return path if path.exists() else None


def active_manifest_path(settings: Settings | None = None) -> Optional[Path]:
    active_settings = settings or get_settings()
    if active_settings.benchmark_manifest_path:
        configured = Path(active_settings.benchmark_manifest_path)
        return configured if configured.exists() else configured
    store_path = Path(active_settings.upload_dir) / "_accuracy_benchmark_manifest.json"
    if store_path.exists():
        return store_path
    return default_manifest_path()


def load_active_benchmark_dataset(settings: Settings | None = None) -> BenchmarkDataset:
    path = active_manifest_path(settings)
    if path and path.exists():
        return load_benchmark_manifest(path)
    return BenchmarkDataset()


def append_benchmark_sample(sample: BenchmarkSample, settings: Settings | None = None) -> BenchmarkDataset:
    active_settings = settings or get_settings()
    path = active_manifest_path(active_settings) or (Path(active_settings.upload_dir) / "_accuracy_benchmark_manifest.json")
    dataset = load_benchmark_manifest(path) if path.exists() else BenchmarkDataset()
    dataset.samples = [existing for existing in dataset.samples if existing.sample_id != sample.sample_id]
    dataset.samples.append(sample)
    save_benchmark_manifest(path, dataset)
    return dataset
