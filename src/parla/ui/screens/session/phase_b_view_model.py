"""ViewModel for Phase B feedback screen (SCREEN-E4)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal

from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
)
from parla.ui.base_view_model import BaseViewModel
from parla.ui.screens.session import MAX_RETRY

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.audio import AudioData
    from parla.event_bus import EventBus
    from parla.ui.screens.session.session_context import SessionContext


class PhaseBViewModel(BaseViewModel):
    """Manages Phase B: progressive feedback display, retry, navigation."""

    feedback_added = Signal(int, str, str, bool)  # index, user_utterance, model_answer, is_acceptable
    feedback_failed = Signal(int, str)  # index, error_message
    item_stocked = Signal(str, bool)  # pattern, is_reappearance
    retry_result = Signal(int, int, bool)  # sentence_index, attempt, correct
    all_feedback_received = Signal()
    navigate_to_next = Signal(bool)  # skip_phase_c
    navigate_to_edit = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        feedback_service: Any,
        practice_service: Any,
        feedback_repo: Any,
        session_context: SessionContext,
    ) -> None:
        super().__init__(event_bus)
        self._feedback_service = feedback_service
        self._practice_service = practice_service
        self._feedback_repo = feedback_repo
        self._ctx = session_context

        self._passage_id: UUID | None = None
        self._sentence_ids: list[UUID] = []
        self._sentence_index: dict[UUID, int] = {}
        self._received_count = 0
        self._retry_counts: dict[UUID, int] = {}
        self._new_item_count = 0

        self._register_sync(FeedbackReady, self._on_feedback_ready)
        self._register_sync(FeedbackFailed, self._on_feedback_failed)
        self._register_sync(LearningItemStocked, self._on_item_stocked)
        self._register_sync(RetryJudged, self._on_retry_judged)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start(self, passage_id: UUID, sentence_ids: list[UUID]) -> None:
        self._passage_id = passage_id
        self._sentence_ids = list(sentence_ids)
        self._sentence_index = {sid: i for i, sid in enumerate(sentence_ids)}
        self._received_count = 0
        self._retry_counts = {}
        self._new_item_count = 0

        # Start TTS generation in background for Phase C
        self._practice_service.request_model_audio(passage_id)

    def retry_sentence(self, sentence_id: UUID, audio: AudioData) -> None:
        count = self._retry_counts.get(sentence_id, 0)
        if count >= MAX_RETRY:
            return
        self._retry_counts[sentence_id] = count + 1
        asyncio.ensure_future(
            self._feedback_service.judge_retry(
                sentence_id=sentence_id,
                attempt=count + 1,
                audio=audio,
            )
        )

    def open_item_edit(self) -> None:
        self.navigate_to_edit.emit()

    def proceed(self) -> None:
        skip = self._practice_service.should_skip(
            new_item_count=self._new_item_count,
            wpm=self._ctx.average_wpm,
            cefr_level="",  # TODO: pass actual CEFR
        )
        self.navigate_to_next.emit(skip)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_feedback_ready(self, event: FeedbackReady) -> None:
        if event.passage_id != self._passage_id:
            return
        idx = self._sentence_index.get(event.sentence_id)
        if idx is None:
            return

        fb = self._feedback_repo.get_feedback_by_sentence(event.sentence_id)
        if fb is None:
            self.feedback_failed.emit(idx, "Feedback data not found")
            return

        self.feedback_added.emit(idx, fb.user_utterance, fb.model_answer, fb.is_acceptable)
        self._received_count += 1
        if self._received_count >= len(self._sentence_ids):
            self.all_feedback_received.emit()

    def _on_feedback_failed(self, event: FeedbackFailed) -> None:
        if event.passage_id != self._passage_id:
            return
        idx = self._sentence_index.get(event.sentence_id)
        if idx is None:
            return
        self.feedback_failed.emit(idx, event.error_message)
        self._received_count += 1
        if self._received_count >= len(self._sentence_ids):
            self.all_feedback_received.emit()

    def _on_item_stocked(self, event: LearningItemStocked) -> None:
        self._new_item_count += 1
        self.item_stocked.emit(event.pattern, event.is_reappearance)

    def _on_retry_judged(self, event: RetryJudged) -> None:
        idx = self._sentence_index.get(event.sentence_id)
        if idx is None:
            return
        self.retry_result.emit(idx, event.attempt, event.correct)
