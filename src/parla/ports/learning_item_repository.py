"""Port for learning item persistence."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from parla.domain.learning_item import LearningItem, LearningItemStatus


class LearningItemRepository(Protocol):
    """Persists and queries learning items."""

    def save_items(self, items: Sequence[LearningItem]) -> None: ...

    def get_stocked_items(self) -> Sequence[LearningItem]: ...

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]: ...

    def update_item_status(self, item_id: UUID, status: LearningItemStatus) -> None: ...

    def get_item(self, item_id: UUID) -> LearningItem | None: ...

    def get_due_items(self, as_of: date, limit: int = 20) -> Sequence[LearningItem]:
        """Get auto_stocked items due for review, ordered by most overdue first."""
        ...

    def update_srs_state(
        self,
        item_id: UUID,
        srs_stage: int,
        ease_factor: float,
        next_review_date: date,
        correct_context_count: int,
    ) -> None: ...
