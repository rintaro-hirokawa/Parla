"""WPM trend line chart widget with CEFR target range band."""

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from parla.domain.source import CEFRLevel
from parla.domain.wpm import CEFR_WPM_TARGETS
from parla.services.query_models import WpmDataPoint


class WpmChartWidget(QWidget):
    """Line chart for WPM trend with CEFR target range band.

    Used in C3 (item detail), C4 (history), F1 (session summary).
    """

    _MARGIN_LEFT = 40
    _MARGIN_RIGHT = 10
    _MARGIN_TOP = 10
    _MARGIN_BOTTOM = 30

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data_points: Sequence[WpmDataPoint] = ()
        self._cefr_level: CEFRLevel | None = None
        self._cefr_lower: int = 0
        self._cefr_upper: int = 0

    @property
    def data_points(self) -> Sequence[WpmDataPoint]:
        return self._data_points

    @property
    def cefr_level(self) -> CEFRLevel | None:
        return self._cefr_level

    def set_data(self, points: Sequence[WpmDataPoint]) -> None:
        self._data_points = points
        self.update()

    def set_cefr_target(self, level: CEFRLevel) -> None:
        self._cefr_level = level
        targets = CEFR_WPM_TARGETS.get(level)
        if targets:
            self._cefr_lower, self._cefr_upper = targets
        self.update()

    def clear(self) -> None:
        self._data_points = ()
        self._cefr_level = None
        self._cefr_lower = 0
        self._cefr_upper = 0
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 150)

    def minimumSizeHint(self) -> QSize:
        return QSize(150, 80)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        chart_left = self._MARGIN_LEFT
        chart_top = self._MARGIN_TOP
        chart_width = self.width() - self._MARGIN_LEFT - self._MARGIN_RIGHT
        chart_height = self.height() - self._MARGIN_TOP - self._MARGIN_BOTTOM

        if chart_width <= 0 or chart_height <= 0:
            painter.end()
            return

        # Determine Y range
        wpm_values = [p.wpm for p in self._data_points]
        all_values = list(wpm_values)
        if self._cefr_lower > 0:
            all_values.extend([self._cefr_lower, self._cefr_upper])

        if not all_values:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data")
            painter.end()
            return

        y_min = max(0, min(all_values) - 10)
        y_max = max(all_values) + 10
        y_range = y_max - y_min
        if y_range == 0:
            y_range = 1

        def y_to_px(wpm: float) -> int:
            return int(chart_top + chart_height - (wpm - y_min) / y_range * chart_height)

        # Draw CEFR target band
        if self._cefr_lower > 0:
            band_top = y_to_px(self._cefr_upper)
            band_bottom = y_to_px(self._cefr_lower)
            painter.fillRect(
                chart_left, band_top, chart_width, band_bottom - band_top,
                QColor(0, 150, 100, 40),
            )

        # Draw axes
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawLine(chart_left, chart_top, chart_left, chart_top + chart_height)
        painter.drawLine(
            chart_left, chart_top + chart_height,
            chart_left + chart_width, chart_top + chart_height,
        )

        # Y-axis labels
        label_font = QFont()
        label_font.setPointSize(7)
        painter.setFont(label_font)
        painter.setPen(QColor(150, 150, 150))
        for wpm_val in [y_min, (y_min + y_max) / 2, y_max]:
            py = y_to_px(wpm_val)
            painter.drawText(0, py - 6, self._MARGIN_LEFT - 4, 12, Qt.AlignmentFlag.AlignRight, f"{int(wpm_val)}")

        # Plot data points
        if not self._data_points:
            painter.end()
            return

        n = len(self._data_points)
        point_coords: list[tuple[int, int]] = []
        for i, dp in enumerate(self._data_points):
            px = chart_left + chart_width // 2 if n == 1 else chart_left + int(i / (n - 1) * chart_width)
            py = y_to_px(dp.wpm)
            point_coords.append((px, py))

        # Lines
        line_pen = QPen(QColor(80, 180, 255), 2)
        painter.setPen(line_pen)
        for i in range(len(point_coords) - 1):
            x1, y1 = point_coords[i]
            x2, y2 = point_coords[i + 1]
            painter.drawLine(x1, y1, x2, y2)

        # Dots
        painter.setBrush(QColor(80, 180, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        for px, py in point_coords:
            painter.drawEllipse(px - 3, py - 3, 6, 6)

        painter.end()
