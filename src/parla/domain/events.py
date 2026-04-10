"""Domain events. All events are defined in this single file for discoverability."""

from uuid import UUID

from parla.event_bus import Event

# --- Slice 1: Source registration & passage generation ---


class SourceRegistered(Event, frozen=True):
    """A source has been registered. Triggers passage generation."""

    source_id: UUID


class PassageGenerationStarted(Event, frozen=True):
    """Passage generation has started (status: generating)."""

    source_id: UUID


class PassageGenerationCompleted(Event, frozen=True):
    """Passage generation completed successfully (status: not_started)."""

    source_id: UUID
    passage_count: int
    total_sentences: int


class PassageGenerationFailed(Event, frozen=True):
    """Passage generation failed (status: generation_failed)."""

    source_id: UUID
    error_message: str


# --- Slice 2: Phase A → Phase B (feedback & retry) ---


class SentenceRecorded(Event, frozen=True):
    """User finished speaking a sentence in Phase A. Triggers feedback generation."""

    passage_id: UUID
    sentence_id: UUID


class FeedbackReady(Event, frozen=True):
    """Feedback generated successfully for a sentence."""

    passage_id: UUID
    sentence_id: UUID


class FeedbackFailed(Event, frozen=True):
    """Feedback generation failed for a sentence."""

    passage_id: UUID
    sentence_id: UUID
    error_message: str


class LearningItemStocked(Event, frozen=True):
    """A learning item was auto-stocked from feedback."""

    item_id: UUID
    pattern: str
    is_reappearance: bool


class RetryJudged(Event, frozen=True):
    """Retry judgment completed for a sentence in Phase B."""

    sentence_id: UUID
    attempt: int
    correct: bool
