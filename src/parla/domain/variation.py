"""Variation (practice question) for SRS review."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Variation(BaseModel, frozen=True):
    """A practice question generated for a learning item review.

    Different from Passage sentences — variations are standalone questions
    generated to practice a specific learning item in a new context.
    """

    id: UUID = Field(default_factory=uuid4)
    learning_item_id: UUID
    source_id: UUID
    ja: str
    en: str
    hint1: str
    hint2: str
    created_at: datetime = Field(default_factory=datetime.now)
