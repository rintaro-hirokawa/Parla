"""Vertical level meter widget for audio RMS display."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from parla.ui import theme


class LevelMeterWidget(QWidget):
    """Displays RMS audio level as a vertical bar with warning indication.

    Used in E1 (mic check) and recording controls.
    """

    _BG_COLOR = theme.BG_SECONDARY
    _OK_COLOR = theme.ACCENT_GREEN
    _WARN_COLOR = theme.WARNING
    _BORDER_COLOR = theme.BORDER

    def __init__(
        self,
        warning_threshold: float = 0.1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._level: float = 0.0
        self._warning_threshold = warning_threshold

    @property
    def level(self) -> float:
        return self._level

    @property
    def is_warning(self) -> bool:
        return self._level < self._warning_threshold

    def set_level(self, rms: float) -> None:
        """Set the current RMS level (clamped to 0.0-1.0) and schedule repaint."""
        new_level = max(0.0, min(1.0, rms))
        if new_level == self._level:
            return
        self._level = new_level
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(20, 60)

    def minimumSizeHint(self) -> QSize:
        return QSize(12, 30)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        painter.fillRect(self.rect(), self._BG_COLOR)

        bar_height = int(self._level * h)
        if bar_height > 0:
            color = self._WARN_COLOR if self.is_warning else self._OK_COLOR
            painter.fillRect(0, h - bar_height, w, bar_height, color)

        painter.setPen(self._BORDER_COLOR)
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.end()
