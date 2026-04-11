"""Tests for SessionQueryService."""

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID, uuid4

from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.practice import LiveDeliveryResult
from parla.domain.review import ReviewAttempt
from parla.domain.session import BlockType, SessionBlock, SessionMenu, SessionPattern, SessionState
from parla.domain.source import Source
from parla.services.session_query_service import SessionQueryService


def _make_source(title: str = "Test Source") -> Source:
    return Source(title=title, text="x" * 100, cefr_level="B1", english_variant="American")


def _make_passage(source_id: UUID, *, order: int = 0) -> Passage:
    return Passage(
        source_id=source_id,
        order=order,
        topic="Topic",
        passage_type="dialogue",
        sentences=(
            Sentence(order=0, ja="日本語", en="English", hints=Hint(hint1="h1", hint2="h2")),
        ),
    )


class FakeSessionRepository:
    def __init__(self) -> None:
        self._menus: dict[UUID, SessionMenu] = {}
        self._date_menus: dict[str, SessionMenu] = {}
        self._states: dict[UUID, SessionState] = {}
        self._active: SessionState | None = None

    def save_menu(self, menu: SessionMenu) -> None:
        self._menus[menu.id] = menu
        if menu.confirmed:
            self._date_menus[menu.target_date.isoformat()] = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menus.get(menu_id)

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        return self._date_menus.get(target_date.isoformat())

    def save_state(self, state: SessionState) -> None:
        self._states[state.id] = state
        if state.status in ("in_progress", "interrupted"):
            self._active = state

    def get_state(self, session_id: UUID) -> SessionState | None:
        return self._states.get(session_id)

    def get_active_state(self) -> SessionState | None:
        return self._active

    def get_completed_states(self) -> Sequence[SessionState]:
        return [s for s in self._states.values() if s.status == "completed"]

    def update_state(self, state: SessionState) -> None:
        self._states[state.id] = state


class FakeSourceRepository:
    def __init__(self) -> None:
        self._sources: dict[UUID, Source] = {}
        self._passages: dict[UUID, list[Passage]] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for p in passages:
            self._passages.setdefault(p.source_id, []).append(p)

    def get_passages_by_source(self, source_id: UUID) -> Sequence[Passage]:
        return self._passages.get(source_id, [])

    def get_passage(self, passage_id: UUID) -> Passage | None:
        for passages in self._passages.values():
            for p in passages:
                if p.id == passage_id:
                    return p
        return None

    def get_active_sources(self) -> Sequence[Source]:
        return [s for s in self._sources.values() if s.status in ("not_started", "in_progress")]

    def get_all_sources(self) -> Sequence[Source]:
        return list(self._sources.values())

    def update_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        return None

    def get_sentence(self, sentence_id: UUID) -> Sentence | None:
        return None


class FakePracticeRepository:
    def __init__(self) -> None:
        self._achievements: set[UUID] = set()
        self._results: dict[UUID, list[LiveDeliveryResult]] = {}

    def has_achievement(self, passage_id: UUID) -> bool:
        return passage_id in self._achievements

    def add_achievement(self, passage_id: UUID) -> None:
        self._achievements.add(passage_id)

    def get_live_delivery_results(self, passage_id: UUID) -> Sequence[LiveDeliveryResult]:
        return self._results.get(passage_id, [])

    def get_all_live_delivery_results(self) -> Sequence[LiveDeliveryResult]:
        all_results = []
        for results in self._results.values():
            all_results.extend(results)
        return all_results

    def add_result(self, result: LiveDeliveryResult) -> None:
        self._results.setdefault(result.passage_id, []).append(result)


class FakeLearningItemRepository:
    def __init__(self) -> None:
        self._items: list[LearningItem] = []

    def save_items(self, items: Sequence[LearningItem]) -> None:
        self._items.extend(items)

    def get_stocked_items(self) -> Sequence[LearningItem]:
        return [i for i in self._items if i.status == "auto_stocked"]

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]:
        return [i for i in self._items if i.source_sentence_id == sentence_id]

    def get_item(self, item_id: UUID) -> LearningItem | None:
        return None

    def get_due_items(self, as_of: date, limit: int = 20) -> Sequence[LearningItem]:
        return []

    def count_due_items(self, as_of: date) -> int:
        return 0

    def update_item_status(self, item_id: UUID, status: str) -> None:
        pass

    def update_srs_state(self, *args: object, **kwargs: object) -> None:
        pass


class FakeReviewAttemptRepository:
    def __init__(self) -> None:
        self._attempts: list[ReviewAttempt] = []

    def save_attempt(self, attempt: ReviewAttempt) -> None:
        self._attempts.append(attempt)

    def get_attempts_by_variation(self, variation_id: UUID) -> Sequence[ReviewAttempt]:
        return []

    def get_all_attempts(self) -> Sequence[ReviewAttempt]:
        return list(self._attempts)


class TestGetTodayDashboard:
    def test_no_menu(self) -> None:
        service = SessionQueryService(
            session_repo=FakeSessionRepository(),
            source_repo=FakeSourceRepository(),
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        dash = service.get_today_dashboard(today=date(2026, 4, 10))
        assert dash.has_menu is False
        assert dash.menu_confirmed is False
        assert dash.blocks == ()

    def test_has_sources_false_when_no_sources(self) -> None:
        service = SessionQueryService(
            session_repo=FakeSessionRepository(),
            source_repo=FakeSourceRepository(),
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        dash = service.get_today_dashboard(today=date(2026, 4, 10))
        assert dash.has_sources is False

    def test_has_sources_true_when_source_exists(self) -> None:
        source_repo = FakeSourceRepository()
        source = _make_source(title="Some Source")
        source_repo.save_source(source)

        service = SessionQueryService(
            session_repo=FakeSessionRepository(),
            source_repo=source_repo,
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        dash = service.get_today_dashboard(today=date(2026, 4, 10))
        assert dash.has_sources is True

    def test_confirmed_menu(self) -> None:
        session_repo = FakeSessionRepository()
        source_repo = FakeSourceRepository()
        source = _make_source(title="My Source")
        source_repo.save_source(source)

        review_items = (uuid4(), uuid4())
        passage_ids = (uuid4(),)
        menu = SessionMenu(
            target_date=date(2026, 4, 10),
            pattern=SessionPattern.REVIEW_AND_NEW,
            blocks=(
                SessionBlock(block_type=BlockType.REVIEW, items=review_items, estimated_minutes=4.0),
                SessionBlock(block_type=BlockType.NEW_MATERIAL, items=passage_ids, estimated_minutes=10.0),
                SessionBlock(block_type=BlockType.CONSOLIDATION, items=(), estimated_minutes=0.0),
            ),
            source_id=source.id,
            confirmed=True,
            pending_review_count=2,
        )
        session_repo.save_menu(menu)

        service = SessionQueryService(
            session_repo=session_repo,
            source_repo=source_repo,
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        dash = service.get_today_dashboard(today=date(2026, 4, 10))
        assert dash.has_menu is True
        assert dash.menu_confirmed is True
        assert dash.menu_id == menu.id
        assert dash.pattern == SessionPattern.REVIEW_AND_NEW
        assert len(dash.blocks) == 3
        assert dash.blocks[0].block_type == BlockType.REVIEW
        assert dash.blocks[0].item_count == 2
        assert dash.total_estimated_minutes == 14.0
        assert dash.source_title == "My Source"

    def test_resumable_session(self) -> None:
        session_repo = FakeSessionRepository()
        menu = SessionMenu(
            target_date=date(2026, 4, 10), pattern=SessionPattern.REVIEW_AND_NEW, blocks=(), confirmed=True,
        )
        session_repo.save_menu(menu)
        state = SessionState(
            menu_id=menu.id, status="interrupted",
            started_at=datetime(2026, 4, 10, 9, 0),
        )
        session_repo.save_state(state)

        service = SessionQueryService(
            session_repo=session_repo,
            source_repo=FakeSourceRepository(),
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        dash = service.get_today_dashboard(today=date(2026, 4, 10))
        assert dash.has_resumable_session is True
        assert dash.resumable_session_id == state.id


class TestGetSessionSummary:
    def test_session_summary(self) -> None:
        session_repo = FakeSessionRepository()
        source_repo = FakeSourceRepository()
        review_attempt_repo = FakeReviewAttemptRepository()
        practice_repo = FakePracticeRepository()
        item_repo = FakeLearningItemRepository()

        review_items = (uuid4(), uuid4())
        menu = SessionMenu(
            target_date=date(2026, 4, 10), pattern=SessionPattern.REVIEW_AND_NEW,
            blocks=(
                SessionBlock(block_type=BlockType.REVIEW, items=review_items, estimated_minutes=4.0),
                SessionBlock(block_type=BlockType.NEW_MATERIAL, items=(), estimated_minutes=10.0),
                SessionBlock(block_type=BlockType.CONSOLIDATION, items=(), estimated_minutes=0.0),
            ),
            confirmed=True,
        )
        session_repo.save_menu(menu)
        state = SessionState(
            menu_id=menu.id, status="completed",
            started_at=datetime(2026, 4, 10, 9, 0),
            completed_at=datetime(2026, 4, 10, 10, 30),
        )
        session_repo.save_state(state)

        service = SessionQueryService(
            session_repo=session_repo,
            source_repo=source_repo,
            practice_repo=practice_repo,
            item_repo=item_repo,
            review_attempt_repo=review_attempt_repo,
        )
        summary = service.get_session_summary(state.id)
        assert summary is not None
        assert summary.session_id == state.id
        assert summary.pattern == SessionPattern.REVIEW_AND_NEW
