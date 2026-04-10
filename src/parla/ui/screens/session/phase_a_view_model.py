"""ViewModel for Phase A speaking screen (SCREEN-E3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal

from parla.ui.base_view_model import BaseViewModel

if TYPE_CHECKING:
    from parla.domain.audio import AudioData
    from parla.domain.passage import Passage
    from parla.event_bus import EventBus
    from parla.ui.screens.session.session_context import SessionContext


class PhaseAViewModel(BaseViewModel):
    """Manages Phase A: sequential sentence recording for a passage."""

    current_sentence_changed = Signal(int)  # new index
    all_sentences_done = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        feedback_service: Any,
        item_query_service: Any,
        session_context: SessionContext,
    ) -> None:
        super().__init__(event_bus)
        self._feedback_service = feedback_service
        self._item_query = item_query_service
        self._ctx = session_context

        self._passage: Passage | None = None
        self._current_index = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_index(self) -> int:
        return self._current_index

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

    def sentence_ja_list(self) -> list[str]:
        if self._passage is None:
            return []
        return [s.ja for s in self._passage.sentences]

    def has_hint_for_current(self) -> bool:
        if self._passage is None:
            return False
        sentence = self._passage.sentences[self._current_index]
        items = self._item_query.get_sentence_items(sentence.id)
        return len(items) > 0

    def get_hint_items(self) -> tuple:
        if self._passage is None:
            return ()
        sentence = self._passage.sentences[self._current_index]
        return self._item_query.get_sentence_items(sentence.id)

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
        if self._current_index >= len(self._passage.sentences):
            self.all_sentences_done.emit()
        else:
            self.current_sentence_changed.emit(self._current_index)
