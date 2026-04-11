"""Tests for first-launch flow: auto-compose menu on first source generation."""

from collections.abc import Sequence
from datetime import date
from uuid import UUID, uuid4

from parla.domain.events import (
    MenuComposed,
    MenuConfirmed,
    PassageGenerationCompleted,
)
from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.session import SessionConfig, SessionMenu, SessionPattern
from parla.domain.source import Source
from parla.domain.srs import SRSConfig
from parla.event_bus import Event, EventBus
from parla.ports.variation_generation import RawVariation
from parla.services.session_service import SessionService

# --- Fakes ---


class FakeSessionRepo:
    def __init__(self) -> None:
        self._menus: dict[UUID, SessionMenu] = {}

    def save_menu(self, menu: SessionMenu) -> None:
        self._menus[menu.id] = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menus.get(menu_id)

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        for menu in reversed(list(self._menus.values())):
            if menu.target_date == target_date and menu.confirmed:
                return menu
        return None

    def get_active_state(self):
        return None

    def save_state(self, state) -> None:
        pass

    def get_state(self, session_id: UUID):
        return None

    def update_state(self, state) -> None:
        pass


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

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        return None

    def get_active_sources(self) -> list[Source]:
        return [s for s in self._sources.values() if s.status in ("not_started", "in_progress")]

    def get_all_sources(self) -> list[Source]:
        return list(self._sources.values())


class FakeItemRepo:
    def get_due_items(self, as_of: date, limit: int = 20) -> list[LearningItem]:
        return []

    def count_due_items(self, as_of: date) -> int:
        return 0


class FakeVariationRepo:
    def get_variations_by_item(self, item_id: UUID) -> list:
        return []

    def save_variation(self, variation) -> None:
        pass


class FakeVariationGenerator:
    async def generate_variation(self, *args, **kwargs) -> RawVariation:
        return RawVariation(ja="ja", en="en", hint1="h1", hint2="h2")


class FakeFeedbackRepo:
    def get_feedback_by_sentence(self, sentence_id: UUID):
        return None


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        for et in (MenuComposed, MenuConfirmed):
            bus.on_sync(et)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[type[Event]]:
        return [type(e) for e in self.events]


# --- Helpers ---


def _make_source(*, status: str = "not_started") -> Source:
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    if status != "registered":
        source = source.start_generating()
        source = source.complete_generation()
    return source


def _make_passage(source_id: UUID, order: int = 0) -> Passage:
    return Passage(
        source_id=source_id,
        order=order,
        topic="Topic",
        passage_type="dialogue",
        sentences=(
            Sentence(order=0, ja="テスト", en="Test.", hints=Hint(hint1="h1", hint2="h2")),
        ),
    )


def _make_service():
    bus = EventBus()
    session_repo = FakeSessionRepo()
    source_repo = FakeSourceRepo()
    item_repo = FakeItemRepo()
    service = SessionService(
        event_bus=bus,
        session_repo=session_repo,
        source_repo=source_repo,
        item_repo=item_repo,
        variation_repo=FakeVariationRepo(),
        variation_generator=FakeVariationGenerator(),
        feedback_repo=FakeFeedbackRepo(),
        config=SessionConfig(),
        srs_config=SRSConfig(),
    )
    collector = EventCollector(bus)
    return service, session_repo, source_repo, bus, collector


class TestHandleFirstSourceReady:
    """handle_first_source_ready auto-composes and confirms today's menu."""

    def test_auto_composes_menu_on_first_source(self) -> None:
        """初回ソース生成完了 → 今日のメニューが自動作成・確定される。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = _make_source()
        source_repo.save_source(source)
        source_repo.save_passages([_make_passage(source.id, order=i) for i in range(2)])

        event = PassageGenerationCompleted(
            source_id=source.id, passage_count=2, total_sentences=2,
        )
        service.handle_first_source_ready(event)

        assert MenuComposed in collector.types()
        assert MenuConfirmed in collector.types()

    def test_auto_composed_menu_is_for_today(self) -> None:
        """自動作成されたメニューは今日の日付。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = _make_source()
        source_repo.save_source(source)
        source_repo.save_passages([_make_passage(source.id)])

        service.handle_first_source_ready(
            PassageGenerationCompleted(source_id=source.id, passage_count=1, total_sentences=1),
        )

        menu_event = next(e for e in collector.events if isinstance(e, MenuComposed))
        assert menu_event.target_date == date.today()

    def test_auto_composed_menu_uses_pattern_c(self) -> None:
        """復習項目がない場合、Pattern c（新素材のみ）が選ばれる。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = _make_source()
        source_repo.save_source(source)
        source_repo.save_passages([_make_passage(source.id)])

        service.handle_first_source_ready(
            PassageGenerationCompleted(source_id=source.id, passage_count=1, total_sentences=1),
        )

        menu_event = next(e for e in collector.events if isinstance(e, MenuComposed))
        assert menu_event.pattern == SessionPattern.NEW_ONLY

    def test_idempotent_when_menu_already_exists(self) -> None:
        """既にメニューが存在する場合は何もしない。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = _make_source()
        source_repo.save_source(source)
        source_repo.save_passages([_make_passage(source.id)])

        # 1回目: メニュー作成
        event = PassageGenerationCompleted(source_id=source.id, passage_count=1, total_sentences=1)
        service.handle_first_source_ready(event)
        assert len([e for e in collector.events if isinstance(e, MenuComposed)]) == 1

        # 2回目: 何もしない
        service.handle_first_source_ready(event)
        assert len([e for e in collector.events if isinstance(e, MenuComposed)]) == 1

    def test_skips_if_source_not_found(self) -> None:
        """ソースが見つからない場合はスキップ。"""
        service, session_repo, source_repo, bus, collector = _make_service()

        event = PassageGenerationCompleted(source_id=uuid4(), passage_count=1, total_sentences=1)
        service.handle_first_source_ready(event)

        assert len(collector.events) == 0

    def test_skips_if_source_status_not_ready(self) -> None:
        """ソースのstatusがnot_startedでなければスキップ。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
        # status is "registered" — not ready for menu
        source_repo.save_source(source)

        event = PassageGenerationCompleted(source_id=source.id, passage_count=1, total_sentences=1)
        service.handle_first_source_ready(event)

        assert len(collector.events) == 0

    def test_auto_confirmed_menu_is_retrievable(self) -> None:
        """確定されたメニューはget_menu_for_dateで取得できる。"""
        service, session_repo, source_repo, bus, collector = _make_service()
        source = _make_source()
        source_repo.save_source(source)
        source_repo.save_passages([_make_passage(source.id)])

        service.handle_first_source_ready(
            PassageGenerationCompleted(source_id=source.id, passage_count=1, total_sentences=1),
        )

        menu = session_repo.get_menu_for_date(date.today())
        assert menu is not None
        assert menu.confirmed is True
