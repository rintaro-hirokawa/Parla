"""Port for variation (practice question) generation for SRS review.

Uses the history-based method (V7 Phase C) to ensure grammatical diversity.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel


class PastVariationInfo(BaseModel, frozen=True):
    """Lightweight DTO of a past variation for diversity in prompt."""

    ja: str
    en: str


class RawVariation(BaseModel, frozen=True):
    """Variation as returned by the adapter (before domain entity conversion)."""

    ja: str
    en: str
    hint1: str
    hint2: str


class VariationGenerationPort(Protocol):
    """Generates a practice question for a learning item in a new context."""

    async def generate_variation(
        self,
        learning_item_pattern: str,
        learning_item_explanation: str,
        cefr_level: str,
        english_variant: str,
        source_text: str,
        past_variations: Sequence[PastVariationInfo],
    ) -> RawVariation: ...
