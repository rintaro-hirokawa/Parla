"""Difflib-based similarity judgment for Phase C evaluation — pure functions."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class MiscueWord:
    """Word with miscue detection result from difflib post-processing."""

    word: str
    error_type: str  # "equal" | "Omission" | "Insertion"


def calculate_similarity(reference: str, recognized: str) -> float:
    """Calculate word-level similarity between reference and recognized text.

    Uses difflib.SequenceMatcher ratio after lowercasing and tokenizing.
    """
    ref_words = reference.lower().split()
    rec_words = recognized.lower().split()
    if not ref_words and not rec_words:
        return 1.0
    if not ref_words or not rec_words:
        return 0.0
    return difflib.SequenceMatcher(None, ref_words, rec_words).ratio()


def judge_sentence_status(similarity: float, omission_ratio: float) -> str:
    """Judge a single sentence's status based on similarity and omission ratio.

    Returns: "correct" | "paraphrase" | "error"
    Rules (from 12-evaluation-criteria.md):
      - omission_ratio > 0.50 → error (regardless of similarity)
      - similarity >= 0.90 → correct
      - similarity >= 0.50 → paraphrase
      - similarity < 0.50 → error
    """
    if omission_ratio > 0.50:
        return "error"
    if similarity >= 0.90:
        return "correct"
    if similarity >= 0.50:
        return "paraphrase"
    return "error"


def judge_passage(statuses: Sequence[str]) -> bool:
    """Judge overall passage pass/fail. All sentences must be correct or paraphrase."""
    return all(s in ("correct", "paraphrase") for s in statuses)


def apply_miscue_detection(
    reference_words: Sequence[str],
    recognized_words: Sequence[str],
) -> list[MiscueWord]:
    """Detect Omission/Insertion using difflib SequenceMatcher.

    Compares reference_words against recognized_words (case-insensitive,
    punctuation-stripped). Returns a list of MiscueWord with error_type
    indicating whether each word was matched, omitted, or inserted.
    """
    ref_normalized = [w.lower().strip(".,!?;:") for w in reference_words]
    rec_normalized = [w.lower().strip(".,!?;:") for w in recognized_words]

    diff = difflib.SequenceMatcher(None, ref_normalized, rec_normalized)
    result: list[MiscueWord] = []

    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for idx in range(i1, i2):
                result.append(MiscueWord(word=reference_words[idx], error_type="equal"))
        elif tag == "delete":
            for idx in range(i1, i2):
                result.append(MiscueWord(word=reference_words[idx], error_type="Omission"))
        elif tag == "insert":
            for idx in range(j1, j2):
                result.append(MiscueWord(word=recognized_words[idx], error_type="Insertion"))
        elif tag == "replace":
            for idx in range(i1, i2):
                result.append(MiscueWord(word=reference_words[idx], error_type="Omission"))
            for idx in range(j1, j2):
                result.append(MiscueWord(word=recognized_words[idx], error_type="Insertion"))

    return result
