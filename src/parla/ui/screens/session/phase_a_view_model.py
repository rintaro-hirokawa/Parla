"""ViewModel for Phase A speaking screen (SCREEN-E3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from parla.domain.audio import AudioData
    from parla.domain.passage import Passage


class PhaseAViewModel(QObject):
    """Manages Phase A: sequential sentence recording for a passage.

    Does not inherit BaseViewModel — no EventBus event handlers needed.
    """

    current_sentence_changed = Signal(int)  # new index
    hint_revealed = Signal(int, str)  # hint_level, hint_text
    all_sentences_done = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        feedback_service: Any,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._feedback_service = feedback_service

        self._passage: Passage | None = None
        self._current_index = 0
        self._hint_level = 0

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
        return len(self._passage.sentences) if self._passage else 0

    @property
    def current_ja(self) -> str:
        if self._passage and 0 <= self._current_index < len(self._passage.sentences):
            return self._passage.sentences[self._current_index].ja
        return ""

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load_passage(self, passage: Passage) -> None:
        self._passage = passage
        self._current_index = 0
        self._hint_level = 0

    def sentence_ja_list(self) -> list[str]:
        if self._passage is None:
            return []
        return [s.ja for s in self._passage.sentences]

    def reveal_hint(self) -> None:
        """Reveal the next hint level (max 2). Level 2 includes level 1 text."""
        if self._passage is None or self._hint_level >= 2:
            return
        self._hint_level += 1
        hints = self._passage.sentences[self._current_index].hints
        text = hints.hint1 if self._hint_level == 1 else f"{hints.hint1}\n{hints.hint2}"
        self.hint_revealed.emit(self._hint_level, text)

    def submit_recording(self, audio: AudioData) -> None:
        if self._passage is None:
            return

        sentence = self._passage.sentences[self._current_index]
        self._feedback_service.record_sentence(
            passage_id=self._passage.id,
            sentence_id=sentence.id,
            audio=audio,
        )

        self._current_index += 1
        self._hint_level = 0
        if self._current_index >= len(self._passage.sentences):
            self.all_sentences_done.emit()
        else:
            self.current_sentence_changed.emit(self._current_index)
