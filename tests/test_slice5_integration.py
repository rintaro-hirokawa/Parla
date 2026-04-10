"""Slice 5 integration tests: Session Composition + Menu Confirmation.

Verifies the full flow with real SQLite (:memory:), real EventBus wiring,
and Fake LLM adapters.

compose_menu → confirm_menu → background generation → start_session
→ interrupt → resume → advance → complete
"""

from collections.abc import Sequence
from datetime import date

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_learning_item_repository import SQLiteLearningItemRepository
from parla.adapters.sqlite_session_repository import SQLiteSessionRepository
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.adapters.sqlite_variation_repository import SQLiteVariationRepository
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
from parla.domain.feedback import SentenceFeedback
from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.session import SessionConfig
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.ports.variation_generation import PastVariationInfo, RawVariation
from parla.services.session_service import SessionService

# --- Fakes ---


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
            en=f"Test using {learning_item_pattern}.",
            hint1="hint1",
            hint2="hint2",
        )


class FakeFeedbackRepo:
    """Minimal fake — only needs get_feedback_by_sentence for passage selection."""

    def __init__(self) -> None:
        self._feedback: dict = {}

    def save_feedback(self, feedback: SentenceFeedback) -> None:
        self._feedback[feedback.sentence_id] = feedback

    def get_feedback_by_sentence(self, sentence_id):
        return self._feedback.get(sentence_id)

    def save_practice_attempt(self, attempt) -> None:
        pass

    def get_attempts_by_sentence(self, sentence_id):
        return []


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


# --- Setup ---


def _setup(*, item_count: int = 5, fail_variation: bool = False):
    """Wire the full system for slice 5 with real SQLite."""
    bus = EventBus()
    conn = create_connection(":memory:")
    init_schema(conn)

    source_repo = SQLiteSourceRepository(conn)
    item_repo = SQLiteLearningItemRepository(conn)
    variation_repo = SQLiteVariationRepository(conn)
    session_repo = SQLiteSessionRepository(conn)
    variation_generator = FakeVariationGenerator(fail=fail_variation)
    feedback_repo = FakeFeedbackRepo()
    config = SessionConfig()

    # Set up test data
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    source = source.start_generating().complete_generation()
    source_repo.save_source(source)
    # Update status to not_started
    source_repo.update_source(source)

    passages = []
    for i in range(3):
        sentence = Sentence(
            order=0,
            ja=f"テスト文{i}",
            en=f"Test sentence {i}.",
            hints=Hint(hint1=f"hint1-{i}", hint2=f"hint2-{i}"),
        )
        passage = Passage(
            source_id=source.id,
            order=i,
            topic=f"Topic {i}",
            passage_type="説明型",
            sentences=(sentence,),
        )
        passages.append(passage)
    source_repo.save_passages(passages)

    items = []
    for p in passages:
        for s in p.sentences:
            for _ in range(item_count):
                item = LearningItem(
                    pattern="be responsible for ~ing",
                    explanation="〜する責任がある",
                    category="構文",
                    priority=5,
                    source_sentence_id=s.id,
                    status="auto_stocked",
                    next_review_date=date(2026, 4, 10),
                )
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

    bus.on_async(MenuConfirmed)(service.handle_menu_confirmed)
    collector = EventCollector(bus)

    return service, session_repo, source_repo, item_repo, variation_repo, bus, collector, source, passages, items


class TestSessionCompositionFlow:
    """End-to-end: compose → confirm → background generation."""

    async def test_compose_and_confirm_generates_variations(self) -> None:
        service, session_repo, _, _, variation_repo, bus, collector, source, passages, items = _setup(item_count=5)

        # 1. Compose menu
        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        assert menu.pattern == "a"
        assert menu.pending_review_count == 15  # 5 items * 3 sentences

        # 2. Verify menu saved to SQLite
        saved = session_repo.get_menu(menu.id)
        assert saved is not None
        assert saved.blocks[0].block_type == "review"
        assert len(saved.blocks[0].items) <= 20

        # 3. Confirm menu — triggers async background generation
        service.confirm_menu(menu.id)
        confirmed = session_repo.get_menu(menu.id)
        assert confirmed is not None
        assert confirmed.confirmed is True

        # 4. Await background generation
        confirmed_event = next(e for e in collector.events if isinstance(e, MenuConfirmed))
        await service.handle_menu_confirmed(confirmed_event)

        # 5. Verify variations generated
        assert BackgroundGenerationCompleted in collector.types()
        completed = next(e for e in collector.events if isinstance(e, BackgroundGenerationCompleted))
        assert completed.success_count == len(saved.blocks[0].items)
        assert completed.failure_count == 0

        # Verify variations persisted
        review_item_id = saved.blocks[0].items[0]
        variations = variation_repo.get_variations_by_item(review_item_id)
        assert len(variations) >= 1

    async def test_pattern_b_overflow(self) -> None:
        service, _, _, _, _, _, collector, source, _, _ = _setup(item_count=20)
        # 20 * 3 = 60 > threshold 30

        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        assert menu.pattern == "b"
        assert len(menu.blocks) == 1
        assert menu.blocks[0].block_type == "review"
        assert menu.source_id is None

    async def test_pattern_c_no_reviews(self) -> None:
        service, _, _, _, _, _, collector, source, passages, _ = _setup(item_count=0)

        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        assert menu.pattern == "c"
        assert len(menu.blocks) == 2
        assert menu.blocks[0].block_type == "new_material"
        assert menu.blocks[0].items == (passages[0].id,)


class TestRecomposeMenu:
    async def test_recompose_with_new_source(self) -> None:
        service, _, source_repo, _, _, _, collector, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )

        # Create a second source
        source2 = Source(text="b" * 200, cefr_level="B2", english_variant="British")
        source2 = source2.start_generating().complete_generation()
        source_repo.save_source(source2)
        source_repo.update_source(source2)
        sentence2 = Sentence(order=0, ja="新テスト", en="New test.", hints=Hint(hint1="h1", hint2="h2"))
        passage2 = Passage(source_id=source2.id, order=0, topic="New", passage_type="説明型", sentences=(sentence2,))
        source_repo.save_passages([passage2])

        new_menu = service.recompose_menu(
            menu_id=menu.id,
            new_source_id=source2.id,
            target_date=date(2026, 4, 11),
            today=date(2026, 4, 10),
        )

        assert new_menu.source_id == source2.id
        assert MenuRecomposed in collector.types()


class TestSessionLifecycleFlow:
    """End-to-end: start → interrupt → resume → advance → complete."""

    async def test_full_session_lifecycle(self) -> None:
        service, session_repo, _, _, _, _, collector, source, _, _ = _setup(item_count=5)

        # Compose and confirm
        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        service.confirm_menu(menu.id)

        # Start session
        state = service.start_session(menu.id)
        assert state.status == "in_progress"
        assert SessionStarted in collector.types()

        # Advance through block 0 → 1
        state = service.advance_block(state.id)
        assert state.current_block_index == 1

        # Interrupt mid-session
        service.interrupt_session(state.id)
        assert SessionInterrupted in collector.types()

        # Verify state persisted
        loaded = session_repo.get_state(state.id)
        assert loaded is not None
        assert loaded.status == "interrupted"
        assert loaded.current_block_index == 1

        # Resume
        resumed = service.resume_session(state.id)
        assert resumed.status == "in_progress"
        assert resumed.current_block_index == 1
        assert SessionResumed in collector.types()

        # Advance block 1 → 2
        state = service.advance_block(state.id)
        assert state.current_block_index == 2

        # Advance block 2 → complete
        state = service.advance_block(state.id)
        assert state.status == "completed"
        assert SessionCompleted in collector.types()

        # Verify final state in DB
        final = session_repo.get_state(state.id)
        assert final is not None
        assert final.status == "completed"
        assert final.completed_at is not None


class TestMenuFreshnessFlow:
    async def test_freshness_check(self) -> None:
        service, _, _, _, _, _, _, source, _, _ = _setup(item_count=5)

        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        service.confirm_menu(menu.id)

        # Check for correct date
        result = service.check_menu_freshness(date(2026, 4, 11))
        assert result is not None
        assert result.id == menu.id

        # Check for wrong date → stale
        result = service.check_menu_freshness(date(2026, 4, 12))
        assert result is None


class TestBackgroundGenerationFailure:
    async def test_failed_variations_counted(self) -> None:
        service, session_repo, _, _, _, _, collector, source, _, _ = _setup(item_count=5, fail_variation=True)

        menu = service.compose_menu(
            target_date=date(2026, 4, 11),
            source_id=source.id,
            today=date(2026, 4, 10),
        )
        service.confirm_menu(menu.id)

        confirmed_event = next(e for e in collector.events if isinstance(e, MenuConfirmed))
        await service.handle_menu_confirmed(confirmed_event)

        completed = next(e for e in collector.events if isinstance(e, BackgroundGenerationCompleted))
        assert completed.success_count == 0
        assert completed.failure_count > 0
