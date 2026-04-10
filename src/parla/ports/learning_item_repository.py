"""Port for learning item persistence."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from parla.domain.learning_item import LearningItem, LearningItemStatus


class LearningItemRepository(Protocol):
    """Persists and queries learning items."""

    def save_items(self, items: Sequence[LearningItem]) -> None: ...

    def get_stocked_items(self) -> Sequence[LearningItem]: ...

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]: ...

    def update_item_status(self, item_id: UUID, status: LearningItemStatus) -> None: ...
