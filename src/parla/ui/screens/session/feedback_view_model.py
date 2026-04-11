"""ViewModel for feedback screen (SCREEN-E4).

Supports two modes:
- NEW_MATERIAL: subscribes to FeedbackReady/Failed, LearningItemStocked, RetryJudged
- REVIEW: subscribes to ReviewAnswered, ReviewRetryJudged
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
    ReviewAnswered,
    ReviewRetryJudged,
)
from parla.ui.base_view_model import BaseViewModel
from parla.ui.screens.session import FeedbackMode

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.audio import AudioData
    from parla.event_bus import EventBus
    from parla.services.feedback_service import FeedbackService
    from parla.services.learning_item_query_service import LearningItemQueryService
    from parla.services.practice_service import PracticeService
    from parla.services.review_service import ReviewService
    from parla.ui.screens.session.session_context import SessionContext


class FeedbackViewModel(BaseViewModel):
    """Manages one-sentence-at-a-time feedback display, retry, navigation."""

    feedback_added = Signal(int, str, str, bool)  # index, user_utterance, model_answer, is_acceptable
    feedback_failed = Signal(int, str)  # index, error_message
    item_stocked = Signal(int, str, str, bool)  # sentence_index, pattern, explanation, is_reappearance
    retry_result = Signal(int, int, bool)  # sentence_index, attempt, correct
    all_feedback_received = Signal()
    navigate_to_next = Signal()
    navigate_to_edit = Signal()
    error = Signal(str)

    current_sentence_loading = Signal(int)  # index — feedback not yet arrived
    current_sentence_changed = Signal(int, int)  # (current_index, total)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        mode: FeedbackMode = FeedbackMode.NEW_MATERIAL,
        feedback_service: FeedbackService | None = None,
        practice_service: PracticeService | None = None,
        item_query: LearningItemQueryService | None = None,
        review_service: ReviewService | None = None,
        session_context: SessionContext | None = None,
    ) -> None:
        super().__init__(event_bus)
        self._mode = mode
        self._feedback_service = feedback_service
        self._practice_service = practice_service
        self._item_query = item_query
        self._review_service = review_service
        self._ctx = session_context

        self._passage_id: UUID | None = None
        self._item_ids: list[UUID] = []  # sentence_ids or variation_ids
        self._item_index: dict[UUID, int] = {}
        self._ja_texts: list[str] = []
        self._model_answers: dict[int, str] = {}  # pre-set for review mode
        self._received_count = 0
        self._retry_counts: dict[UUID, int] = {}
        self._new_item_count = 0

        self._current_index: int = 0
        self._feedback_buffer: dict[int, tuple[str, str, bool]] = {}
        self._error_buffer: dict[int, str] = {}
        self._passed: set[int] = set()
        self._seen_item_ids: set[UUID] = set()
        self._items_buffer: dict[int, list[tuple[str, str, bool]]] = {}

        if mode == FeedbackMode.NEW_MATERIAL:
            self._register_sync(FeedbackReady, self._on_feedback_ready)
            self._register_sync(FeedbackFailed, self._on_feedback_failed)
            self._register_sync(LearningItemStocked, self._on_item_stocked)
            self._register_sync(RetryJudged, self._on_retry_judged)
        else:
            self._register_sync(ReviewAnswered, self._on_review_answered)
            self._register_sync(ReviewRetryJudged, self._on_review_retry_judged)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> FeedbackMode:
        return self._mode

    @property
    def sentence_count(self) -> int:
        return len(self._item_ids)

    @property
    def is_current_passed(self) -> bool:
        return self._current_index in self._passed

    @property
    def current_sentence_id(self) -> UUID:
        return self._item_ids[self._current_index]

    @property
    def current_ja(self) -> str:
        if 0 <= self._current_index < len(self._ja_texts):
            return self._ja_texts[self._current_index]
        return ""

    @property
    def show_items(self) -> bool:
        return self._mode == FeedbackMode.NEW_MATERIAL

    # ------------------------------------------------------------------
    # Start methods
    # ------------------------------------------------------------------

    def start_for_passage(
        self, passage_id: UUID, sentence_ids: list[UUID], ja_texts: list[str]
    ) -> None:
        """Start feedback for new material (passage sentences)."""
        self._passage_id = passage_id
        self._item_ids = list(sentence_ids)
        self._item_index = {sid: i for i, sid in enumerate(sentence_ids)}
        self._ja_texts = list(ja_texts)
        self._reset_state()

        # Pre-fill buffers with data already generated during recording
        if self._feedback_service is not None:
            for i, sid in enumerate(sentence_ids):
                fb = self._feedback_service.get_feedback_by_sentence(sid)
                if fb is not None:
                    self._feedback_buffer[i] = (fb.user_utterance, fb.model_answer, fb.is_acceptable)
                    self._received_count += 1
                    if fb.is_acceptable:
                        self._passed.add(i)

                if self._item_query is not None:
                    for item in self._item_query.get_items_by_sentence(sid):
                        if item.status == "auto_stocked" and item.id not in self._seen_item_ids:
                            self._seen_item_ids.add(item.id)
                            self._new_item_count += 1
                            self._items_buffer.setdefault(i, []).append(
                                (item.pattern, item.explanation, item.is_reappearance)
                            )

        # Start TTS generation in background for run-through
        if self._practice_service is not None:
            self._practice_service.request_model_audio(passage_id)

    def start_for_review(
        self,
        variation_ids: list[UUID],
        ja_texts: list[str],
        model_answers: list[str],
    ) -> None:
        """Start feedback for review (variations)."""
        self._passage_id = None
        self._item_ids = list(variation_ids)
        self._item_index = {vid: i for i, vid in enumerate(variation_ids)}
        self._ja_texts = list(ja_texts)
        self._model_answers = {i: ans for i, ans in enumerate(model_answers)}
        self._reset_state()

    def _reset_state(self) -> None:
        self._received_count = 0
        self._retry_counts = {}
        self._new_item_count = 0
        self._current_index = 0
        self._feedback_buffer = {}
        self._error_buffer = {}
        self._passed = set()
        self._seen_item_ids = set()
        self._items_buffer = {}

    # ------------------------------------------------------------------
    # Backward-compatible start (for coordinator)
    # ------------------------------------------------------------------

    def start(self, passage_id: UUID, sentence_ids: list[UUID]) -> None:
        """Legacy start for new material."""
        ja_texts = [""] * len(sentence_ids)
        self.start_for_passage(passage_id, sentence_ids, ja_texts)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def show_initial(self) -> None:
        """Emit signals for the first sentence. Called by the View after connection."""
        self.current_sentence_changed.emit(0, len(self._item_ids))
        self._show_current()

    def advance_sentence(self) -> None:
        """Move to the next sentence, or proceed to next phase if at end."""
        if not self.is_current_passed:
            return
        if self._current_index >= len(self._item_ids) - 1:
            self.proceed()
            return
        self._current_index += 1
        self.current_sentence_changed.emit(self._current_index, len(self._item_ids))
        self._show_current()

    def retry_current(self, audio: AudioData) -> None:
        """Retry the currently displayed sentence."""
        sid = self._item_ids[self._current_index]
        self.retry_sentence(sid, audio)

    def retry_sentence(self, sentence_id: UUID, audio: AudioData) -> None:
        count = self._retry_counts.get(sentence_id, 0)
        self._retry_counts[sentence_id] = count + 1

        if self._mode == FeedbackMode.NEW_MATERIAL:
            if self._feedback_service is not None:
                asyncio.ensure_future(
                    self._feedback_service.judge_retry(
                        sentence_id=sentence_id,
                        attempt=count + 1,
                        audio=audio,
                    )
                )
        else:
            if self._review_service is not None:
                asyncio.ensure_future(
                    self._review_service.judge_review_retry(
                        variation_id=sentence_id,
                        attempt_number=count + 1,
                        audio=audio,
                    )
                )

    def open_item_edit(self) -> None:
        self.navigate_to_edit.emit()

    def proceed(self) -> None:
        self.navigate_to_next.emit()

    # ------------------------------------------------------------------
    # Event handlers — NEW_MATERIAL mode
    # ------------------------------------------------------------------

    def _on_feedback_ready(self, event: FeedbackReady) -> None:
        if event.passage_id != self._passage_id:
            return
        idx = self._item_index.get(event.sentence_id)
        if idx is None:
            return
        if idx in self._feedback_buffer:
            return

        if self._feedback_service is None:
            return
        fb = self._feedback_service.get_feedback_by_sentence(event.sentence_id)
        if fb is None:
            self._error_buffer[idx] = "Feedback data not found"
            if idx == self._current_index:
                self.feedback_failed.emit(idx, "Feedback data not found")
            self._mark_received()
            return

        self._feedback_buffer[idx] = (fb.user_utterance, fb.model_answer, fb.is_acceptable)
        if fb.is_acceptable:
            self._passed.add(idx)
        self._mark_received()

        if idx == self._current_index:
            self.feedback_added.emit(idx, fb.user_utterance, fb.model_answer, fb.is_acceptable)
            for pattern, explanation, is_reapp in self._items_buffer.get(idx, []):
                self.item_stocked.emit(idx, pattern, explanation, is_reapp)

    def _on_feedback_failed(self, event: FeedbackFailed) -> None:
        if event.passage_id != self._passage_id:
            return
        idx = self._item_index.get(event.sentence_id)
        if idx is None:
            return

        self._error_buffer[idx] = event.error_message
        self._mark_received()

        if idx == self._current_index:
            self.feedback_failed.emit(idx, event.error_message)

    def _on_item_stocked(self, event: LearningItemStocked) -> None:
        if event.item_id in self._seen_item_ids:
            return
        self._seen_item_ids.add(event.item_id)
        self._new_item_count += 1

        if self._item_query is None:
            return
        item = self._item_query.get_item(event.item_id)
        explanation = item.explanation if item else ""
        idx = self._item_index.get(item.source_sentence_id) if item else None

        if idx is not None:
            self._items_buffer.setdefault(idx, []).append(
                (event.pattern, explanation, event.is_reappearance)
            )
            if idx == self._current_index:
                self.item_stocked.emit(idx, event.pattern, explanation, event.is_reappearance)

    def _on_retry_judged(self, event: RetryJudged) -> None:
        idx = self._item_index.get(event.sentence_id)
        if idx is None:
            return
        if event.correct:
            self._passed.add(idx)
        self.retry_result.emit(idx, event.attempt, event.correct)

    # ------------------------------------------------------------------
    # Event handlers — REVIEW mode
    # ------------------------------------------------------------------

    def _on_review_answered(self, event: ReviewAnswered) -> None:
        idx = self._item_index.get(event.variation_id)
        if idx is None:
            return
        if idx in self._feedback_buffer:
            return

        model_answer = self._model_answers.get(idx, "")
        # In review mode, user utterance is not available; use empty string
        self._feedback_buffer[idx] = ("", model_answer, event.correct)
        if event.correct:
            self._passed.add(idx)
        self._mark_received()

        if idx == self._current_index:
            self.feedback_added.emit(idx, "", model_answer, event.correct)

    def _on_review_retry_judged(self, event: ReviewRetryJudged) -> None:
        idx = self._item_index.get(event.variation_id)
        if idx is None:
            return
        if event.correct:
            self._passed.add(idx)
        self.retry_result.emit(idx, event.attempt, event.correct)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _show_current(self) -> None:
        """Emit signal for the current sentence: feedback, error, or loading."""
        idx = self._current_index
        if idx in self._feedback_buffer:
            u, m, a = self._feedback_buffer[idx]
            self.feedback_added.emit(idx, u, m, a)
            for pattern, explanation, is_reapp in self._items_buffer.get(idx, []):
                self.item_stocked.emit(idx, pattern, explanation, is_reapp)
        elif idx in self._error_buffer:
            self.feedback_failed.emit(idx, self._error_buffer[idx])
        else:
            self.current_sentence_loading.emit(idx)

    def _mark_received(self) -> None:
        self._received_count += 1
        if self._received_count >= len(self._item_ids):
            self.all_feedback_received.emit()
