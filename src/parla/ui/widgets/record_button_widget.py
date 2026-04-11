"""Circular record button with pulse animation."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from parla.ui import theme


class RecordButtonWidget(QWidget):
    """Custom-painted record button: red circle (idle) / red rounded-rect (recording)."""

    clicked = Signal()

    def __init__(self, size: int = 56, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recording = False
        self._hovered = False
        self._pulse_phase = 0.0
        self._size = size

    @property
    def recording(self) -> bool:
        return self._recording

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self._pulse_phase = 0.0
        self.update()

    def advance_pulse(self, dt: float) -> None:
        if self._recording:
            self._pulse_phase += dt
            self.update()

    def enterEvent(self, _event: object) -> None:  # noqa: N802
        self._hovered = True
        self.update()

    def leaveEvent(self, _event: object) -> None:  # noqa: N802
        self._hovered = False
        self.update()

    def mousePressEvent(self, _event: object) -> None:  # noqa: N802
        self.clicked.emit()

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        border_w = 3

        # Pulse glow ring (recording)
        if self._recording:
            glow_r = cx + 2 + 4 * math.sin(self._pulse_phase * 4.2)
            glow_color = QColor(239, 68, 68, 38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow_color)
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Outer circle
        border_color = (
            QColor(theme.ERROR)
            if (self._recording or self._hovered)
            else QColor(theme.BORDER_SECONDARY)
        )
        p.setPen(QPen(border_color, border_w))
        p.setBrush(QColor(theme.BG_CARD))
        r = cx - border_w
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Hover ring
        if self._hovered and not self._recording:
            hover_ring = QColor(239, 68, 68, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_ring)
            outer = cx + 2
            p.drawEllipse(QRectF(cx - outer, cy - outer, outer * 2, outer * 2))

        # Inner shape
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ERROR))
        if self._recording:
            # Rounded rectangle (stop icon)
            half = self._size * 0.16
            rect = QRectF(cx - half, cy - half, half * 2, half * 2)
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            p.fillPath(path, QColor(theme.ERROR))
        else:
            # Circle (record icon)
            dot_r = self._size * 0.2
            p.drawEllipse(QRectF(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

        p.end()
