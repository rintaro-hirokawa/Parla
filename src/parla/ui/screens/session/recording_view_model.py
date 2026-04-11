"""ViewModel for recording screen (SCREEN-E3).

Manages carousel navigation, hints, per-sentence timer, and recording signals.
Decoupled from Passage/Variation — accepts generic SpeakingItem list.
Service calls are handled by the coordinator via recording_submitted signal.
"""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from parla.domain.audio import AudioData
    from parla.ui.screens.session.speaking_item import SpeakingItem


class RecordingViewModel(QObject):
    """Manages sequential recording for a list of SpeakingItems."""

    current_sentence_changed = Signal(int)  # new index
    hint_revealed = Signal(int, str)  # hint_level (1 or 2), hint_text
    recording_submitted = Signal(object, object)  # item_id: UUID, audio: AudioData
    all_sentences_done = Signal()
    timer_updated = Signal(int, int, str)  # remaining, total, state_name
    error = Signal(str)

    def __init__(self, *, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._items: list[SpeakingItem] = []
        self._current_index = 0
        self._hint_level = 0

        # Per-sentence timer
        self._timer_remaining = 0
        self._timer_limit = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._is_recording = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def hint_level(self) -> int:
        return self._hint_level

    @property
    def sentence_count(self) -> int:
        return len(self._items)

    @property
    def current_ja(self) -> str:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index].ja
        return ""

    @property
    def prev_ja(self) -> str:
        idx = self._current_index - 1
        if 0 <= idx < len(self._items):
            return self._items[idx].ja
        return ""

    @property
    def next_ja(self) -> str:
        idx = self._current_index + 1
        if 0 <= idx < len(self._items):
            return self._items[idx].ja
        return ""

    @property
    def timer_ratio(self) -> float:
        if self._timer_limit <= 0:
            return 1.0
        return self._timer_remaining / self._timer_limit

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load_items(self, items: list[SpeakingItem]) -> None:
        self._items = list(items)
        self._current_index = 0
        self._hint_level = 0
        self._reset_timer()

    def sentence_ja_list(self) -> list[str]:
        return [item.ja for item in self._items]

    def reveal_hint(self) -> None:
        """Reveal the next hint level (max 2)."""
        if not self._items or self._hint_level >= 2:
            return
        self._hint_level += 1
        item = self._items[self._current_index]
        text = item.hint1 if self._hint_level == 1 else item.hint2
        self.hint_revealed.emit(self._hint_level, text)

    def start_recording(self) -> None:
        """Called when user presses record button."""
        self._is_recording = True
        self._start_timer()

    def stop_recording(self, audio: AudioData) -> None:
        """Called when user stops recording. Emits signal and advances."""
        self._is_recording = False
        self._countdown_timer.stop()

        if not self._items:
            return

        item = self._items[self._current_index]
        self.recording_submitted.emit(item.id, audio)
        self._advance()

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_time_limit(ja: str) -> int:
        return max(15, ceil(len(ja) / 10) * 3 + 10)

    def _reset_timer(self) -> None:
        self._countdown_timer.stop()
        if self._items and self._current_index < len(self._items):
            self._timer_limit = self._calc_time_limit(
                self._items[self._current_index].ja
            )
            self._timer_remaining = self._timer_limit
        else:
            self._timer_limit = 0
            self._timer_remaining = 0
        self._emit_timer()

    def _start_timer(self) -> None:
        if not self._countdown_timer.isActive():
            self._countdown_timer.start()

    def _on_countdown_tick(self) -> None:
        self._timer_remaining = max(0, self._timer_remaining - 1)
        self._emit_timer()

    def _emit_timer(self) -> None:
        ratio = self.timer_ratio
        if ratio <= 0.2:
            state = "danger"
        elif ratio <= 0.4:
            state = "caution"
        else:
            state = "normal"
        self.timer_updated.emit(self._timer_remaining, self._timer_limit, state)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _advance(self) -> None:
        self._current_index += 1
        self._hint_level = 0
        if self._current_index >= len(self._items):
            self.all_sentences_done.emit()
        else:
            self._reset_timer()
            self.current_sentence_changed.emit(self._current_index)
