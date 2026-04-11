"""Day 1 short state seeder — 1 passage, 2 sentences for quick testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from parla.seeders.day1 import seed as seed_day1

if TYPE_CHECKING:
    from parla.ui.container import Container


def seed(container: Container) -> None:
    """Reset DB and seed minimal day-1 state: 1 passage with 2 sentences."""
    seed_day1(container, max_passages=1, max_sentences=2)
