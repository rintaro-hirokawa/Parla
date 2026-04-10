"""Port for source and passage persistence."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.passage import Passage, Sentence
from parla.domain.source import Source


class SourceRepository(Protocol):
    """Persists sources and their generated passages."""

    def save_source(self, source: Source) -> None: ...

    def get_source(self, source_id: UUID) -> Source | None: ...

    def update_source(self, source: Source) -> None: ...

    def save_passages(self, passages: Sequence[Passage]) -> None: ...

    def get_passages_by_source(self, source_id: UUID) -> Sequence[Passage]: ...

    def get_passage(self, passage_id: UUID) -> Passage | None: ...

    def get_active_sources(self) -> Sequence[Source]:
        """Get sources with status not_started or in_progress."""
        ...

    def get_all_sources(self) -> Sequence[Source]:
        """Get all sources regardless of status."""
        ...

    def get_sentence(self, sentence_id: UUID) -> Sentence | None:
        """Get a single sentence by ID."""
        ...

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        """Get the source that contains the given sentence (via JOIN)."""
        ...
