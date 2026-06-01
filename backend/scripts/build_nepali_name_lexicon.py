#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.nepali_name_lexicon import normalize_nepali_name, roman_display_token  # noqa: E402


def build_lexicon(
    csv_path: Path,
    output_path: Path,
    *,
    name_column: str,
    gender_column: str,
    max_names: int,
    max_tokens: int,
) -> None:
    full_names: Counter[str] = Counter()
    token_counts: Counter[str] = Counter()
    token_np_by_roman: dict[str, Counter[str]] = {}
    gender_counts: Counter[str] = Counter()
    row_count = 0

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if name_column not in (reader.fieldnames or []):
            raise SystemExit(f"Missing name column '{name_column}'. Available columns: {reader.fieldnames}")
        for row in reader:
            row_count += 1
            name_np = normalize_nepali_name(row.get(name_column, ""))
            if not name_np:
                continue
            full_names[name_np] += 1
            gender = str(row.get(gender_column) or "").strip()
            if gender:
                gender_counts[gender] += 1
            for token_np in name_np.split():
                roman = roman_display_token(token_np)
                if not roman:
                    continue
                token_counts[roman] += 1
                token_np_by_roman.setdefault(roman, Counter())[token_np] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "source": str(csv_path),
            "source_format": "Nepali-only voter name CSV",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows_read": row_count,
            "unique_names": len(full_names),
            "unique_tokens": len(token_counts),
            "max_names": max_names,
            "max_tokens": max_tokens,
            "gender_counts": dict(gender_counts),
        },
        "names": [
            {"name_np": name, "count": count}
            for name, count in full_names.most_common(max_names)
        ],
        "tokens": [
            {
                "roman": roman,
                "token_np": token_np_by_roman[roman].most_common(1)[0][0],
                "count": count,
            }
            for roman, count in token_counts.most_common(max_tokens)
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact LipiOCR Nepali name lexicon from a Nepali-only CSV.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "storage" / "name-lexicon" / "nepali_name_lexicon.json",
    )
    parser.add_argument("--name-column", default="voter_name")
    parser.add_argument("--gender-column", default="voter_gender")
    parser.add_argument("--max-names", type=int, default=250_000)
    parser.add_argument("--max-tokens", type=int, default=75_000)
    args = parser.parse_args()
    build_lexicon(
        args.csv_path,
        args.output,
        name_column=args.name_column,
        gender_column=args.gender_column,
        max_names=args.max_names,
        max_tokens=args.max_tokens,
    )
    print(f"Wrote compact Nepali name lexicon to {args.output}")


if __name__ == "__main__":
    main()
