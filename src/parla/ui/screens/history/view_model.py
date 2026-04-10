"""ViewModel for learning history screen (SCREEN-C4)."""

from datetime import date

from PySide6.QtCore import Signal

from parla.domain.events import SessionCompleted
from parla.event_bus import EventBus
from parla.services.history_query_service import HistoryQueryService
from parla.services.query_models import DailySummary, HistoryOverview
from parla.ui.base_view_model import BaseViewModel


class HistoryViewModel(BaseViewModel):
    """ViewModel for the learning history (C4) tab."""

    overview_loaded = Signal(object)
    daily_summary_loaded = Signal(object)

    def __init__(
        self,
        event_bus: EventBus,
        history_query: HistoryQueryService,
    ) -> None:
        super().__init__(event_bus)
        self._history_query = history_query
        self._overview: HistoryOverview | None = None
        self._daily_summary: DailySummary | None = None
        self._register_sync(SessionCompleted, self._on_session_completed)

    def load_overview(self) -> None:
        self._overview = self._history_query.get_history_overview()
        self.overview_loaded.emit(self._overview)

    def select_date(self, target_date: date) -> None:
        self._daily_summary = self._history_query.get_daily_summary(target_date)
        self.daily_summary_loaded.emit(self._daily_summary)

    @property
    def overview(self) -> HistoryOverview | None:
        return self._overview

    @property
    def daily_summary(self) -> DailySummary | None:
        return self._daily_summary

    def _on_session_completed(self, _event: SessionCompleted) -> None:
        self.load_overview()
