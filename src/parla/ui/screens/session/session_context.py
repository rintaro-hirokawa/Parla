"""Shared session-level state holder.

Tracks block progress, elapsed time, cumulative word count, and average WPM
across all session screens.  Emits Qt Signals (not EventBus events) because
this is transient UI state, not domain state.
"""

from PySide6.QtCore import QObject, QTimer, Signal


class SessionContext(QObject):
    """Mutable session metrics shared by the header and all session ViewModels."""

    progress_changed = Signal()
    elapsed_changed = Signal(int)   # seconds
    words_changed = Signal(int)     # cumulative word count
    wpm_changed = Signal(float)     # average WPM

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._block_name = ""
        self._progress_current = 0
        self._progress_total = 0
        self._elapsed_seconds = 0
        self._cumulative_words = 0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def block_name(self) -> str:
        return self._block_name

    @property
    def progress_current(self) -> int:
        return self._progress_current

    @property
    def progress_total(self) -> int:
        return self._progress_total

    @property
    def progress_label(self) -> str:
        if not self._block_name:
            return ""
        if self._progress_total == 0:
            return self._block_name
        return f"{self._block_name} ({self._progress_current}/{self._progress_total})"

    @property
    def elapsed_seconds(self) -> int:
        return self._elapsed_seconds

    @property
    def elapsed_display(self) -> str:
        m, s = divmod(self._elapsed_seconds, 60)
        return f"{m:02d}:{s:02d}"

    @property
    def cumulative_word_count(self) -> int:
        return self._cumulative_words

    @property
    def average_wpm(self) -> float:
        if self._elapsed_seconds == 0:
            return 0.0
        return self._cumulative_words / (self._elapsed_seconds / 60)

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def update_progress(self, block_name: str, current: int, total: int) -> None:
        if (self._block_name, self._progress_current, self._progress_total) == (block_name, current, total):
            return
        self._block_name = block_name
        self._progress_current = current
        self._progress_total = total
        self.progress_changed.emit()

    def add_words(self, count: int) -> None:
        self._cumulative_words += count
        self.words_changed.emit(self._cumulative_words)
        self.wpm_changed.emit(self.average_wpm)

    def start_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop_timer(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self._timer.stop()
        self._block_name = ""
        self._progress_current = 0
        self._progress_total = 0
        self._elapsed_seconds = 0
        self._cumulative_words = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._elapsed_seconds += 1
        self.elapsed_changed.emit(self._elapsed_seconds)
