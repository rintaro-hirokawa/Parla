"""ViewModel for learning item list screen (SCREEN-C2)."""

from uuid import UUID

from PySide6.QtCore import Signal

from parla.domain.events import LearningItemStocked, SRSUpdated
from parla.domain.learning_item import LearningItemCategory, LearningItemStatus
from parla.event_bus import EventBus
from parla.services.learning_item_query_service import LearningItemQueryService
from parla.services.query_models import LearningItemFilter, LearningItemRow
from parla.ui.base_view_model import BaseViewModel


class ListViewModel(BaseViewModel):
    """ViewModel for the learning item list (C2) screen."""

    items_loaded = Signal(tuple)
    navigate_to_detail = Signal(object)

    def __init__(
        self,
        event_bus: EventBus,
        item_query: LearningItemQueryService,
    ) -> None:
        super().__init__(event_bus)
        self._item_query = item_query
        self._items: tuple[LearningItemRow, ...] = ()
        self._current_filter: LearningItemFilter | None = None
        self._register_sync(LearningItemStocked, self._on_item_changed)
        self._register_sync(SRSUpdated, self._on_item_changed)

    def load_items(self) -> None:
        self._items = self._item_query.list_items(filter=self._current_filter)
        self.items_loaded.emit(self._items)

    def apply_filter(
        self,
        category: LearningItemCategory | None = None,
        status: LearningItemStatus | None = None,
        srs_stage: int | None = None,
        source_id: UUID | None = None,
    ) -> None:
        if category is None and status is None and srs_stage is None and source_id is None:
            self._current_filter = None
        else:
            self._current_filter = LearningItemFilter(
                category=category, status=status, srs_stage=srs_stage, source_id=source_id,
            )
        self.load_items()

    def select_item(self, item_id: UUID) -> None:
        self.navigate_to_detail.emit(item_id)

    @property
    def items(self) -> tuple[LearningItemRow, ...]:
        return self._items

    @property
    def current_filter(self) -> LearningItemFilter | None:
        return self._current_filter

    def _on_item_changed(self, _event: object) -> None:
        self.load_items()
