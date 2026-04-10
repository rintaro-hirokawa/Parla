"""Port for source and passage persistence."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.passage import Passage
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
