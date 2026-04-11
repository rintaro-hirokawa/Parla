"""ViewModel for the Block 1/3 review screen (SCREEN-E2)."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from parla.domain.events import (
    ReviewAnswered,
    ReviewRetryJudged,
    VariationGenerationFailed,
    VariationReady,
)
from parla.ui.base_view_model import BaseViewModel
from parla.ui.screens.session import MAX_RETRY

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.audio import AudioData
    from parla.domain.variation import Variation
    from parla.event_bus import EventBus
    from parla.services.review_service import ReviewService
    from parla.ui.screens.session.session_context import SessionContext


class ReviewViewModel(BaseViewModel):
    """Manages the review flow: variation request → question → judge → advance."""

    question_ready = Signal()
    hint_revealed = Signal(int, str)  # hint_level, hint_text
    result_ready = Signal(bool, str)  # correct, model_answer
    retry_result = Signal(int, bool)  # attempt, correct
    all_done = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        review_service: ReviewService,
        session_context: SessionContext,
    ) -> None:
        super().__init__(event_bus)
        self._review_service = review_service
        self._ctx = session_context

        self._items: list[tuple[UUID, UUID]] = []  # (item_id, source_id)
        self._current_index = -1
        self._current_variation: Variation | None = None
        self._hint_level = 0
        self._attempt_count = 0
        self._waiting_for_item_id: UUID | None = None

        self._register_sync(VariationReady, self._on_variation_ready)
        self._register_sync(VariationGenerationFailed, self._on_variation_failed)
        self._register_sync(ReviewAnswered, self._on_review_answered)
        self._register_sync(ReviewRetryJudged, self._on_retry_judged)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_ja(self) -> str:
        return self._current_variation.ja if self._current_variation else ""

    @property
    def current_en(self) -> str:
        return self._current_variation.en if self._current_variation else ""

    @property
    def hint_level(self) -> int:
        return self._hint_level

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_items(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start_review(self, items: list[tuple[UUID, UUID]]) -> None:
        """Initialize with list of (learning_item_id, source_id) pairs."""
        self._items = list(items)
        self._current_index = -1

    def request_next(self) -> None:
        """Request the next review item's variation."""
        self._current_index += 1
        if self._current_index >= len(self._items):
            self.all_done.emit()
            return

        self._current_variation = None
        self._hint_level = 0
        self._attempt_count = 0

        item_id, source_id = self._items[self._current_index]
        self._waiting_for_item_id = item_id
        self._review_service.request_variation(item_id, source_id)
        self._ctx.update_progress(
            self._ctx.block_name,
            self._current_index + 1,
            len(self._items),
        )

    def reveal_hint(self) -> None:
        """Reveal the next hint level (max 2)."""
        if self._current_variation is None or self._hint_level >= 2:
            return
        self._hint_level += 1
        text = (
            self._current_variation.hint1
            if self._hint_level == 1
            else self._current_variation.hint2
        )
        self.hint_revealed.emit(self._hint_level, text)

    def submit_recording(self, audio: AudioData) -> None:
        """Submit initial recording for review judgment."""
        if self._current_variation is None:
            return
        self._attempt_count = 1
        asyncio.ensure_future(
            self._review_service.judge_review(
                variation_id=self._current_variation.id,
                audio=audio,
                hint_level=self._hint_level,
                timer_ratio=0.0,  # TODO: integrate with timer
                today=date.today(),
            )
        )

    def submit_retry(self, audio: AudioData) -> None:
        """Submit a retry recording."""
        if self._current_variation is None:
            return
        if self._attempt_count >= MAX_RETRY:
            return
        self._attempt_count += 1
        asyncio.ensure_future(
            self._review_service.judge_review_retry(
                variation_id=self._current_variation.id,
                attempt_number=self._attempt_count,
                audio=audio,
            )
        )

    def advance(self) -> None:
        """Advance to next item. Called by View after auto-advance delay."""
        self.request_next()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_variation_ready(self, event: VariationReady) -> None:
        import structlog
        _logger = structlog.get_logger()
        _logger.info(
            "review_vm_variation_ready",
            event_item_id=str(event.learning_item_id),
            waiting_for=str(self._waiting_for_item_id),
            active=self._active,
        )
        if event.learning_item_id != self._waiting_for_item_id:
            _logger.warning("review_vm_id_mismatch")
            return
        variation = self._review_service.get_variation(event.variation_id)
        if variation is None:
            self.error.emit(f"Variation not found: {event.variation_id}")
            return
        _logger.info("review_vm_question_ready", ja=variation.ja[:30])
        self._current_variation = variation
        self.question_ready.emit()

    def _on_variation_failed(self, event: VariationGenerationFailed) -> None:
        if event.learning_item_id != self._waiting_for_item_id:
            return
        self.error.emit(event.error_message)

    def _on_review_answered(self, event: ReviewAnswered) -> None:
        if self._current_variation is None:
            return
        if event.variation_id != self._current_variation.id:
            return
        self.result_ready.emit(event.correct, self._current_variation.en)

    def _on_retry_judged(self, event: ReviewRetryJudged) -> None:
        if self._current_variation is None:
            return
        if event.variation_id != self._current_variation.id:
            return
        self.retry_result.emit(event.attempt, event.correct)
