"""ViewModel for Today's Learning tab (SCREEN-C1)."""

from datetime import date

from PySide6.QtCore import Signal

from parla.domain.events import MenuConfirmed, SessionCompleted
from parla.event_bus import EventBus
from parla.services.query_models import TodayDashboard
from parla.services.session_query_service import SessionQueryService
from parla.ui.base_view_model import BaseViewModel


class TodayViewModel(BaseViewModel):
    """Manages today's learning dashboard state."""

    dashboard_loaded = Signal(object)  # TodayDashboard
    start_enabled_changed = Signal(bool)
    start_session_requested = Signal()

    def __init__(self, event_bus: EventBus, session_query_service: SessionQueryService) -> None:
        super().__init__(event_bus)
        self._session_query = session_query_service
        self._dashboard: TodayDashboard | None = None
        self._register_sync(MenuConfirmed, self._on_menu_confirmed)
        self._register_sync(SessionCompleted, self._on_session_completed)

    @property
    def dashboard(self) -> TodayDashboard | None:
        return self._dashboard

    def load_dashboard(self) -> None:
        """Load today's dashboard from query service."""
        self._dashboard = self._session_query.get_today_dashboard(today=date.today())
        self.dashboard_loaded.emit(self._dashboard)
        self.start_enabled_changed.emit(self._can_start)

    @property
    def _can_start(self) -> bool:
        d = self._dashboard
        return d is not None and d.has_menu and d.menu_confirmed

    def start_learning(self) -> None:
        """Request session start if conditions are met."""
        if self._can_start:
            self.start_session_requested.emit()

    def _on_menu_confirmed(self, _event: MenuConfirmed) -> None:
        self.load_dashboard()

    def _on_session_completed(self, _event: SessionCompleted) -> None:
        self.load_dashboard()
