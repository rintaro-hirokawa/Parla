"""Session coordinator — orchestrates screen transitions during a learning session."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from PySide6.QtCore import QObject, Signal

from parla.domain.events import LearningItemStocked
from parla.ui.audio.recorder import AudioRecorder
from parla.ui.screens.session.session_context import SessionContext

if TYPE_CHECKING:
    from uuid import UUID

    from parla.container import Container
    from parla.domain.passage import Passage
    from parla.domain.session import SessionBlock, SessionMenu, SessionState
    from parla.event_bus import EventBus
    from parla.ui.navigation import NavigationController
    from parla.ui.screens.session.speaking_item import SpeakingItem

from parla.domain.session import BlockType, SessionStatus

logger = structlog.get_logger()


class SessionCoordinator(QObject):
    """Orchestrates session screen transitions and ViewModel lifecycle."""

    session_finished = Signal()

    def __init__(
        self,
        *,
        nav: NavigationController,
        container: Container,
        skip_to_phase: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._nav = nav
        self._c = container
        self._bus: EventBus = container.event_bus
        self._skip_to_phase = skip_to_phase

        # Shared objects — created once per session
        self._recorder = AudioRecorder()
        self._session_context = SessionContext()

        # Session state
        self._session_state: SessionState | None = None
        self._menu: SessionMenu | None = None

        # new_material block tracking
        self._stocked_item_ids: list[UUID] = []
        self._listening_stocked = False
        self._current_passage_index = 0
        self._current_passage_ids: list[UUID] = []
        self._current_passage: Passage | None = None

        # Current ViewModel reference for cleanup
        self._current_vm: QObject | None = None

        # Review batch tracking
        self._review_remaining: list[tuple[UUID, UUID]] = []
        self._review_block_label = ""
        self._review_batch_items: list[tuple[UUID, UUID]] = []
        self._variation_collector: object = None
        self._review_variation_map: dict[UUID, tuple[UUID, UUID]] = {}
        self._review_variation_ids: list[UUID] = []
        self._review_ja_texts: list[str] = []
        self._review_model_answers: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, menu_id: UUID) -> None:
        """Start a new session from a confirmed menu."""
        self._session_state = self._c.session_service.start_session(menu_id)
        self._menu = self._c.session_query.get_menu(menu_id)
        self._nav.enter_session()
        self._show_mic_check()

    def start_resumed(self, session_id: UUID) -> None:
        """Resume an interrupted session (skip mic check)."""
        self._session_state = self._c.session_service.resume_session(session_id)
        self._menu = self._c.session_query.get_menu(self._session_state.menu_id)
        self._nav.enter_session()
        self._session_context.start_timer()
        self._start_current_block()

    def interrupt(self) -> None:
        """Interrupt the active session and clean up."""
        if self._session_state is None:
            return
        self._deactivate_current_vm()
        self._unsubscribe_stocked()
        self._c.session_service.interrupt_session(self._session_state.id)
        self._session_context.stop_timer()
        self._nav.exit_session()
        self.session_finished.emit()

    # ------------------------------------------------------------------
    # Mic check (E1)
    # ------------------------------------------------------------------

    def _show_mic_check(self) -> None:
        from parla.ui.screens.session.mic_check_view import MicCheckView
        from parla.ui.screens.session.mic_check_view_model import MicCheckViewModel

        vm = MicCheckViewModel(recorder=self._recorder)
        view = MicCheckView(vm, recorder=self._recorder)
        vm.proceed.connect(self._on_mic_check_done)
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_mic_check_done(self) -> None:
        self._pop_current()
        self._session_context.start_timer()
        self._start_current_block()

    # ------------------------------------------------------------------
    # Block dispatch
    # ------------------------------------------------------------------

    def _start_current_block(self) -> None:
        block = self._current_block()
        if block is None:
            self._show_session_summary()
            return

        match block.block_type:
            case BlockType.REVIEW:
                items = self._resolve_review_items(list(block.items))
                self._start_review_block(items, "復習")
            case BlockType.NEW_MATERIAL:
                self._start_new_material_block(block)
            case BlockType.CONSOLIDATION:
                self._start_consolidation_block()

    def _current_block(self) -> SessionBlock | None:
        if self._menu is None or self._session_state is None:
            return None
        idx = self._session_state.current_block_index
        if idx >= len(self._menu.blocks):
            return None
        return self._menu.blocks[idx]

    # ------------------------------------------------------------------
    # Review block (E2) — batched recording → feedback flow
    # ------------------------------------------------------------------

    def _start_review_block(
        self, items: list[tuple[UUID, UUID]], block_label: str
    ) -> None:
        self._review_remaining = items
        self._review_block_label = block_label
        self._review_batch_items = []
        self._variation_collector = None
        self._start_next_review_batch()

    def _start_next_review_batch(self) -> None:
        from parla.ui.screens.session.variation_collector import VariationCollector

        batch = self._review_remaining[:5]
        self._review_remaining = self._review_remaining[5:]
        self._review_batch_items = batch

        if not batch:
            self._on_block_complete()
            return

        self._session_context.update_progress(
            self._review_block_label, 0, len(batch)
        )

        # Collect variations for the batch
        self._variation_collector = VariationCollector(
            expected_items=batch,
            review_service=self._c.review_service,
            event_bus=self._bus,
            on_ready=self._on_review_batch_ready,
        )

        # Request all variations
        for item_id, source_id in batch:
            self._c.review_service.request_variation(item_id, source_id)

    def _on_review_batch_ready(
        self,
        items: list[SpeakingItem],
        variation_map: dict[UUID, tuple[UUID, UUID]],
    ) -> None:
        """All variations collected — show recording screen."""
        from parla.ui.screens.session.recording_view import RecordingView
        from parla.ui.screens.session.recording_view_model import RecordingViewModel

        self._review_variation_map = variation_map
        self._review_variation_ids = [item.id for item in items]
        self._review_ja_texts = [item.ja for item in items]
        self._review_model_answers = []

        # Resolve model answers from variations
        for item in items:
            variation = self._c.review_service.get_variation(item.id)
            self._review_model_answers.append(variation.en if variation else "")

        vm = RecordingViewModel()
        vm.load_items(items)
        vm.recording_submitted.connect(self._on_review_item_recorded)
        vm.all_sentences_done.connect(self._on_review_recording_done)

        view = RecordingView(vm, recorder=self._recorder)
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_review_item_recorded(self, variation_id: object, audio: object) -> None:
        """Submit review judgment for a recorded variation."""
        import asyncio
        from datetime import date as date_type

        asyncio.ensure_future(
            self._c.review_service.judge_review(
                variation_id=variation_id,  # type: ignore[arg-type]
                audio=audio,  # type: ignore[arg-type]
                hint_level=0,
                timer_ratio=0.0,
                today=date_type.today(),
            )
        )

    def _on_review_recording_done(self) -> None:
        """All items in batch recorded — show feedback screen."""
        from parla.ui.screens.session import FeedbackMode
        from parla.ui.screens.session.feedback_view import FeedbackView
        from parla.ui.screens.session.feedback_view_model import FeedbackViewModel

        self._pop_current()

        vm = FeedbackViewModel(
            event_bus=self._bus,
            mode=FeedbackMode.REVIEW,
            review_service=self._c.review_service,
            session_context=self._session_context,
        )
        vm.start_for_review(
            self._review_variation_ids,
            self._review_ja_texts,
            self._review_model_answers,
        )
        view = FeedbackView(vm, recorder=self._recorder)
        vm.navigate_to_next.connect(self._on_review_feedback_done)
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_review_feedback_done(self) -> None:
        """Feedback complete for current batch — next batch or block complete."""
        self._deactivate_current_vm()
        self._pop_current()
        if self._review_remaining:
            self._start_next_review_batch()
        else:
            self._advance_block()

    def _resolve_review_items(self, item_ids: list[UUID]) -> list[tuple[UUID, UUID]]:
        """Resolve learning_item_ids to (item_id, source_id) pairs."""
        return self._c.item_query.resolve_review_pairs(item_ids)

    # ------------------------------------------------------------------
    # New material block (Recording → Feedback → RunThrough per passage)
    # ------------------------------------------------------------------

    def _start_new_material_block(self, block: SessionBlock) -> None:
        self._subscribe_stocked()
        self._stocked_item_ids = []
        self._current_passage_ids = list(block.items)
        self._current_passage_index = 0
        self._start_next_passage()

    def _start_next_passage(self) -> None:
        if self._current_passage_index >= len(self._current_passage_ids):
            self._on_block_complete()
            return

        passage_id = self._current_passage_ids[self._current_passage_index]
        passage = self._c.source_query.get_passage(passage_id)
        if passage is None:
            logger.error("passage_not_found", passage_id=str(passage_id))
            self._current_passage_index += 1
            self._start_next_passage()
            return

        self._current_passage = passage

        source = self._c.source_query.get_source(passage.source_id)
        if source is not None:
            self._session_context.set_cefr_level(source.cefr_level)

        if self._skip_to_phase == "run_through":
            self._c.practice_service.request_model_audio(passage.id)
            self._show_run_through(passage.id)
            return

        self._show_recording(passage)

    # --- Recording (E3) ---

    def _show_recording(self, passage: Passage) -> None:
        from parla.ui.screens.session.recording_view import RecordingView
        from parla.ui.screens.session.recording_view_model import RecordingViewModel
        from parla.ui.screens.session.speaking_item import SpeakingItem

        items = [
            SpeakingItem(
                id=s.id,
                ja=s.ja,
                hint1=s.hints.hint1,
                hint2=s.hints.hint2,
            )
            for s in passage.sentences
        ]

        vm = RecordingViewModel()
        vm.load_items(items)
        vm.recording_submitted.connect(
            lambda sid, audio: self._c.feedback_service.record_sentence(
                passage_id=passage.id,
                sentence_id=sid,
                audio=audio,
            )
        )
        view = RecordingView(vm, recorder=self._recorder)
        vm.all_sentences_done.connect(self._on_recording_done)
        self._current_vm = vm
        self._session_context.update_progress(
            "新素材",
            self._current_passage_index + 1,
            len(self._current_passage_ids),
        )
        self._nav.push_screen(view)

    def _on_recording_done(self) -> None:
        self._pop_current()
        self._show_feedback()

    # --- Feedback (E4) ---

    def _show_feedback(self) -> None:
        from parla.ui.screens.session import FeedbackMode
        from parla.ui.screens.session.feedback_view import FeedbackView
        from parla.ui.screens.session.feedback_view_model import FeedbackViewModel

        passage = self._current_passage
        if passage is None:
            return

        vm = FeedbackViewModel(
            event_bus=self._bus,
            mode=FeedbackMode.NEW_MATERIAL,
            feedback_service=self._c.feedback_service,
            practice_service=self._c.practice_service,
            item_query=self._c.item_query,
            session_context=self._session_context,
        )
        vm.start_for_passage(
            passage.id,
            [s.id for s in passage.sentences],
            [s.ja for s in passage.sentences],
        )
        view = FeedbackView(vm, recorder=self._recorder)
        vm.navigate_to_next.connect(self._on_feedback_done)
        vm.navigate_to_edit.connect(self._show_item_edit)
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_feedback_done(self) -> None:
        passage_id = self._current_passage.id if self._current_passage else None
        self._deactivate_current_vm()
        self._pop_current()
        if passage_id is None:
            return
        self._show_run_through(passage_id)

    # --- Run-through (E6) ---

    def _show_run_through(self, passage_id: UUID) -> None:
        from parla.ui.audio.player import AudioPlayer
        from parla.ui.screens.session.run_through_view import RunThroughView
        from parla.ui.screens.session.run_through_view_model import RunThroughViewModel

        vm = RunThroughViewModel(
            event_bus=self._bus,
            practice_service=self._c.practice_service,
            audio_player=AudioPlayer(),
            recorder=self._recorder,
            session_context=self._session_context,
            session_query_service=self._c.session_query,
        )
        ja_texts = tuple(s.ja for s in self._current_passage.sentences) if self._current_passage else ()
        vm.start(passage_id, sentence_ja_texts=ja_texts)
        view = RunThroughView(vm, recorder=self._recorder)
        vm.run_through_complete.connect(lambda: self._on_run_through_done(passage_id))
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_run_through_done(self, passage_id: UUID) -> None:
        self._deactivate_current_vm()
        self._pop_current()
        if self._current_passage_index < len(self._current_passage_ids) - 1:
            self._current_passage_index += 1
            self._start_next_passage()
        else:
            self._advance_block()

    # ------------------------------------------------------------------
    # Consolidation block
    # ------------------------------------------------------------------

    def _start_consolidation_block(self) -> None:
        self._unsubscribe_stocked()
        if not self._stocked_item_ids:
            self._on_block_complete()
            return
        items = self._resolve_review_items(self._stocked_item_ids)
        if not items:
            self._on_block_complete()
            return
        self._start_review_block(items, "定着")

    # ------------------------------------------------------------------
    # Block completion
    # ------------------------------------------------------------------

    def _on_block_complete(self) -> None:
        self._deactivate_current_vm()
        self._pop_current()
        self._advance_block()

    def _advance_block(self) -> None:
        """Advance to the next block (or session summary)."""
        if self._session_state is None:
            return
        state = self._c.session_service.advance_block(self._session_state.id)
        self._session_state = state

        if state.status == SessionStatus.COMPLETED:
            self._show_session_summary()
        else:
            self._start_current_block()

    # ------------------------------------------------------------------
    # Session summary (F1)
    # ------------------------------------------------------------------

    def _show_session_summary(self) -> None:
        from parla.ui.screens.session.session_summary_view import SessionSummaryView
        from parla.ui.screens.session.session_summary_view_model import (
            SessionSummaryViewModel,
        )

        self._session_context.stop_timer()
        vm = SessionSummaryViewModel(session_query_service=self._c.session_query)
        view = SessionSummaryView(vm)
        if self._session_state is not None:
            vm.load(self._session_state.id)
        vm.navigate_to_menu.connect(self._on_session_end)
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_session_end(self) -> None:
        self._deactivate_current_vm()
        self._nav.exit_session()
        self.session_finished.emit()

    # ------------------------------------------------------------------
    # Item edit modal (E5)
    # ------------------------------------------------------------------

    def _show_item_edit(self) -> None:
        from parla.ui.screens.session.feedback_view_model import FeedbackViewModel
        from parla.ui.screens.session.item_edit_view import ItemEditView
        from parla.ui.screens.session.item_edit_view_model import ItemEditViewModel

        if not isinstance(self._current_vm, FeedbackViewModel):
            return

        vm = ItemEditViewModel(item_query=self._c.item_query)
        vm.load_items(self._current_vm.current_sentence_id)
        view = ItemEditView(vm)
        view.exec()

    # ------------------------------------------------------------------
    # LearningItemStocked subscription
    # ------------------------------------------------------------------

    def _subscribe_stocked(self) -> None:
        if not self._listening_stocked:
            self._bus.on_sync(LearningItemStocked)(self._on_item_stocked)
            self._listening_stocked = True

    def _unsubscribe_stocked(self) -> None:
        if self._listening_stocked:
            self._bus.off_sync(LearningItemStocked, self._on_item_stocked)
            self._listening_stocked = False

    def _on_item_stocked(self, event: LearningItemStocked) -> None:
        self._stocked_item_ids.append(event.item_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _deactivate_current_vm(self) -> None:
        from parla.ui.base_view_model import BaseViewModel

        if isinstance(self._current_vm, BaseViewModel) and self._current_vm.is_active:
            self._current_vm.deactivate()

    def _pop_current(self) -> None:
        self._nav.pop_screen()
        self._current_vm = None
