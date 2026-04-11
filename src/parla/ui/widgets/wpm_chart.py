"""WPM trend line chart widget with CEFR target line."""

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from parla.domain.source import CEFRLevel
from parla.domain.wpm import CEFR_WPM_TARGETS
from parla.services.query_models import WpmDataPoint
from parla.ui import theme


class WpmChartWidget(QWidget):
    """Line chart for WPM trend with CEFR target minimum line.

    Used in C3 (item detail), C4 (history), F1 (session summary).
    """

    _MARGIN_LEFT = 40
    _MARGIN_RIGHT = 10
    _MARGIN_TOP = 10
    _MARGIN_BOTTOM = 30

    _BG_COLOR = theme.BG_PRIMARY
    _AXIS_PEN = theme.PEN_BORDER
    _LABEL_COLOR = theme.TEXT_SECONDARY
    _NO_DATA_COLOR = theme.TEXT_DISABLED
    _BAND_COLOR = theme.BAND_BG
    _LINE_PEN = theme.PEN_ACCENT_BLUE_2
    _DOT_COLOR = theme.ACCENT

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data_points: Sequence[WpmDataPoint] = ()
        self._cefr_level: CEFRLevel | None = None

        self._label_font = QFont()
        self._label_font.setPointSize(theme.FONT_SIZE_XS)

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
        self.update()

    def clear(self) -> None:
        self._data_points = ()
        self._cefr_level = None
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 150)

    def minimumSizeHint(self) -> QSize:
        return QSize(150, 80)

    def _get_cefr_target(self) -> int | None:
        """Look up CEFR minimum WPM target, returning None if level is not in targets."""
        if self._cefr_level is None:
            return None
        return CEFR_WPM_TARGETS.get(self._cefr_level)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self._BG_COLOR)

        chart_left = self._MARGIN_LEFT
        chart_top = self._MARGIN_TOP
        chart_width = self.width() - self._MARGIN_LEFT - self._MARGIN_RIGHT
        chart_height = self.height() - self._MARGIN_TOP - self._MARGIN_BOTTOM

        if chart_width <= 0 or chart_height <= 0:
            painter.end()
            return

        # Determine Y range
        cefr_target = self._get_cefr_target()
        wpm_values = [p.wpm for p in self._data_points]
        all_values = list(wpm_values)
        if cefr_target is not None:
            all_values.append(cefr_target)

        if not all_values:
            painter.setPen(self._NO_DATA_COLOR)
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

        # Draw CEFR target line
        if cefr_target is not None:
            target_y = y_to_px(cefr_target)
            painter.setPen(self._BAND_COLOR)
            painter.drawLine(chart_left, target_y, chart_left + chart_width, target_y)

        # Draw axes
        painter.setPen(self._AXIS_PEN)
        painter.drawLine(chart_left, chart_top, chart_left, chart_top + chart_height)
        painter.drawLine(
            chart_left, chart_top + chart_height,
            chart_left + chart_width, chart_top + chart_height,
        )

        # Y-axis labels
        painter.setFont(self._label_font)
        painter.setPen(self._LABEL_COLOR)
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
        painter.setPen(self._LINE_PEN)
        for i in range(len(point_coords) - 1):
            x1, y1 = point_coords[i]
            x2, y2 = point_coords[i + 1]
            painter.drawLine(x1, y1, x2, y2)

        # Dots
        painter.setBrush(self._DOT_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        for px, py in point_coords:
            painter.drawEllipse(px - 3, py - 3, 6, 6)

        painter.end()
