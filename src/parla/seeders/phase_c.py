"""Phase C state seeder — skip Phase A/B and start directly at Phase C."""

from __future__ import annotations

from typing import TYPE_CHECKING

from parla.seeders.day1 import seed as seed_day1

if TYPE_CHECKING:
    from parla.ui.container import Container


def seed(container: Container) -> None:
    """Seed day-1 data with feedback, then set skip_to_phase flag."""
    seed_day1(container, max_passages=1, max_sentences=2, seed_feedback=True)
    container.skip_to_phase = "c"
