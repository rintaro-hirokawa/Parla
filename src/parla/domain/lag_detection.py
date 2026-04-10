"""Overlapping lag detection — domain types and pure functions.

Identifies delayed phrases from timing deviations, and defines
the result types for LLM-based cause estimation (LLM call #7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

# Smoothing window for timing deviation (V9-validated parameter)
_SMOOTHING_WINDOW = 3

# Default threshold from V9 verification
DEFAULT_DELAY_THRESHOLD_SEC = 0.3

EstimatedCause = Literal[
    "pronunciation_difficulty",
    "vocabulary_recall",
    "syntactic_complexity",
    "discourse_boundary",
]


class DelayedPhrase(BaseModel, frozen=True):
    """A contiguous region of words where the user lagged behind the model."""

    phrase: str
    word_indices: tuple[int, ...]
    avg_delay_sec: float
    max_delay_sec: float


class LagPoint(BaseModel, frozen=True):
    """LLM-analyzed lag point with cause estimation."""

    phrase: str
    delay_sec: float = Field(ge=0.0)
    estimated_cause: EstimatedCause
    suggestion: str


class LagDetectionResult(BaseModel, frozen=True):
    """Full result of overlapping lag detection (LLM call #7 output)."""

    lag_points: tuple[LagPoint, ...]
    overall_comment: str


# --- Pure functions ---


def _smooth(values: list[float], window: int = _SMOOTHING_WINDOW) -> list[float]:
    """Sliding-window average for smoothing timing deviations."""
    n = len(values)
    if n == 0 or window <= 1:
        return values
    half = window // 2
    return [
        sum(values[max(0, i - half) : min(n, i + half + 1)])
        / (min(n, i + half + 1) - max(0, i - half))
        for i in range(n)
    ]


def _find_delay_regions(
    smoothed: list[float],
    threshold: float,
) -> list[tuple[int, int]]:
    """Find contiguous regions where smoothed deviation exceeds threshold.

    Returns list of (start, end_exclusive) index pairs.
    """
    regions: list[tuple[int, int]] = []
    in_region = False
    start = 0
    for i, val in enumerate(smoothed):
        if val > threshold and not in_region:
            start = i
            in_region = True
        elif val <= threshold and in_region:
            regions.append((start, i))
            in_region = False
    if in_region:
        regions.append((start, len(smoothed)))
    return regions


def identify_delayed_phrases(
    words: Sequence[str],
    deviations: Sequence[float],
    threshold: float = DEFAULT_DELAY_THRESHOLD_SEC,
) -> list[DelayedPhrase]:
    """Identify delayed phrase regions from per-word timing deviations.

    Args:
        words: Reference word list (same length as deviations).
        deviations: Per-word timing deviation in seconds (positive = lagging).
        threshold: Deviation threshold for considering a word delayed.

    Returns:
        List of DelayedPhrase, each representing a contiguous delayed region.
    """
    n = min(len(words), len(deviations))
    if n == 0:
        return []

    smoothed = _smooth(list(deviations[:n]))
    regions = _find_delay_regions(smoothed, threshold)

    phrases: list[DelayedPhrase] = []
    for start, end in regions:
        region_deviations = smoothed[start:end]
        phrase_words = [words[i] for i in range(start, end)]
        phrases.append(
            DelayedPhrase(
                phrase=" ".join(phrase_words),
                word_indices=tuple(range(start, end)),
                avg_delay_sec=sum(region_deviations) / len(region_deviations),
                max_delay_sec=max(region_deviations),
            )
        )

    return phrases
