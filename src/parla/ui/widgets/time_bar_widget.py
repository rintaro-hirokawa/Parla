"""Thin progress bar with normal / caution / danger states."""

from __future__ import annotations

import math

from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from parla.ui import theme


class TimeBarWidget(QWidget):
    """3–5 px horizontal time bar that changes colour by urgency."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(5)
        self._ratio = 1.0
        self._state = "normal"  # normal | caution | danger
        self._pulse_phase = 0.0

    def set_state(self, ratio: float, state: str) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._state = state
        self.update()

    def advance_pulse(self, dt: float) -> None:
        self._pulse_phase += dt
        if self._state == "danger":
            self.update()

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Track
        p.fillRect(0, 0, w, h, QColor(theme.BORDER_LIGHT))

        # Fill
        if self._state == "danger":
            color = QColor(theme.ERROR)
            bar_h = 5
            opacity = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._pulse_phase * 10))
            p.setOpacity(opacity)
        elif self._state == "caution":
            color = QColor(theme.WARNING)
            bar_h = 4
        else:
            color = QColor(theme.ACCENT)
            bar_h = 3

        fill_w = int(w * self._ratio)
        y = (h - bar_h) // 2
        p.fillRect(0, y, fill_w, bar_h, color)
        p.setOpacity(1.0)
        p.end()
