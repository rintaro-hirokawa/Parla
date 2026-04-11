"""LearningItem entity — a specific weakness extracted from feedback."""

import contextlib
from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

type LearningItemCategory = Literal["文法", "語彙", "コロケーション", "構文", "表現"]
type LearningItemStatus = Literal["auto_stocked", "review_later", "dismissed"]


def status_from_priority(priority: int) -> LearningItemStatus:
    """Map V2 priority (2-5) to item status.

    V2 verification recommendations:
    - priority 4-5 → auto_stocked (auto SRS enrollment)
    - priority 2-3 → review_later (held for review)
    """
    if priority >= 4:
        return "auto_stocked"
    return "review_later"


class LearningItem(BaseModel):
    """A concrete, reusable language pattern the learner couldn't produce."""

    id: UUID = Field(default_factory=uuid4)
    pattern: str
    explanation: str
    category: LearningItemCategory
    sub_tag: str = ""
    priority: int = Field(ge=2, le=5)
    source_sentence_id: UUID
    is_reappearance: bool = False
    matched_item_id: UUID | None = None
    status: LearningItemStatus
    created_at: datetime = Field(default_factory=datetime.now)

    # SRS state (slice 3)
    srs_stage: int = Field(default=0, ge=0)
    ease_factor: float = Field(default=1.0, gt=0.0)
    next_review_date: date | None = None
    correct_context_count: int = Field(default=0, ge=0)


class RawItemData(BaseModel, frozen=True):
    """Raw learning item data for domain factory (port-agnostic)."""

    pattern: str
    explanation: str
    category: str
    sub_tag: str = ""
    priority: int
    is_reappearance: bool = False
    matched_stock_item_id: str | None = None


def create_learning_items_from_raw(
    raw_items: Sequence[RawItemData],
    sentence_id: UUID,
) -> list[LearningItem]:
    """Convert raw item data into LearningItem domain entities.

    Safely parses matched_stock_item_id (suppresses invalid UUIDs).
    Maps priority to status via status_from_priority.
    """
    items: list[LearningItem] = []
    for raw in raw_items:
        matched_id = None
        if raw.matched_stock_item_id:
            with contextlib.suppress(ValueError):
                matched_id = UUID(raw.matched_stock_item_id)

        items.append(
            LearningItem(
                pattern=raw.pattern,
                explanation=raw.explanation,
                category=cast("LearningItemCategory", raw.category),
                sub_tag=raw.sub_tag,
                priority=raw.priority,
                source_sentence_id=sentence_id,
                is_reappearance=raw.is_reappearance,
                matched_item_id=matched_id,
                status=status_from_priority(raw.priority),
            )
        )
    return items
