"""Timer widget with countdown and countup modes."""

import enum

from PySide6.QtCore import QElapsedTimer, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class TimerMode(enum.Enum):
    COUNTDOWN = "countdown"
    COUNTUP = "countup"


class TimerWidget(QWidget):
    """Displays elapsed time with countdown/countup support.

    Used in E2 (review), E3 (phase A speaking).
    """

    timeout = Signal()

    def __init__(
        self,
        mode: TimerMode = TimerMode.COUNTUP,
        duration_ms: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._duration_ms = duration_ms
        self._running = False
        self._accumulated_ms: int = 0

        self._elapsed_timer = QElapsedTimer()
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._tick)

        self._label = QLabel("00:00", self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def elapsed_ms(self) -> int:
        if self._running:
            return self._accumulated_ms + int(self._elapsed_timer.elapsed())
        return self._accumulated_ms

    def elapsed_ratio(self) -> float:
        if self._duration_ms <= 0:
            return 0.0
        return min(1.0, self.elapsed_ms / self._duration_ms)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._elapsed_timer.start()
        self._tick_timer.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._accumulated_ms += int(self._elapsed_timer.elapsed())
        self._running = False
        self._tick_timer.stop()

    def reset(self) -> None:
        self._tick_timer.stop()
        self._running = False
        self._accumulated_ms = 0
        self._update_display()

    def set_mode(self, mode: TimerMode, duration_ms: int = 0) -> None:
        self.reset()
        self._mode = mode
        self._duration_ms = duration_ms

    def _tick(self) -> None:
        elapsed = self.elapsed_ms
        if self._mode is TimerMode.COUNTDOWN and elapsed >= self._duration_ms:
            self._accumulated_ms = self._duration_ms
            self._running = False
            self._tick_timer.stop()
            self._update_display()
            self.timeout.emit()
            return
        self._update_display()

    def _update_display(self) -> None:
        elapsed = self.elapsed_ms
        if self._mode is TimerMode.COUNTDOWN:
            remaining = max(0, self._duration_ms - elapsed)
            total_seconds = remaining // 1000
        else:
            total_seconds = elapsed // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        self._label.setText(f"{minutes:02d}:{seconds:02d}")
