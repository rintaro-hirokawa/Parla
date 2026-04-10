"""Domain events. All events are defined in this single file for discoverability."""

from uuid import UUID

from parla.event_bus import Event


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
