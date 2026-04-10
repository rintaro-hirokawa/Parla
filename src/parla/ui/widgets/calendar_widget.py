"""Learning calendar widget with activity markers."""

from collections.abc import Sequence
from datetime import date

from PySide6.QtCore import QDate, QRect, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCalendarWidget, QWidget

from parla.services.query_models import CalendarMarker


class CalendarWidget(QCalendarWidget):
    """Calendar with learning activity markers on dates.

    Used in C4 (learning history).
    """

    date_selected = Signal(object)  # datetime.date

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._markers: dict[date, int] = {}
        self.clicked.connect(self._on_clicked)

    @property
    def markers(self) -> dict[date, int]:
        return self._markers

    def set_markers(self, markers: Sequence[CalendarMarker]) -> None:
        self._markers = {m.date: m.session_count for m in markers}
        self.updateCells()

    def set_month(self, year: int, month: int) -> None:
        self.setCurrentPage(year, month)

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate) -> None:
        super().paintCell(painter, rect, qdate)
        py_date = date(qdate.year(), qdate.month(), qdate.day())
        session_count = self._markers.get(py_date)
        if session_count is not None and session_count > 0:
            # Draw a dot at bottom-center
            alpha = min(255, 100 + session_count * 50)
            color = QColor(0, 180, 120, alpha)
            dot_radius = 3
            cx = rect.center().x()
            cy = rect.bottom() - dot_radius - 2
            painter.setBrush(color)
            painter.setPen(color)
            painter.drawEllipse(cx - dot_radius, cy - dot_radius, dot_radius * 2, dot_radius * 2)

    def _on_clicked(self, qdate: QDate) -> None:
        py_date = date(qdate.year(), qdate.month(), qdate.day())
        self.date_selected.emit(py_date)
