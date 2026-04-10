"""Port for feedback generation from user speech audio.

The 2-stage pipeline (audio→text, text→feedback) is an adapter-internal
implementation detail. The port just returns a RawFeedback DTO.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field


class StockedItemInfo(BaseModel, frozen=True):
    """Lightweight DTO for reappearance detection in LLM prompt."""

    item_id: str
    pattern: str
    category: str
    example_sentence: str = ""


class RawLearningItem(BaseModel, frozen=True):
    """Learning item as returned by the LLM (before domain entity conversion)."""

    pattern: str
    explanation: str
    category: str
    sub_tag: str = ""
    priority: int = Field(ge=2, le=5)
    is_reappearance: bool = False
    matched_stock_item_id: str | None = None


class RawFeedback(BaseModel, frozen=True):
    """Feedback result DTO from the adapter."""

    user_utterance: str
    model_answer: str
    is_acceptable: bool
    items: tuple[RawLearningItem, ...] = ()


class FeedbackGenerationPort(Protocol):
    """Generates feedback for a single sentence's audio recording."""

    async def generate_feedback(
        self,
        audio_data: bytes,
        audio_format: str,
        ja_prompt: str,
        cefr_level: str,
        english_variant: str,
        stocked_items: Sequence[StockedItemInfo],
    ) -> RawFeedback: ...
