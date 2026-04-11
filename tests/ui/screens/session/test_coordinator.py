"""Tests for SessionCoordinator."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from parla.domain.events import LearningItemStocked
from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.session import SessionBlock, SessionMenu, SessionState
from parla.domain.source import Source
from parla.event_bus import EventBus
from parla.ui.screens.session.coordinator import SessionCoordinator

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


# ======================================================================
# Helpers
# ======================================================================


def _make_passage(passage_id: UUID | None = None, source_id: UUID | None = None) -> Passage:
    sid = source_id or uuid4()
    return Passage(
        id=passage_id or uuid4(),
        source_id=sid,
        order=0,
        topic="Test topic",
        passage_type="dialogue",
        sentences=(
            Sentence(order=0, ja="テスト文1", en="Test sentence 1", hints=Hint(hint1="h1", hint2="h2")),
            Sentence(order=1, ja="テスト文2", en="Test sentence 2", hints=Hint(hint1="h1", hint2="h2")),
        ),
    )


def _make_item(item_id: UUID | None = None, sentence_id: UUID | None = None) -> LearningItem:
    return LearningItem(
        id=item_id or uuid4(),
        pattern="test pattern",
        explanation="test explanation",
        category="語彙",
        priority=4,
        source_sentence_id=sentence_id or uuid4(),
        status="auto_stocked",
    )


def _make_source(source_id: UUID | None = None) -> Source:
    return Source(
        id=source_id or uuid4(),
        title="Test Source",
        text="x" * 100,
        cefr_level="B1",
        english_variant="American",
    )


def _make_menu(
    *,
    pattern: str = "a",
    blocks: tuple[SessionBlock, ...] | None = None,
    source_id: UUID | None = None,
    confirmed: bool = True,
) -> SessionMenu:
    if blocks is None:
        blocks = (
            SessionBlock(block_type="review", items=(uuid4(),), estimated_minutes=2.0),
            SessionBlock(block_type="new_material", items=(uuid4(),), estimated_minutes=10.0),
            SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
        )
    return SessionMenu(
        target_date=date.today(),
        pattern=pattern,
        blocks=blocks,
        source_id=source_id or uuid4(),
        confirmed=confirmed,
    )


def _make_state(
    menu_id: UUID,
    *,
    status: str = "in_progress",
    block_index: int = 0,
) -> SessionState:
    return SessionState(
        menu_id=menu_id,
        status=status,
        current_block_index=block_index,
        started_at=datetime.now(),
    )


# ======================================================================
# Fakes
# ======================================================================


class FakeNavigationController:
    """Records push/pop/enter/exit calls."""

    def __init__(self) -> None:
        self.pushed: list[QWidget] = []
        self.popped_count = 0
        self.entered_session = False
        self.exited_session = False

    def enter_session(self) -> None:
        self.entered_session = True

    def exit_session(self) -> None:
        self.exited_session = True

    def push_screen(self, widget: QWidget) -> None:
        self.pushed.append(widget)

    def pop_screen(self) -> QWidget | None:
        self.popped_count += 1
        return None


class FakeSessionService:
    """Records session lifecycle calls."""

    def __init__(self, menu: SessionMenu) -> None:
        self._menu = menu
        self._state: SessionState | None = None
        self._advance_count = 0
        self.start_session_calls: list[UUID] = []
        self.advance_block_calls: list[UUID] = []
        self.interrupt_calls: list[UUID] = []
        self.resume_calls: list[UUID] = []
        self.compose_menu_calls: list[dict] = []

    def start_session(self, menu_id: UUID) -> SessionState:
        self.start_session_calls.append(menu_id)
        self._state = _make_state(menu_id)
        return self._state

    def advance_block(self, session_id: UUID) -> SessionState:
        self.advance_block_calls.append(session_id)
        if self._state is None:
            msg = "No active state"
            raise ValueError(msg)
        self._advance_count += 1
        next_index = self._state.current_block_index + 1
        if next_index >= len(self._menu.blocks):
            self._state = self._state.model_copy(
                update={"status": "completed", "completed_at": datetime.now()}
            )
        else:
            self._state = self._state.model_copy(
                update={"current_block_index": next_index}
            )
        return self._state

    def interrupt_session(self, session_id: UUID) -> None:
        self.interrupt_calls.append(session_id)

    def resume_session(self, session_id: UUID) -> SessionState:
        self.resume_calls.append(session_id)
        if self._state is None:
            self._state = _make_state(self._menu.id, block_index=0)
        self._state = self._state.model_copy(update={"status": "in_progress"})
        return self._state

    def get_active_sources(self) -> list[Source]:
        return [_make_source(self._menu.source_id)]

    def compose_menu(self, target_date: date, source_id: UUID, today: date) -> SessionMenu:
        self.compose_menu_calls.append({"target_date": target_date, "source_id": source_id})
        return self._menu


class FakeSessionRepo:
    """Returns preset menu."""

    def __init__(self, menu: SessionMenu) -> None:
        self._menu = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menu if menu_id == self._menu.id else None


class FakeSourceRepo:
    """Returns preset passages and sources."""

    def __init__(self) -> None:
        self._passages: dict[UUID, Passage] = {}
        self._sources: dict[UUID, Source] = {}
        self._sources_by_sentence: dict[UUID, Source] = {}

    def add_passage(self, p: Passage) -> None:
        self._passages[p.id] = p

    def add_source(self, s: Source) -> None:
        self._sources[s.id] = s

    def add_source_for_sentence(self, sentence_id: UUID, source: Source) -> None:
        self._sources_by_sentence[sentence_id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def get_passage(self, passage_id: UUID) -> Passage | None:
        return self._passages.get(passage_id)

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        return self._sources_by_sentence.get(sentence_id)


class FakeItemRepo:
    """Returns preset items."""

    def __init__(self) -> None:
        self._items: dict[UUID, LearningItem] = {}

    def add_item(self, item: LearningItem) -> None:
        self._items[item.id] = item

    def get_item(self, item_id: UUID) -> LearningItem | None:
        return self._items.get(item_id)

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        return [i for i in self._items.values() if i.source_sentence_id == sentence_id]


class FakeReviewService:
    def request_variation(self, item_id: UUID, source_id: UUID) -> None:
        pass

    def get_variation(self, variation_id: UUID) -> None:
        return None

    async def judge_review(self, **kwargs: Any) -> None:
        pass

    async def judge_review_retry(self, **kwargs: Any) -> None:
        pass


class FakeFeedbackService:
    def record_sentence(self, passage_id: UUID, sentence_id: UUID, audio: Any) -> None:
        pass

    def get_feedback_by_sentence(self, sentence_id: UUID) -> None:
        return None

    async def judge_retry(self, **kwargs: Any) -> None:
        pass


class FakePracticeService:
    def request_model_audio(self, passage_id: UUID) -> None:
        pass

    def get_model_audio(self, passage_id: UUID) -> None:
        return None

    def should_skip(self, **kwargs: Any) -> bool:
        return False

    async def evaluate_overlapping(self, *args: Any) -> None:
        pass

    async def evaluate_live_delivery(self, *args: Any) -> None:
        pass


class FakeSessionQuery:
    def __init__(self, menu: SessionMenu) -> None:
        self._menu = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menu if menu_id == self._menu.id else None

    def get_passage_summary(self, passage_id: UUID) -> None:
        return None

    def get_session_summary(self, session_id: UUID) -> None:
        return None

    def get_menu_preview(self, menu_id: UUID) -> None:
        return None


class FakeSourceQuery:
    def __init__(self, source_repo: FakeSourceRepo) -> None:
        self._repo = source_repo

    def get_passage(self, passage_id: UUID) -> Passage | None:
        return self._repo.get_passage(passage_id)

    def get_source(self, source_id: UUID) -> Source | None:
        return self._repo.get_source(source_id)


class FakeItemQuery:
    def __init__(self, item_repo: FakeItemRepo, source_repo: FakeSourceRepo) -> None:
        self._item_repo = item_repo
        self._source_repo = source_repo

    def get_sentence_items(self, sentence_id: UUID) -> tuple:
        return ()

    def get_item(self, item_id: UUID) -> LearningItem | None:
        return self._item_repo.get_item(item_id)

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        return self._item_repo.get_items_by_sentence(sentence_id)

    def update_item(self, item_id: UUID, pattern: str, explanation: str) -> None:
        pass

    def dismiss_item(self, item_id: UUID) -> None:
        pass

    def resolve_review_pairs(self, item_ids: list[UUID]) -> list[tuple[UUID, UUID]]:
        pairs: list[tuple[UUID, UUID]] = []
        for item_id in item_ids:
            item = self._item_repo.get_item(item_id)
            if item is None:
                continue
            source = self._source_repo.get_source_by_sentence_id(item.source_sentence_id)
            if source is None:
                continue
            pairs.append((item_id, source.id))
        return pairs


class FakeContainer:
    """Minimal DI container for coordinator tests."""

    def __init__(
        self,
        menu: SessionMenu,
        *,
        source_repo: FakeSourceRepo | None = None,
        item_repo: FakeItemRepo | None = None,
    ) -> None:
        _source_repo = source_repo or FakeSourceRepo()
        _item_repo = item_repo or FakeItemRepo()

        self.event_bus = EventBus()
        self.session_service = FakeSessionService(menu)
        self.review_service = FakeReviewService()
        self.feedback_service = FakeFeedbackService()
        self.practice_service = FakePracticeService()
        self.settings_service = None
        self.source_service = None
        self.session_query = FakeSessionQuery(menu)
        self.source_query = FakeSourceQuery(_source_repo)
        self.item_query = FakeItemQuery(_item_repo, _source_repo)


# ======================================================================
# Fixtures
# ======================================================================


def _build_coordinator(
    menu: SessionMenu,
    *,
    source_repo: FakeSourceRepo | None = None,
    item_repo: FakeItemRepo | None = None,
) -> tuple[SessionCoordinator, FakeNavigationController, FakeContainer]:
    container = FakeContainer(menu, source_repo=source_repo, item_repo=item_repo)
    nav = FakeNavigationController()
    coord = SessionCoordinator(nav=nav, container=container)  # type: ignore[arg-type]
    return coord, nav, container


# ======================================================================
# Tests: 6-1 Session flow
# ======================================================================


class TestStart:
    def test_start_enters_session_and_shows_mic_check(self, qtbot: Any) -> None:
        menu = _make_menu()
        coord, nav, container = _build_coordinator(menu)

        coord.start(menu.id)

        assert nav.entered_session
        assert len(nav.pushed) == 1  # MicCheckView

    def test_start_calls_session_service(self, qtbot: Any) -> None:
        menu = _make_menu()
        coord, nav, container = _build_coordinator(menu)

        coord.start(menu.id)

        assert container.session_service.start_session_calls == [menu.id]


class TestMicCheckDone:
    def test_mic_check_proceed_starts_first_block(self, qtbot: Any) -> None:
        """After mic check, the first block screen should be pushed."""
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        menu = _make_menu(
            blocks=(
                SessionBlock(block_type="review", items=(item_id,), estimated_minutes=2.0),
            ),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        coord.start(menu.id)
        assert len(nav.pushed) == 1  # MicCheckView

        # Simulate mic check completion
        coord._on_mic_check_done()

        assert len(nav.pushed) == 2  # MicCheck + ReviewView
        assert coord._session_context.is_running  # timer started


class TestReviewBlock:
    def test_review_block_pushes_review_view(self, qtbot: Any) -> None:
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        menu = _make_menu(
            pattern="b",
            blocks=(SessionBlock(block_type="review", items=(item_id,), estimated_minutes=2.0),),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        coord.start(menu.id)
        coord._on_mic_check_done()

        # ReviewView should be pushed (after MicCheck was popped)
        assert len(nav.pushed) == 2

    def test_review_all_done_advances_block(self, qtbot: Any) -> None:
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        menu = _make_menu(
            pattern="b",
            blocks=(SessionBlock(block_type="review", items=(item_id,), estimated_minutes=2.0),),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        coord.start(menu.id)
        coord._on_mic_check_done()

        # Simulate review completion
        coord._on_block_complete()

        assert len(container.session_service.advance_block_calls) == 1


class TestNewMaterialBlock:
    def test_new_material_shows_phase_a(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()

        # PhaseAView should be pushed
        assert len(nav.pushed) == 2

    def test_phase_a_done_shows_phase_b(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()

        coord._on_phase_a_done()

        # PhaseA popped + PhaseBView pushed
        assert len(nav.pushed) == 3
        assert nav.popped_count >= 1

    def test_phase_b_skip_shows_passage_summary(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()
        coord._on_phase_a_done()

        coord._on_phase_b_done(skip_phase_c=True)

        # PhaseB popped + PassageSummaryView pushed (no PhaseC)
        pushed_count = len(nav.pushed)
        assert pushed_count == 4  # MicCheck + PhaseA + PhaseB + PassageSummary

    def test_phase_b_no_skip_shows_phase_c(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()
        coord._on_phase_a_done()

        coord._on_phase_b_done(skip_phase_c=False)

        # PhaseB popped + PhaseCView pushed
        assert len(nav.pushed) == 4  # MicCheck + PhaseA + PhaseB + PhaseC

    def test_phase_c_complete_shows_passage_summary(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()
        coord._on_phase_a_done()
        coord._on_phase_b_done(skip_phase_c=False)

        coord._on_phase_c_done(passage.id)

        # PhaseC popped + PassageSummaryView pushed
        assert len(nav.pushed) == 5


class TestMultiplePassages:
    def test_two_passages_loop(self, qtbot: Any) -> None:
        p1 = _make_passage()
        p2 = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(p1)
        source_repo.add_passage(p2)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(
                    block_type="new_material",
                    items=(p1.id, p2.id),
                    estimated_minutes=20.0,
                ),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()

        # Passage 1: PhaseA → PhaseB → skip PhaseC → PassageSummary
        coord._on_phase_a_done()
        coord._on_phase_b_done(skip_phase_c=True)

        # Navigate to next passage
        coord._on_next_passage()

        # Passage 2: PhaseA should be pushed
        assert coord._current_passage_index == 1
        assert coord._current_passage is not None
        assert coord._current_passage.id == p2.id


class TestConsolidation:
    def test_consolidation_uses_stocked_items(self, qtbot: Any) -> None:
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        passage = _make_passage()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        coord.start(menu.id)
        coord._on_mic_check_done()

        # Simulate item stocking during new material
        container.event_bus.emit(
            LearningItemStocked(item_id=item_id, pattern="test", is_reappearance=False)
        )
        assert item_id in coord._stocked_item_ids

        # Complete new_material block: PhaseA → PhaseB → PassageSummary → block_complete
        coord._on_phase_a_done()
        coord._on_phase_b_done(skip_phase_c=True)
        coord._on_block_complete()  # advance to consolidation

        # Consolidation should have started a review with the stocked item
        assert len(container.session_service.advance_block_calls) == 1
        # Should be listening=False now
        assert not coord._listening_stocked

    def test_consolidation_empty_skips(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="c",
            blocks=(
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        coord.start(menu.id)
        coord._on_mic_check_done()

        # Complete new_material without stocking any items
        coord._on_phase_a_done()
        coord._on_phase_b_done(skip_phase_c=True)
        coord._on_block_complete()  # advance to consolidation

        # Consolidation should auto-skip (advance_block called twice: once for new_material, once for consolidation)
        assert len(container.session_service.advance_block_calls) == 2


class TestPatternFlows:
    def test_pattern_b_review_only(self, qtbot: Any) -> None:
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        menu = _make_menu(
            pattern="b",
            blocks=(SessionBlock(block_type="review", items=(item_id,), estimated_minutes=2.0),),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )

        finished = []
        coord.session_finished.connect(lambda: finished.append(True))

        coord.start(menu.id)
        coord._on_mic_check_done()  # → review block
        coord._on_block_complete()  # → session complete → F1

        # Session summary should be pushed
        assert container.session_service.advance_block_calls


class TestSessionSummaryAndMenu:
    def test_session_summary_stops_timer(self, qtbot: Any) -> None:
        menu = _make_menu(pattern="b", blocks=(
            SessionBlock(block_type="review", items=(uuid4(),), estimated_minutes=2.0),
        ))
        item_id = menu.blocks[0].items[0]
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        coord.start(menu.id)
        coord._on_mic_check_done()
        assert coord._session_context.is_running

        coord._on_block_complete()  # → F1

        assert not coord._session_context.is_running

    def test_tomorrow_menu_confirmed_exits(self, qtbot: Any) -> None:
        menu = _make_menu(pattern="b", blocks=(
            SessionBlock(block_type="review", items=(uuid4(),), estimated_minutes=2.0),
        ))
        item_id = menu.blocks[0].items[0]
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        finished = []
        coord.session_finished.connect(lambda: finished.append(True))

        coord.start(menu.id)
        coord._on_mic_check_done()
        coord._on_block_complete()  # → F1
        coord._show_tomorrow_menu()  # → F2
        coord._on_session_end()

        assert nav.exited_session
        assert len(finished) == 1


# ======================================================================
# Tests: 6-2 Interrupt / Resume
# ======================================================================


class TestInterrupt:
    def test_interrupt_saves_and_exits(self, qtbot: Any) -> None:
        menu = _make_menu()
        coord, nav, container = _build_coordinator(menu)
        finished = []
        coord.session_finished.connect(lambda: finished.append(True))

        coord.start(menu.id)
        coord.interrupt()

        assert len(container.session_service.interrupt_calls) == 1
        assert nav.exited_session
        assert len(finished) == 1
        assert not coord._session_context.is_running


class TestResume:
    def test_resume_skips_mic_check(self, qtbot: Any) -> None:
        item_id = uuid4()
        source = _make_source()
        item = _make_item(item_id=item_id)
        source_repo = FakeSourceRepo()
        source_repo.add_source_for_sentence(item.source_sentence_id, source)
        item_repo = FakeItemRepo()
        item_repo.add_item(item)

        menu = _make_menu(
            pattern="b",
            blocks=(SessionBlock(block_type="review", items=(item_id,), estimated_minutes=2.0),),
        )
        coord, nav, container = _build_coordinator(
            menu, source_repo=source_repo, item_repo=item_repo
        )
        # Set up state for resume
        state = _make_state(menu.id, status="interrupted", block_index=0)
        container.session_service._state = state

        coord.start_resumed(state.id)

        assert nav.entered_session
        assert len(container.session_service.resume_calls) == 1
        # Should go directly to first block (ReviewView), no MicCheck
        assert len(nav.pushed) == 1  # Only ReviewView, no MicCheck
        assert coord._session_context.is_running

    def test_resume_at_block_1(self, qtbot: Any) -> None:
        passage = _make_passage()
        source_repo = FakeSourceRepo()
        source_repo.add_passage(passage)

        menu = _make_menu(
            pattern="a",
            blocks=(
                SessionBlock(block_type="review", items=(uuid4(),), estimated_minutes=2.0),
                SessionBlock(block_type="new_material", items=(passage.id,), estimated_minutes=10.0),
                SessionBlock(block_type="consolidation", items=(), estimated_minutes=0.0),
            ),
        )
        coord, nav, container = _build_coordinator(menu, source_repo=source_repo)
        # Resume at block 1 (new_material)
        state = _make_state(menu.id, status="interrupted", block_index=1)
        container.session_service._state = state

        coord.start_resumed(state.id)

        # Should start new_material block directly (PhaseAView)
        assert len(nav.pushed) == 1
