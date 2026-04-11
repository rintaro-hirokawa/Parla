"""Horizontal progress dots indicator."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from parla.ui import theme


class ProgressDotsWidget(QWidget):
    """Row of dots: done (filled) / current (filled + glow ring) / upcoming (gray)."""

    _DOT_RADIUS = 5
    _GAP = 8
    _GLOW_EXTRA = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = 0
        self._current = 0
        self.setFixedHeight(self._DOT_RADIUS * 2 + self._GLOW_EXTRA * 2)

    def set_count(self, n: int) -> None:
        self._count = n
        self._current = min(self._current, max(0, n - 1))
        self._update_width()
        self.update()

    def set_current(self, idx: int) -> None:
        self._current = idx
        self.update()

    def _update_width(self) -> None:
        if self._count <= 0:
            self.setFixedWidth(0)
            return
        total_w = self._count * self._DOT_RADIUS * 2 + (self._count - 1) * self._GAP
        self.setFixedWidth(total_w + self._GLOW_EXTRA * 2)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        if self._count <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        total_w = self._count * self._DOT_RADIUS * 2 + (self._count - 1) * self._GAP
        start_x = (self.width() - total_w) / 2 + self._DOT_RADIUS
        cy = self.height() / 2

        for i in range(self._count):
            cx = start_x + i * (self._DOT_RADIUS * 2 + self._GAP)

            if i < self._current:
                # Done
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.ACCENT))
                p.drawEllipse(QRectF(
                    cx - self._DOT_RADIUS, cy - self._DOT_RADIUS,
                    self._DOT_RADIUS * 2, self._DOT_RADIUS * 2,
                ))
            elif i == self._current:
                # Current — glow ring
                glow_color = QColor(theme.ACCENT)
                glow_color.setAlpha(46)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow_color)
                glow_r = self._DOT_RADIUS + self._GLOW_EXTRA
                p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
                # Dot
                p.setBrush(QColor(theme.ACCENT))
                r = self._DOT_RADIUS + 1
                p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
            else:
                # Upcoming
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(theme.BORDER))
                p.drawEllipse(QRectF(
                    cx - self._DOT_RADIUS, cy - self._DOT_RADIUS,
                    self._DOT_RADIUS * 2, self._DOT_RADIUS * 2,
                ))

        p.end()
