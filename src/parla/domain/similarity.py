"""Difflib-based similarity judgment for Phase C evaluation — pure functions."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

SentenceJudgment = Literal["correct", "paraphrase", "error"]


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


def judge_sentence_status(similarity: float, omission_ratio: float) -> SentenceJudgment:
    """Judge a single sentence's status based on similarity and omission ratio.

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
