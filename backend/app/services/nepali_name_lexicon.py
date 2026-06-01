from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.config import get_settings
from app.services.calendar_intelligence import normalize_nepali_digits


DEVANAGARI_TEXT_RE = re.compile(r"[\u0900-\u097F]")
SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "nepali_name_lexicon_seed.json"

TRANSLITERATION_OVERRIDES = {
    "रुद्रमान": "rudra man",
    "रुद्र": "rudra",
    "मान": "man",
    "इसुवा": "isuwa",
    "सीता": "sita",
    "शर्मा": "sharma",
    "माया": "maya",
    "लामा": "lama",
    "राजेश": "rajesh",
    "कार्की": "karki",
    "काकी": "kaki",
    "किरण": "kiran",
    "घले": "ghale",
    "प्रसाद": "prasad",
    "थापा": "thapa",
    "शेर्पा": "sherpa",
    "गुरुङ": "gurung",
    "गुरुंग": "gurung",
    "तामाङ": "tamang",
    "तामाङ्ग": "tamang",
}

DEVANAGARI_VOWELS = {
    "अ": "a",
    "आ": "a",
    "इ": "i",
    "ई": "i",
    "उ": "u",
    "ऊ": "u",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
}

DEVANAGARI_CONSONANTS = {
    "क": "k",
    "ख": "kh",
    "ग": "g",
    "घ": "gh",
    "ङ": "ng",
    "च": "ch",
    "छ": "chh",
    "ज": "j",
    "झ": "jh",
    "ञ": "ny",
    "ट": "t",
    "ठ": "th",
    "ड": "d",
    "ढ": "dh",
    "ण": "n",
    "त": "t",
    "थ": "th",
    "द": "d",
    "ध": "dh",
    "न": "n",
    "प": "p",
    "फ": "ph",
    "ब": "b",
    "भ": "bh",
    "म": "m",
    "य": "y",
    "र": "r",
    "ल": "l",
    "व": "w",
    "श": "sh",
    "ष": "sh",
    "स": "s",
    "ह": "h",
}

DEVANAGARI_MATRAS = {
    "ा": "a",
    "ि": "i",
    "ी": "i",
    "ु": "u",
    "ू": "u",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
}


@dataclass(frozen=True)
class NameTokenEntry:
    token_np: str
    roman: str
    count: int = 1


@dataclass
class NameLexicon:
    token_entries: dict[str, NameTokenEntry] = field(default_factory=dict)
    token_counts: Counter[str] = field(default_factory=Counter)
    full_name_counts: Counter[str] = field(default_factory=Counter)

    @classmethod
    def from_nepali_names(cls, names: Iterable[str]) -> "NameLexicon":
        lexicon = cls()
        for raw_name in names:
            lexicon.add_name(raw_name)
        return lexicon

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "NameLexicon":
        lexicon = cls()
        for item in payload.get("names", []):
            if isinstance(item, str):
                lexicon.add_name(item)
                continue
            if isinstance(item, dict):
                lexicon.add_name(str(item.get("name_np") or item.get("name") or ""), int(item.get("count") or 1))
        for item in payload.get("tokens", []):
            if not isinstance(item, dict):
                continue
            token_np = str(item.get("token_np") or item.get("token") or "").strip()
            roman = normalize_roman_name(str(item.get("roman") or transliterate_nepali(token_np)))
            count = int(item.get("count") or 1)
            if token_np and roman:
                lexicon._add_token(token_np, roman, count)
        return lexicon

    def add_name(self, name_np: str, count: int = 1) -> None:
        normalized_name = normalize_nepali_name(name_np)
        if not normalized_name:
            return
        self.full_name_counts[normalized_name] += count
        for token_np in normalized_name.split():
            roman = roman_display_token(token_np)
            if roman:
                self._add_token(token_np, roman, count)

    def _add_token(self, token_np: str, roman: str, count: int) -> None:
        existing = self.token_entries.get(roman)
        if existing is None or count > existing.count:
            self.token_entries[roman] = NameTokenEntry(token_np=token_np, roman=roman, count=count)
        self.token_counts[roman] += count

    def suggest(self, value: str, *, counterpart: str = "", field_key: str = "", limit: int = 5) -> list[dict[str, object]]:
        normalized_value = normalize_roman_name(value) if not DEVANAGARI_TEXT_RE.search(value) else transliterate_nepali(value)
        tokens = [token for token in normalized_value.split() if token]
        if not tokens:
            return []

        counterpart_tokens = (
            [token for token in transliterate_nepali(counterpart).split() if token]
            if counterpart and DEVANAGARI_TEXT_RE.search(counterpart)
            else [token for token in normalize_roman_name(counterpart).split() if token]
        )
        phrase_candidates: list[dict[str, object]] = []
        proposed_tokens = tokens[:]
        changed_tokens: list[dict[str, object]] = []
        sources: set[str] = set()

        for index, token in enumerate(tokens):
            replacement = self._best_token_candidate(token, counterpart_tokens[index] if index < len(counterpart_tokens) else "")
            if replacement is None or replacement["suggested_roman"] == token:
                continue
            proposed_tokens[index] = str(replacement["suggested_roman"])
            changed_tokens.append(replacement)
            sources.update(str(source) for source in replacement["sources"])

        if not changed_tokens:
            return []

        suggested_value = _format_suggested_name(proposed_tokens, prefer_nepali=DEVANAGARI_TEXT_RE.search(value), lexicon=self)
        confidence = _candidate_confidence(changed_tokens, has_counterpart="bilingual_pair" in sources)
        phrase_candidates.append(
            {
                "field_key": field_key,
                "original_value": value,
                "suggested_value": suggested_value,
                "confidence": confidence,
                "status": "suggested",
                "sources": sorted(sources),
                "candidate_tokens": changed_tokens,
                "audit_reason": (
                    "Suggested from Nepali name lexicon"
                    + (" and bilingual Nepali/English field pairing." if "bilingual_pair" in sources else ".")
                ),
            }
        )
        return sorted(phrase_candidates, key=lambda item: float(item["confidence"]), reverse=True)[:limit]

    def _best_token_candidate(self, token: str, counterpart_token: str = "") -> Optional[dict[str, object]]:
        candidates: list[tuple[float, dict[str, object]]] = []
        if counterpart_token and counterpart_token != token and _levenshtein_distance(token, counterpart_token) <= 2:
            entry = self.token_entries.get(counterpart_token)
            if entry:
                candidates.append(
                    (
                        1.0,
                        {
                            "original": token,
                            "suggested_roman": counterpart_token,
                            "suggested_nepali": entry.token_np,
                            "distance": _levenshtein_distance(token, counterpart_token),
                            "frequency": self.token_counts[counterpart_token],
                            "sources": ["bilingual_pair", "nepali_name_lexicon"],
                        },
                    )
                )

        first_char = token[:1]
        for roman, entry in self.token_entries.items():
            if first_char and roman[:1] != first_char:
                continue
            distance = _levenshtein_distance(token, roman)
            if distance > 1:
                continue
            frequency = self.token_counts[roman]
            score = (0.90 - distance * 0.08) + min(0.08, frequency / max(sum(self.token_counts.values()), 1))
            candidates.append(
                (
                    score,
                    {
                        "original": token,
                        "suggested_roman": roman,
                        "suggested_nepali": entry.token_np,
                        "distance": distance,
                        "frequency": frequency,
                        "sources": ["nepali_name_lexicon"],
                    },
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], -int(item[1]["frequency"]), str(item[1]["suggested_roman"])))
        return candidates[0][1]


def normalize_nepali_name(value: str) -> str:
    normalized = normalize_nepali_digits(value)
    normalized = re.sub(r"[^\u0900-\u097F\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_roman_name(value: str) -> str:
    normalized = normalize_nepali_digits(value).lower()
    normalized = normalized.replace(".", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.replace("w", "v")


def _strip_inherent_vowel(buffer: list[str]) -> None:
    if buffer and buffer[-1].endswith("a"):
        buffer[-1] = buffer[-1][:-1]


def _transliterate_devanagari_token(token: str) -> str:
    buffer: list[str] = []
    for char in token:
        if char in DEVANAGARI_CONSONANTS:
            buffer.append(f"{DEVANAGARI_CONSONANTS[char]}a")
        elif char in DEVANAGARI_MATRAS:
            _strip_inherent_vowel(buffer)
            buffer.append(DEVANAGARI_MATRAS[char])
        elif char == "्":
            _strip_inherent_vowel(buffer)
        elif char in DEVANAGARI_VOWELS:
            buffer.append(DEVANAGARI_VOWELS[char])
        elif char in {"ं", "ँ"}:
            buffer.append("n")
        elif char == "ः":
            buffer.append("h")
        elif char.strip():
            buffer.append(char)
    return "".join(buffer)


def roman_display_token(token_np: str) -> str:
    roman = TRANSLITERATION_OVERRIDES.get(token_np, _transliterate_devanagari_token(token_np))
    roman = normalize_roman_name(roman)
    if len(roman) > 3 and roman.endswith("a") and not roman.endswith(("ya", "pa")):
        roman = roman[:-1]
    return roman


def transliterate_nepali(value: str) -> str:
    tokens = re.split(r"(\s+)", normalize_nepali_name(value))
    converted = [roman_display_token(token) if token.strip() else token for token in tokens]
    return normalize_roman_name("".join(converted))


def _format_suggested_name(tokens: list[str], *, prefer_nepali: bool, lexicon: NameLexicon) -> str:
    if prefer_nepali:
        return " ".join(lexicon.token_entries.get(token, NameTokenEntry(token, token)).token_np for token in tokens)
    return " ".join(token.capitalize() for token in tokens)


def _candidate_confidence(changed_tokens: list[dict[str, object]], *, has_counterpart: bool) -> float:
    if not changed_tokens:
        return 0.0
    max_distance = max(int(token.get("distance") or 0) for token in changed_tokens)
    confidence = 0.86 if max_distance <= 1 else 0.78
    if has_counterpart:
        confidence += 0.08
    return round(min(0.96, confidence), 2)


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[right_index - 1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _payload_from_path(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def name_lexicon() -> NameLexicon:
    settings = get_settings()
    configured_path = Path(settings.nepali_name_lexicon_path)
    payload = _payload_from_path(configured_path) or _payload_from_path(SEED_PATH) or {"names": []}
    return NameLexicon.from_payload(payload)


def suggest_name_corrections(value: str, *, counterpart: str = "", field_key: str = "", limit: int = 5) -> list[dict[str, object]]:
    return name_lexicon().suggest(value, counterpart=counterpart, field_key=field_key, limit=limit)
