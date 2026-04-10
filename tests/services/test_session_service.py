"""Tests for SessionService."""

from collections.abc import Sequence
from datetime import date
from uuid import UUID

import pytest

from parla.domain.events import (
    BackgroundGenerationCompleted,
    BackgroundGenerationStarted,
    MenuComposed,
    MenuConfirmed,
    MenuRecomposed,
    SessionCompleted,
    SessionInterrupted,
    SessionResumed,
    SessionStarted,
)
from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.session import SessionConfig, SessionMenu, SessionState
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.ports.variation_generation import PastVariationInfo, RawVariation
from parla.services.session_service import SessionService

# --- Fakes ---


class FakeSessionRepo:
    def __init__(self) -> None:
        self._menus: dict[UUID, SessionMenu] = {}
        self._states: dict[UUID, SessionState] = {}

    def save_menu(self, menu: SessionMenu) -> None:
        self._menus[menu.id] = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menus.get(menu_id)

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        for menu in reversed(list(self._menus.values())):
            if menu.target_date == target_date and menu.confirmed:
                return menu
        return None

    def save_state(self, state: SessionState) -> None:
        self._states[state.id] = state

    def get_state(self, session_id: UUID) -> SessionState | None:
        return self._states.get(session_id)

    def get_active_state(self) -> SessionState | None:
        for state in self._states.values():
            if state.status in ("in_progress", "interrupted"):
                return state
        return None

    def update_state(self, state: SessionState) -> None:
        self._states[state.id] = state


class FakeSourceRepo:
    def __init__(self) -> None:
        self._sources: dict[UUID, Source] = {}
        self._passages: dict[UUID, Passage] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def update_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for p in passages:
            self._passages[p.id] = p

    def get_passages_by_source(self, source_id: UUID) -> list[Passage]:
        return sorted(
            [p for p in self._passages.values() if p.source_id == source_id],
            key=lambda p: p.order,
        )

    def get_passage(self, passage_id: UUID) -> Passage | None:
        return self._passages.get(passage_id)

    def get_active_sources(self) -> list[Source]:
        return [s for s in self._sources.values() if s.status in ("not_started", "in_progress")]


class FakeItemRepo:
    def __init__(self) -> None:
        self._items: list[LearningItem] = []

    def save_items(self, items: Sequence[LearningItem]) -> None:
        self._items.extend(items)

    def get_item(self, item_id: UUID) -> LearningItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def get_due_items(self, as_of: date, limit: int = 20) -> list[LearningItem]:
        due = [
            i
            for i in self._items
            if i.status == "auto_stocked" and i.next_review_date is not None and i.next_review_date <= as_of
        ]
        due.sort(key=lambda i: i.next_review_date)  # type: ignore[arg-type]
        return due[:limit]

    def count_due_items(self, as_of: date) -> int:
        return len(
            [
                i
                for i in self._items
                if i.status == "auto_stocked" and i.next_review_date is not None and i.next_review_date <= as_of
            ]
        )


class FakeVariationRepo:
    def __init__(self) -> None:
        self._variations: list = []

    def get_variations_by_item(self, item_id: UUID) -> list:
        return [v for v in self._variations if v.learning_item_id == item_id]

    def save_variation(self, variation) -> None:
        self._variations.append(variation)


class FakeVariationGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.call_count = 0

    async def generate_variation(
        self,
        learning_item_pattern: str,
        learning_item_explanation: str,
        cefr_level: str,
        english_variant: str,
        source_text: str,
        past_variations: Sequence[PastVariationInfo],
    ) -> RawVariation:
        self.call_count += 1
        if self._fail:
            msg = "Simulated LLM error"
            raise RuntimeError(msg)
        return RawVariation(
            ja="テスト日本語",
            en=f"Test sentence using {learning_item_pattern}.",
            hint1="Test hint1",
            hint2="Test hint2",
        )


class FakeFeedbackRepo:
    def __init__(self) -> None:
        self._feedback_sentence_ids: set[UUID] = set()

    def get_feedback_by_sentence(self, sentence_id: UUID):
        if sentence_id in self._feedback_sentence_ids:
            return True  # truthy sentinel
        return None

    def mark_sentence_done(self, sentence_id: UUID) -> None:
        self._feedback_sentence_ids.add(sentence_id)


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        for event_type in (
            MenuComposed,
            MenuConfirmed,
            MenuRecomposed,
            BackgroundGenerationStarted,
            BackgroundGenerationCompleted,
            SessionStarted,
            SessionInterrupted,
            SessionResumed,
            SessionCompleted,
        ):
            bus.on_sync(event_type)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[type[Event]]:
        return [type(e) for e in self.events]


# --- Setup helpers ---


def _make_source(status: str = "not_started") -> Source:
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    if status != "registered":
        source = source.start_generating()
        source = source.complete_generation()
    return source


def _make_passage(source_id: UUID, order: int = 0) -> Passage:
    sentence = Sentence(
        order=0,
        ja="テスト文",
        en="Test sentence.",
        hints=Hint(hint1="Test...", hint2="主語 + 動詞"),
    )
    return Passage(
        source_id=source_id,
        order=order,
        topic="Test",
        passage_type="説明型",
        sentences=(sentence,),
    )


def _make_item(sentence_id: UUID, review_date: date = date(2026, 4, 10)) -> LearningItem:
    return LearningItem(
        pattern="be responsible for ~ing",
        explanation="〜する責任がある",
        category="構文",
        priority=5,
        source_sentence_id=sentence_id,
        status="auto_stocked",
        next_review_date=review_date,
    )


def _setup(
    *,
    item_count: int = 5,
    review_date: date = date(2026, 4, 10),
    fail_variation: bool = False,
):
    bus = EventBus()
    session_repo = FakeSessionRepo()
    source_repo = FakeSourceRepo()
    item_repo = FakeItemRepo()
    variation_repo = FakeVariationRepo()
    variation_generator = FakeVariationGenerator(fail=fail_variation)
    feedback_repo = FakeFeedbackRepo()
    config = SessionConfig()

    source = _make_source()
    source_repo.save_source(source)

    passages = [_make_passage(source.id, order=i) for i in range(3)]
    source_repo.save_passages(passages)

    items = []
    for p in passages:
        for s in p.sentences:
            for _ in range(item_count):
                item = _make_item(s.id, review_date=review_date)
                items.append(item)
    if items:
        item_repo.save_items(items)

    service = SessionService(
        event_bus=bus,
        session_repo=session_repo,
        source_repo=source_repo,
        item_repo=item_repo,
        variation_repo=variation_repo,
        variation_generator=variation_generator,
        feedback_repo=feedback_repo,
        config=config,
    )

    collector = EventCollector(bus)
    bus.on_async(MenuConfirmed)(service.handle_menu_confirmed)

    return service, session_repo, source_repo, item_repo, bus, collector, source, passages, items


class TestComposeMenu:
    async def test_pattern_a_normal(self) -> None:
        service, session_repo, _, _, _, collector, source, passages, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert menu.pattern == "a"
        assert len(menu.blocks) == 3
        assert menu.blocks[0].block_type == "review"
        assert menu.blocks[1].block_type == "new_material"
        assert menu.blocks[2].block_type == "consolidation"
        assert menu.source_id == source.id

        saved = session_repo.get_menu(menu.id)
        assert saved is not None

    async def test_pattern_b_overflow(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=20)
        # 20 items * 3 passages * 1 sentence = 60 items > threshold 30

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert menu.pattern == "b"
        assert len(menu.blocks) == 1
        assert menu.blocks[0].block_type == "review"
        assert menu.source_id is None

    async def test_pattern_c_no_reviews(self) -> None:
        service, _, _, _, _, _, source, passages, _ = _setup(item_count=0)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert menu.pattern == "c"
        assert len(menu.blocks) == 2
        assert menu.blocks[0].block_type == "new_material"

    async def test_emits_menu_composed(self) -> None:
        service, _, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert MenuComposed in collector.types()
        composed = next(e for e in collector.events if isinstance(e, MenuComposed))
        assert composed.menu_id == menu.id
        assert composed.pattern == "a"

    async def test_pending_review_count_stored(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=5)
        # 5 items * 3 sentences = 15 items

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert menu.pending_review_count == 15

    async def test_review_items_limited(self) -> None:
        """Review block items should be limited to config.review_limit."""
        service, _, _, _, _, _, source, _, _ = _setup(item_count=10)
        # 10 * 3 = 30 items, at threshold → pattern a, but limited to 20

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        assert menu.pattern == "a"
        assert len(menu.blocks[0].items) <= 20


class TestRecomposeMenu:
    async def test_recompose_changes_source(self) -> None:
        service, _, source_repo, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        new_source = _make_source()
        source_repo.save_source(new_source)
        new_passage = _make_passage(new_source.id)
        source_repo.save_passages([new_passage])

        new_menu = service.recompose_menu(
            menu_id=menu.id,
            new_source_id=new_source.id,
            target_date=date(2026, 4, 11),
            today=date(2026, 4, 10),
        )

        assert new_menu.source_id == new_source.id
        assert new_menu.id != menu.id
        assert MenuRecomposed in collector.types()


class TestConfirmMenu:
    async def test_confirm_saves_and_emits(self) -> None:
        service, session_repo, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        saved = session_repo.get_menu(menu.id)
        assert saved is not None
        assert saved.confirmed is True
        assert MenuConfirmed in collector.types()


class TestBackgroundGeneration:
    async def test_generates_variations_for_review_items(self) -> None:
        service, session_repo, _, _, bus, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        # Find the MenuConfirmed event and process it
        confirmed_event = next(e for e in collector.events if isinstance(e, MenuConfirmed))
        await service.handle_menu_confirmed(confirmed_event)

        assert BackgroundGenerationStarted in collector.types()
        assert BackgroundGenerationCompleted in collector.types()
        completed = next(e for e in collector.events if isinstance(e, BackgroundGenerationCompleted))
        assert completed.success_count > 0
        assert completed.failure_count == 0

    async def test_handles_generation_failures(self) -> None:
        service, _, _, _, _, collector, source, _, _ = _setup(item_count=5, fail_variation=True)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        confirmed_event = next(e for e in collector.events if isinstance(e, MenuConfirmed))
        await service.handle_menu_confirmed(confirmed_event)

        completed = next(e for e in collector.events if isinstance(e, BackgroundGenerationCompleted))
        assert completed.success_count == 0
        assert completed.failure_count > 0

    async def test_no_review_block_completes_immediately(self) -> None:
        service, _, _, _, _, collector, source, _, _ = _setup(item_count=0)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        confirmed_event = next(e for e in collector.events if isinstance(e, MenuConfirmed))
        await service.handle_menu_confirmed(confirmed_event)

        completed = next(e for e in collector.events if isinstance(e, BackgroundGenerationCompleted))
        assert completed.success_count == 0
        assert completed.failure_count == 0


class TestSessionLifecycle:
    async def test_start_session(self) -> None:
        service, session_repo, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)
        state = service.start_session(menu.id)

        assert state.status == "in_progress"
        assert state.menu_id == menu.id
        assert state.current_block_index == 0
        assert SessionStarted in collector.types()

    async def test_interrupt_session(self) -> None:
        service, _, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)
        state = service.start_session(menu.id)
        service.advance_block(state.id)  # move to block 1
        service.interrupt_session(state.id)

        assert SessionInterrupted in collector.types()
        interrupted_event = next(e for e in collector.events if isinstance(e, SessionInterrupted))
        assert interrupted_event.block_index == 1

    async def test_resume_session(self) -> None:
        service, session_repo, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)
        state = service.start_session(menu.id)
        service.advance_block(state.id)
        service.interrupt_session(state.id)
        resumed = service.resume_session(state.id)

        assert resumed.status == "in_progress"
        assert resumed.current_block_index == 1
        assert SessionResumed in collector.types()

    async def test_advance_through_all_blocks_completes(self) -> None:
        service, _, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)
        state = service.start_session(menu.id)

        # Pattern a: 3 blocks (review, new_material, consolidation)
        service.advance_block(state.id)  # block 0 → 1
        service.advance_block(state.id)  # block 1 → 2
        service.advance_block(state.id)  # block 2 → complete

        assert SessionCompleted in collector.types()

    async def test_start_unconfirmed_menu_raises(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        with pytest.raises(ValueError, match="not confirmed"):
            service.start_session(menu.id)


class TestMenuFreshness:
    async def test_returns_menu_when_current(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        result = service.check_menu_freshness(date(2026, 4, 11))
        assert result is not None
        assert result.id == menu.id

    async def test_returns_none_when_stale(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))
        service.confirm_menu(menu.id)

        result = service.check_menu_freshness(date(2026, 4, 12))
        assert result is None

    async def test_returns_none_when_unconfirmed(self) -> None:
        service, _, _, _, _, _, source, _, _ = _setup(item_count=5)

        service.compose_menu(target_date=date(2026, 4, 11), source_id=source.id, today=date(2026, 4, 10))

        result = service.check_menu_freshness(date(2026, 4, 11))
        assert result is None


class TestGetActiveSources:
    async def test_returns_active_sources(self) -> None:
        service, _, source_repo, _, _, _, source, _, _ = _setup(item_count=0)

        sources = service.get_active_sources()
        assert len(sources) == 1
        assert sources[0].id == source.id
