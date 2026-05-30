from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BenchmarkSample(BaseModel):
    sample_id: str
    document_type: str
    mode: Literal["printed", "handwriting", "mixed"] = "printed"
    expected_text: str = ""
    actual_text: str = ""
    expected_fields: Dict[str, str] = Field(default_factory=dict)
    actual_fields: Dict[str, str] = Field(default_factory=dict)
    reviewer_corrections: int = 0


class BenchmarkDataset(BaseModel):
    name: str = "LipiOCR Nepal Financial Document Benchmark"
    version: str = "1"
    samples: List[BenchmarkSample] = Field(default_factory=list)


def load_benchmark_manifest(path: str | Path) -> BenchmarkDataset:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return BenchmarkDataset.model_validate(payload)


def default_manifest_path() -> Optional[Path]:
    path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "accuracy" / "manifest.json"
    return path if path.exists() else None
