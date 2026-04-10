"""Source entity and related types."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from parla.domain.errors import (
    InvalidStatusTransition,
    SourceTextTooLong,
    SourceTextTooShort,
)

type SourceStatus = Literal[
    "registered",
    "generating",
    "generation_failed",
    "not_started",
    "in_progress",
    "completed",
    "archived",
]

type CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
type EnglishVariant = Literal["American", "British", "Australian", "Canadian", "Indian"]

_MIN_TEXT_LENGTH = 100
_MAX_TEXT_LENGTH = 50_000

_VALID_TRANSITIONS: dict[SourceStatus, set[SourceStatus]] = {
    "registered": {"generating"},
    "generating": {"not_started", "generation_failed"},
    "generation_failed": set(),
    "not_started": {"in_progress"},
    "in_progress": {"completed"},
    "completed": {"archived"},
    "archived": set(),
}


class Source(BaseModel):
    """A user-registered source text for learning material generation."""

    id: UUID = Field(default_factory=uuid4)
    title: str = ""
    text: str
    cefr_level: CEFRLevel
    english_variant: EnglishVariant
    status: SourceStatus = "registered"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def _validate_text_length(self) -> "Source":
        if len(self.text) < _MIN_TEXT_LENGTH:
            msg = f"Source text must be at least {_MIN_TEXT_LENGTH} characters, got {len(self.text)}"
            raise SourceTextTooShort(msg)
        if len(self.text) > _MAX_TEXT_LENGTH:
            msg = f"Source text must be at most {_MAX_TEXT_LENGTH} characters, got {len(self.text)}"
            raise SourceTextTooLong(msg)
        return self

    def _transition(self, new_status: SourceStatus) -> "Source":
        if new_status not in _VALID_TRANSITIONS[self.status]:
            msg = f"Cannot transition from '{self.status}' to '{new_status}'"
            raise InvalidStatusTransition(msg)
        return self.model_copy(update={"status": new_status, "updated_at": datetime.now()})

    def start_generating(self) -> "Source":
        return self._transition("generating")

    def complete_generation(self) -> "Source":
        return self._transition("not_started")

    def fail_generation(self) -> "Source":
        return self._transition("generation_failed")
