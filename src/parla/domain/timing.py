"""Overlapping timing deviation calculation — pure functions.

Implements the baseline-corrected cumulative deviation method from V9.
"""

from __future__ import annotations

from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def calculate_timing_deviations(
    user_offsets: Sequence[float],
    reference_offsets: Sequence[float],
    baseline_correction: bool = False,
) -> list[float]:
    """Calculate per-word timing deviation between user and reference.

    For overlapping mode (baseline_correction=False):
        deviation[i] = user[i] - ref[i]
        Even 0.3s of delay is significant since simultaneous speech is the goal.

    For shadowing mode (baseline_correction=True):
        d_raw[i] = user[i] - ref[i]
        baseline = median(d_raw)
        deviation[i] = d_raw[i] - baseline
        Natural shadowing delay is absorbed; only local deviations remain.
    """
    n = min(len(user_offsets), len(reference_offsets))
    if n == 0:
        return []

    raw = [user_offsets[i] - reference_offsets[i] for i in range(n)]

    if not baseline_correction:
        return raw

    base = median(raw)
    return [d - base for d in raw]
