"""Learning calendar widget with activity markers."""

from collections.abc import Mapping, Sequence
from datetime import date
from types import MappingProxyType

from PySide6.QtCore import QDate, QRect, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCalendarWidget, QWidget

from parla.services.query_models import CalendarMarker
from parla.ui import theme


class CalendarWidget(QCalendarWidget):
    """Calendar with learning activity markers on dates.

    Used in C4 (learning history).
    """

    date_selected = Signal(object)  # datetime.date

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._markers: dict[date, int] = {}
        self._markers_view: Mapping[date, int] = MappingProxyType(self._markers)
        # QDate-keyed version for fast lookup in paintCell
        self._qdate_markers: dict[QDate, int] = {}
        self.clicked.connect(self._on_clicked)

    @property
    def markers(self) -> Mapping[date, int]:
        return self._markers_view

    def set_markers(self, markers: Sequence[CalendarMarker]) -> None:
        self._markers.clear()
        self._qdate_markers.clear()
        for m in markers:
            self._markers[m.date] = m.session_count
            self._qdate_markers[QDate(m.date.year, m.date.month, m.date.day)] = m.session_count
        self.updateCells()

    def set_month(self, year: int, month: int) -> None:
        self.setCurrentPage(year, month)

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate) -> None:
        super().paintCell(painter, rect, qdate)
        session_count = self._qdate_markers.get(qdate)
        if session_count is not None and session_count > 0:
            alpha = min(255, 100 + session_count * 50)
            color = QColor(theme.CORRECT_TEXT)
            color.setAlpha(alpha)
            dot_radius = 3
            cx = rect.center().x()
            cy = rect.bottom() - dot_radius - 2
            painter.setBrush(color)
            painter.setPen(color)
            painter.drawEllipse(cx - dot_radius, cy - dot_radius, dot_radius * 2, dot_radius * 2)

    def _on_clicked(self, qdate: QDate) -> None:
        self.date_selected.emit(date(qdate.year(), qdate.month(), qdate.day()))
