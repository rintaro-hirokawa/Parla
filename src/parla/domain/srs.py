"""SRS (Spaced Repetition System) interval calculation.

All parameters are configurable via SRSConfig.
Domain functions receive config as an argument — no hardcoded values.
"""

import math
from datetime import date, timedelta

from pydantic import BaseModel, Field


class SRSConfig(BaseModel, frozen=True):
    """SRS parameters — loaded from config file, immutable at runtime."""

    intervals: tuple[int, ...] = (0, 1, 3, 7, 14, 30, 60)
    confidence_multipliers: tuple[float, ...] = (1.0, 0.7, 0.4)
    timer_penalty_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    context_mastery_threshold: int = 3
    default_ease_factor: float = 1.0
    review_limit: int = 20


class SRSUpdate(BaseModel, frozen=True):
    """Result of an SRS calculation."""

    new_stage: int
    next_review_date: date
    new_ease_factor: float


def calculate_next_review(
    *,
    current_stage: int,
    correct: bool,
    hint_level: int,
    timer_ratio: float,
    ease_factor: float,
    today: date,
    config: SRSConfig,
) -> SRSUpdate:
    """Calculate next SRS state after a review attempt.

    Args:
        current_stage: Current SRS stage (0 to max_stage).
        correct: Whether the initial answer was correct.
        hint_level: Hint level used (0=none, 1=hint1, 2=hint2).
        timer_ratio: Fraction of timer consumed (0.0-1.0).
        ease_factor: Current ease factor for the item.
        today: Current date (injected for testability).
        config: SRS configuration parameters.
    """
    max_stage = len(config.intervals) - 1

    if not correct:
        new_stage = max(0, current_stage - 1)
        interval_days = config.intervals[new_stage]
        return SRSUpdate(
            new_stage=new_stage,
            next_review_date=today + timedelta(days=interval_days),
            new_ease_factor=ease_factor,
        )

    # Correct but too slow — don't advance
    if timer_ratio >= config.timer_penalty_threshold:
        interval_days = config.intervals[current_stage]
        return SRSUpdate(
            new_stage=current_stage,
            next_review_date=today + timedelta(days=interval_days),
            new_ease_factor=ease_factor,
        )

    # Correct and fast enough — advance
    new_stage = min(current_stage + 1, max_stage)
    confidence = config.confidence_multipliers[hint_level]
    raw_interval = config.intervals[new_stage] * ease_factor * confidence
    # Minimum 1 day for non-zero stages
    interval_days = max(1, math.ceil(raw_interval)) if new_stage > 0 else 0

    return SRSUpdate(
        new_stage=new_stage,
        next_review_date=today + timedelta(days=interval_days),
        new_ease_factor=ease_factor,
    )
