"""WPM calculation — pure functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from parla.domain.practice import PronunciationWord

CEFR_WPM_TARGETS: dict[str, int] = {
    "A2": 90,
    "B1": 110,
    "B2": 140,
    "C1": 180,
}


def calculate_speech_duration(words: Sequence[PronunciationWord]) -> float:
    """Calculate actual speech duration from Azure word timestamps.

    Uses the first recognized word's offset to the last recognized word's
    offset + duration. Omissions (offset < 0) are excluded.
    Returns 0.0 if no recognized words are found.
    """
    recognized = [w for w in words if w.offset_seconds >= 0]
    if not recognized:
        return 0.0
    first = min(recognized, key=lambda w: w.offset_seconds)
    last = max(recognized, key=lambda w: w.offset_seconds + w.duration_seconds)
    return last.offset_seconds + last.duration_seconds - first.offset_seconds


def calculate_wpm(word_count: int, duration_seconds: float) -> float:
    """Calculate words per minute from word count and duration."""
    if duration_seconds <= 0:
        return 0.0
    return word_count / duration_seconds * 60


def calculate_time_limit(word_count: int, cefr_level: str, buffer_ratio: float = 1.2) -> float:
    """Calculate time limit in seconds based on CEFR target WPM.

    Uses the CEFR target as the minimum WPM,
    then applies a buffer ratio for learner tolerance.
    """
    target_wpm = CEFR_WPM_TARGETS[cefr_level]
    base_seconds = word_count / target_wpm * 60
    return base_seconds * buffer_ratio
