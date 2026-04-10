"""LearningItem entity — a specific weakness extracted from feedback."""

from datetime import date, datetime
from typing import Literal
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
