"""ViewModel for session end summary (SCREEN-F1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from uuid import UUID

    from parla.services.query_models import SessionSummary


class SessionSummaryViewModel(QObject):
    """Loads and exposes session summary data."""

    summary_loaded = Signal()
    navigate_to_menu = Signal()
    error = Signal(str)

    def __init__(self, *, session_query_service: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._query = session_query_service
        self._summary: SessionSummary | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pattern(self) -> str:
        return self._summary.pattern if self._summary else ""

    @property
    def duration_minutes(self) -> float:
        return self._summary.duration_minutes if self._summary else 0.0

    @property
    def passage_count(self) -> int:
        return self._summary.passage_count if self._summary else 0

    @property
    def new_item_count(self) -> int:
        return self._summary.new_item_count if self._summary else 0

    @property
    def review_count(self) -> int:
        return self._summary.review_count if self._summary else 0

    @property
    def review_correct_count(self) -> int:
        return self._summary.review_correct_count if self._summary else 0

    @property
    def average_wpm(self) -> float:
        return self._summary.average_wpm if self._summary else 0.0

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load(self, session_id: UUID) -> None:
        self._summary = self._query.get_session_summary(session_id)
        if self._summary is None:
            self.error.emit("Session summary not found")
            return
        self.summary_loaded.emit()

    def proceed(self) -> None:
        self.navigate_to_menu.emit()
