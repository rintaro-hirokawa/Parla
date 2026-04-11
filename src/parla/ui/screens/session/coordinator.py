"""Session coordinator — orchestrates screen transitions during a learning session."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from PySide6.QtCore import QObject, Signal

from parla.domain.events import LearningItemStocked
from parla.ui.audio.recorder import AudioRecorder
from parla.ui.screens.session.session_context import SessionContext

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.passage import Passage
    from parla.domain.session import SessionBlock, SessionMenu, SessionState
    from parla.event_bus import EventBus
    from parla.ui.navigation import NavigationController

logger = structlog.get_logger()


class SessionCoordinator(QObject):
    """Orchestrates session screen transitions and ViewModel lifecycle."""

    session_finished = Signal()

    def __init__(
        self,
        *,
        nav: NavigationController,
        container: Any,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._nav = nav
        self._c = container
        self._bus: EventBus = container.event_bus

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, menu_id: UUID) -> None:
        """Start a new session from a confirmed menu."""
        self._session_state = self._c.session_service.start_session(menu_id)
        self._menu = self._c.session_repo.get_menu(menu_id)
        self._nav.enter_session()
        self._show_mic_check()

    def start_resumed(self, session_id: UUID) -> None:
        """Resume an interrupted session (skip mic check)."""
        self._session_state = self._c.session_service.resume_session(session_id)
        self._menu = self._c.session_repo.get_menu(self._session_state.menu_id)
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
            case "review":
                items = self._resolve_review_items(list(block.items))
                self._start_review_block(items, "復習")
            case "new_material":
                self._start_new_material_block(block)
            case "consolidation":
                self._start_consolidation_block()

    def _current_block(self) -> SessionBlock | None:
        if self._menu is None or self._session_state is None:
            return None
        idx = self._session_state.current_block_index
        if idx >= len(self._menu.blocks):
            return None
        return self._menu.blocks[idx]

    # ------------------------------------------------------------------
    # Review block (E2) — used for both review and consolidation
    # ------------------------------------------------------------------

    def _start_review_block(
        self, items: list[tuple[UUID, UUID]], block_label: str
    ) -> None:
        from parla.ui.screens.session.review_view import ReviewView
        from parla.ui.screens.session.review_view_model import ReviewViewModel

        vm = ReviewViewModel(
            event_bus=self._bus,
            review_service=self._c.review_service,
            variation_repo=self._c.variation_repo,
            session_context=self._session_context,
        )
        view = ReviewView(vm, recorder=self._recorder)
        vm.all_done.connect(self._on_block_complete)
        self._session_context.update_progress(block_label, 0, len(items))
        vm.start_review(items)
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)
        vm.request_next()

    def _resolve_review_items(self, item_ids: list[UUID]) -> list[tuple[UUID, UUID]]:
        """Resolve learning_item_ids to (item_id, source_id) pairs."""
        pairs: list[tuple[UUID, UUID]] = []
        for item_id in item_ids:
            item = self._c.item_repo.get_item(item_id)
            if item is None:
                logger.warning("item_not_found", item_id=str(item_id))
                continue
            source = self._c.source_repo.get_source_by_sentence_id(
                item.source_sentence_id
            )
            if source is None:
                logger.warning("source_not_found", item_id=str(item_id))
                continue
            pairs.append((item_id, source.id))
        return pairs

    # ------------------------------------------------------------------
    # New material block (E3 → E4 → E6 → E9 per passage)
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
        passage = self._c.source_repo.get_passage(passage_id)
        if passage is None:
            logger.error("passage_not_found", passage_id=str(passage_id))
            self._current_passage_index += 1
            self._start_next_passage()
            return

        self._current_passage = passage

        source = self._c.source_repo.get_source(passage.source_id)
        if source is not None:
            self._session_context.set_cefr_level(source.cefr_level)

        self._show_phase_a(passage)

    # --- Phase A (E3) ---

    def _show_phase_a(self, passage: Passage) -> None:
        from parla.ui.screens.session.phase_a_view import PhaseAView
        from parla.ui.screens.session.phase_a_view_model import PhaseAViewModel

        vm = PhaseAViewModel(
            feedback_service=self._c.feedback_service,
        )
        vm.load_passage(passage)
        view = PhaseAView(vm, recorder=self._recorder)
        vm.all_sentences_done.connect(self._on_phase_a_done)
        self._current_vm = vm
        self._session_context.update_progress(
            "新素材",
            self._current_passage_index + 1,
            len(self._current_passage_ids),
        )
        self._nav.push_screen(view)

    def _on_phase_a_done(self) -> None:
        self._pop_current()
        self._show_phase_b()

    # --- Phase B (E4) ---

    def _show_phase_b(self) -> None:
        from parla.ui.screens.session.phase_b_view import PhaseBView
        from parla.ui.screens.session.phase_b_view_model import PhaseBViewModel

        passage = self._current_passage
        if passage is None:
            return

        vm = PhaseBViewModel(
            event_bus=self._bus,
            feedback_service=self._c.feedback_service,
            practice_service=self._c.practice_service,
            feedback_repo=self._c.feedback_repo,
            item_repo=self._c.item_repo,
            session_context=self._session_context,
        )
        vm.start(passage.id, [s.id for s in passage.sentences])
        view = PhaseBView(vm, recorder=self._recorder)
        vm.navigate_to_next.connect(self._on_phase_b_done)
        vm.navigate_to_edit.connect(self._show_item_edit)
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_phase_b_done(self, skip_phase_c: bool) -> None:
        passage_id = self._current_passage.id if self._current_passage else None
        self._deactivate_current_vm()
        self._pop_current()
        if passage_id is None:
            return
        if skip_phase_c:
            self._show_passage_summary(passage_id)
        else:
            self._show_phase_c(passage_id)

    # --- Phase C (E6) ---

    def _show_phase_c(self, passage_id: UUID) -> None:
        from parla.ui.audio.player import AudioPlayer
        from parla.ui.screens.session.phase_c_view import PhaseCView
        from parla.ui.screens.session.phase_c_view_model import PhaseCViewModel

        vm = PhaseCViewModel(
            event_bus=self._bus,
            practice_service=self._c.practice_service,
            practice_repo=self._c.practice_repo,
            audio_player=AudioPlayer(),
            session_context=self._session_context,
        )
        vm.start(passage_id)
        view = PhaseCView(vm, recorder=self._recorder)
        vm.phase_complete.connect(lambda: self._on_phase_c_done(passage_id))
        vm.activate()
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_phase_c_done(self, passage_id: UUID) -> None:
        self._deactivate_current_vm()
        self._pop_current()
        self._show_passage_summary(passage_id)

    # --- Passage summary (E9) ---

    def _show_passage_summary(self, passage_id: UUID) -> None:
        from parla.ui.screens.session.passage_summary_view import PassageSummaryView
        from parla.ui.screens.session.passage_summary_view_model import (
            PassageSummaryViewModel,
        )

        vm = PassageSummaryViewModel(session_query_service=self._c.session_query)
        has_more = self._current_passage_index < len(self._current_passage_ids) - 1
        vm.set_has_more_passages(has_more)
        vm.load(passage_id)
        view = PassageSummaryView(vm)
        vm.navigate_next_passage.connect(self._on_next_passage)
        vm.navigate_block_complete.connect(self._on_block_complete)
        self._current_vm = vm
        self._nav.push_screen(view)

    def _on_next_passage(self) -> None:
        self._pop_current()
        self._current_passage_index += 1
        self._start_next_passage()

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

        if self._session_state is None:
            return
        state = self._c.session_service.advance_block(self._session_state.id)
        self._session_state = state

        if state.status == "completed":
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
        if self._session_state is not None:
            vm.load(self._session_state.id)
        view = SessionSummaryView(vm)
        vm.navigate_to_menu.connect(self._show_tomorrow_menu)
        self._current_vm = vm
        self._nav.push_screen(view)

    # ------------------------------------------------------------------
    # Tomorrow menu (F2)
    # ------------------------------------------------------------------

    def _show_tomorrow_menu(self) -> None:
        from parla.ui.screens.session.tomorrow_menu_view import TomorrowMenuView
        from parla.ui.screens.session.tomorrow_menu_view_model import (
            TomorrowMenuViewModel,
        )

        self._pop_current()

        source_id = self._menu.source_id if self._menu else None
        if source_id is None:
            sources = self._c.session_service.get_active_sources()
            source_id = sources[0].id if sources else None

        today = date.today()
        tomorrow = today + timedelta(days=1)
        if source_id is not None:
            new_menu = self._c.session_service.compose_menu(tomorrow, source_id, today)
            menu_id = new_menu.id
        else:
            menu_id = None

        vm = TomorrowMenuViewModel(
            event_bus=self._bus,
            session_service=self._c.session_service,
            session_query_service=self._c.session_query,
            session_context=self._session_context,
        )
        if menu_id is not None:
            vm.load(menu_id)
        view = TomorrowMenuView(vm)
        vm.confirmed.connect(self._on_session_end)
        vm.activate()
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
        from parla.ui.screens.session.item_edit_view import ItemEditView
        from parla.ui.screens.session.item_edit_view_model import ItemEditViewModel
        from parla.ui.screens.session.phase_b_view_model import PhaseBViewModel

        if not isinstance(self._current_vm, PhaseBViewModel):
            return

        vm = ItemEditViewModel(item_repo=self._c.item_repo)
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
