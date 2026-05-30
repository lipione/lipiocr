from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def levenshtein_distance(expected: str, actual: str) -> int:
    left = _normalize_text(expected)
    right = _normalize_text(actual)
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current.append(min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def character_error_rate(expected: str, actual: str) -> float:
    normalized = _normalize_text(expected)
    if not normalized:
        return 0.0 if not _normalize_text(actual) else 1.0
    return round(levenshtein_distance(expected, actual) / len(normalized), 4)


def word_error_rate(expected: str, actual: str) -> float:
    expected_words = _normalize_text(expected).split()
    actual_words = _normalize_text(actual).split()
    if not expected_words:
        return 0.0 if not actual_words else 1.0
    return round(_sequence_distance(expected_words, actual_words) / len(expected_words), 4)


def _sequence_distance(expected: list[str], actual: list[str]) -> int:
    previous = list(range(len(actual) + 1))
    for i, left_word in enumerate(expected, start=1):
        current = [i]
        for j, right_word in enumerate(actual, start=1):
            cost = 0 if left_word == right_word else 1
            current.append(min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class FieldClassification:
    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return round(self.true_positive / denominator, 4) if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return round(self.true_positive / denominator, 4) if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return round((2 * self.precision * self.recall) / denominator, 4) if denominator else 0.0


def field_classification(
    expected: Mapping[str, str],
    actual: Mapping[str, str],
    *,
    match_threshold: float = 0.92,
) -> FieldClassification:
    true_positive = 0
    false_positive = 0
    false_negative = 0

    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value is None:
            false_negative += 1
            continue
        similarity = 1 - character_error_rate(expected_value, actual_value)
        if similarity >= match_threshold:
            true_positive += 1
        else:
            false_positive += 1
            false_negative += 1

    for key in actual:
        if key not in expected:
            false_positive += 1

    return FieldClassification(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
    )


def average(values: Iterable[float]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 4) if items else 0.0
