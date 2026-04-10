"""Review judgment and attempt records for Block 1/3."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewResult(BaseModel, frozen=True):
    """Judgment result for a Block 1/3 review utterance.

    Differs from RetryResult (Phase B) in that it checks whether the
    target learning item pattern was used, not just model answer reproduction.
    """

    correct: bool
    item_used: bool
    reason: str


class ReviewAttempt(BaseModel, frozen=True):
    """Record of a single Block 1/3 review attempt."""

    id: UUID = Field(default_factory=uuid4)
    variation_id: UUID
    learning_item_id: UUID
    attempt_number: int = Field(ge=1, le=4)
    correct: bool
    item_used: bool
    hint_level: int = Field(ge=0, le=2)
    timer_ratio: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)
