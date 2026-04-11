"""Shared data type for recording carousel items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class SpeakingItem:
    """A single item to record in the carousel.

    Abstracts over Passage.Sentence (new material) and Variation (review).
    """

    id: UUID
    ja: str
    hint1: str
    hint2: str
