"""Run-through state seeder — skip recording/feedback and start directly at run-through."""

from __future__ import annotations

from typing import TYPE_CHECKING

from parla.seeders.day1 import seed as seed_day1

if TYPE_CHECKING:
    from parla.container import Container


def seed(container: Container) -> None:
    """Seed day-1 data with feedback, then set skip_to_phase flag."""
    seed_day1(container, max_passages=1, max_sentences=2, seed_feedback=True)
    container._skip_to_phase = "run_through"  # noqa: SLF001 — dev-only seeder
