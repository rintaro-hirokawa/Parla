"""Passage, Sentence, and Hint value objects."""

from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Hint(BaseModel, frozen=True):
    """Two-level progressive hint for a sentence."""

    hint1: str
    hint2: str


class Sentence(BaseModel, frozen=True):
    """A single sentence within a passage."""

    id: UUID = Field(default_factory=uuid4)
    order: int
    ja: str
    en: str
    hints: Hint


class Passage(BaseModel, frozen=True):
    """A learning passage generated from a source."""

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    order: int
    topic: str
    passage_type: str
    sentences: tuple[Sentence, ...]

    @model_validator(mode="after")
    def _validate_sentences_not_empty(self) -> "Passage":
        if len(self.sentences) == 0:
            msg = "A passage must contain at least one sentence"
            raise ValueError(msg)
        return self
