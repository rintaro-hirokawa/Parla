"""ViewModel for the learning item edit sheet (SCREEN-E5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from parla.domain.learning_item import LearningItem
    from parla.services.learning_item_query_service import LearningItemQueryService


class ItemEditViewModel(QObject):
    """Manages CRUD for learning items in a modal edit sheet.

    Does not inherit BaseViewModel — no EventBus needed for this modal.
    """

    item_updated = Signal(str)    # item_id
    item_dismissed = Signal(str)  # item_id
    dismissed = Signal()

    def __init__(self, *, item_query: LearningItemQueryService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._repo = item_query
        self._sentence_id: UUID | None = None
        self._items: Sequence[LearningItem] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def item_count(self) -> int:
        return len(self._items)

    @property
    def items(self) -> Sequence[LearningItem]:
        return list(self._items)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load_items(self, sentence_id: UUID) -> None:
        self._sentence_id = sentence_id
        self._items = self._repo.get_items_by_sentence(sentence_id)

    def update_item(self, item_id: UUID, pattern: str, explanation: str) -> None:
        self._repo.update_item(item_id, pattern, explanation)
        self._reload()
        self.item_updated.emit(str(item_id))

    def dismiss_item(self, item_id: UUID) -> None:
        self._repo.dismiss_item(item_id)
        self._reload()
        self.item_dismissed.emit(str(item_id))

    def dismiss(self) -> None:
        self.dismissed.emit()

    def _reload(self) -> None:
        if self._sentence_id:
            self._items = self._repo.get_items_by_sentence(self._sentence_id)
