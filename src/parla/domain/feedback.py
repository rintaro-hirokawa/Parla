"""Feedback-related value objects for Phase A/B."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SentenceFeedback(BaseModel, frozen=True):
    """Feedback result for a single sentence (Phase B display)."""

    id: UUID = Field(default_factory=uuid4)
    sentence_id: UUID
    user_utterance: str
    model_answer: str
    is_acceptable: bool
    created_at: datetime = Field(default_factory=datetime.now)


class RetryResult(BaseModel, frozen=True):
    """Immediate retry judgment result (LLM Call #5)."""

    correct: bool
    reason: str


class PracticeAttempt(BaseModel, frozen=True):
    """A single retry attempt record for a sentence."""

    id: UUID = Field(default_factory=uuid4)
    sentence_id: UUID
    attempt_number: int = Field(ge=1, le=3)
    correct: bool
    reason: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
