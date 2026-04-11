"""Error-rate-based pass/fail judgment for Phase C evaluation — pure functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from parla.ports.pronunciation_assessment import ErrorType

#: Maximum ratio of error words (Mispronunciation + Omission) allowed to pass.
ERROR_RATE_THRESHOLD: float = 0.15


def calculate_error_rate(
    error_types: Sequence[ErrorType],
) -> float:
    """Calculate ratio of error words (Mispronunciation/Omission) excluding Insertions.

    Insertions are excluded from both numerator and denominator because they
    represent extra words not in the reference text.
    """
    ref_aligned = [e for e in error_types if e != "Insertion"]
    if not ref_aligned:
        return 0.0
    error_count = sum(1 for e in ref_aligned if e in ("Mispronunciation", "Omission"))
    return error_count / len(ref_aligned)


def judge_passed(error_types: Sequence[ErrorType]) -> bool:
    """Judge overall pass/fail based on error rate threshold."""
    return calculate_error_rate(error_types) < ERROR_RATE_THRESHOLD
