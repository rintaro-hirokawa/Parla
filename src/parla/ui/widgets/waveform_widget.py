"""Real-time waveform display widget using QPainter."""

from collections import deque
from collections.abc import Sequence

from PySide6.QtCore import QLine, QSize
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    """Displays a real-time audio waveform using a ring buffer.

    Used in E1 (mic check), E2 (review), E3 (phase A), E6 (phase C).
    """

    _BG_COLOR = QColor(30, 30, 30)
    _CENTER_LINE_PEN = QPen(QColor(60, 60, 60), 1)
    _WAVEFORM_PEN = QPen(QColor(0, 200, 100), 1)

    def __init__(self, buffer_size: int = 1024, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buffer_size = buffer_size
        self._buffer: deque[float] = deque([0.0] * buffer_size, maxlen=buffer_size)

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    def update_samples(self, samples: Sequence[float]) -> None:
        """Append samples to the ring buffer and schedule a repaint."""
        self._buffer.extend(max(-1.0, min(1.0, s)) for s in samples)
        self.update()

    def clear(self) -> None:
        """Reset the buffer to silence."""
        self._buffer = deque([0.0] * self._buffer_size, maxlen=self._buffer_size)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(200, 60)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 30)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        center_y = h / 2.0

        painter.fillRect(self.rect(), self._BG_COLOR)

        painter.setPen(self._CENTER_LINE_PEN)
        painter.drawLine(0, int(center_y), w, int(center_y))

        if self._buffer_size == 0:
            painter.end()
            return

        painter.setPen(self._WAVEFORM_PEN)

        x_step = w / self._buffer_size
        center_i = int(center_y)
        lines = [
            QLine(int(i * x_step), int(center_y - sample * center_y), int(i * x_step), center_i)
            for i, sample in enumerate(self._buffer)
        ]
        painter.drawLines(lines)

        painter.end()
