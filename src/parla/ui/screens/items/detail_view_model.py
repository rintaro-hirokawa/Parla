"""ViewModel for learning item detail screen (SCREEN-C3)."""

from uuid import UUID

from PySide6.QtCore import Signal

from parla.domain.events import SRSUpdated
from parla.event_bus import EventBus
from parla.services.learning_item_query_service import LearningItemQueryService
from parla.services.query_models import LearningItemDetail
from parla.ui.base_view_model import BaseViewModel


class DetailViewModel(BaseViewModel):
    """ViewModel for the learning item detail (C3) screen."""

    detail_loaded = Signal(object)
    detail_not_found = Signal()
    navigate_back = Signal()

    def __init__(
        self,
        event_bus: EventBus,
        item_query: LearningItemQueryService,
    ) -> None:
        super().__init__(event_bus)
        self._item_query = item_query
        self._detail: LearningItemDetail | None = None
        self._item_id: UUID | None = None
        self._register_sync(SRSUpdated, self._on_srs_updated)

    def load_detail(self, item_id: UUID) -> None:
        self._item_id = item_id
        self._detail = self._item_query.get_item_detail(item_id)
        if self._detail is not None:
            self.detail_loaded.emit(self._detail)
        else:
            self.detail_not_found.emit()

    def go_back(self) -> None:
        self.navigate_back.emit()

    @property
    def detail(self) -> LearningItemDetail | None:
        return self._detail

    def _on_srs_updated(self, event: SRSUpdated) -> None:
        if self._item_id is not None and event.learning_item_id == self._item_id:
            self.load_detail(self._item_id)
