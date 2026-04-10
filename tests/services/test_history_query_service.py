"""Tests for HistoryQueryService."""

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID, uuid4

from parla.domain.learning_item import LearningItem
from parla.domain.practice import LiveDeliveryResult
from parla.domain.review import ReviewAttempt
from parla.domain.session import SessionMenu, SessionState
from parla.services.history_query_service import HistoryQueryService


class FakeSessionRepository:
    def __init__(self) -> None:
        self._menus: dict[UUID, SessionMenu] = {}
        self._states: list[SessionState] = []

    def save_menu(self, menu: SessionMenu) -> None:
        self._menus[menu.id] = menu

    def get_menu(self, menu_id: UUID) -> SessionMenu | None:
        return self._menus.get(menu_id)

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        return None

    def save_state(self, state: SessionState) -> None:
        self._states.append(state)

    def get_state(self, session_id: UUID) -> SessionState | None:
        return None

    def get_active_state(self) -> SessionState | None:
        return None

    def get_completed_states(self) -> Sequence[SessionState]:
        return [s for s in self._states if s.status == "completed"]

    def update_state(self, state: SessionState) -> None:
        pass


class FakePracticeRepository:
    def __init__(self) -> None:
        self._results: list[LiveDeliveryResult] = []

    def get_all_live_delivery_results(self) -> Sequence[LiveDeliveryResult]:
        return list(self._results)

    def has_achievement(self, passage_id: UUID) -> bool:
        return False

    def add_result(self, result: LiveDeliveryResult) -> None:
        self._results.append(result)


class FakeLearningItemRepository:
    def __init__(self) -> None:
        self._items: list[LearningItem] = []

    def save_items(self, items: Sequence[LearningItem]) -> None:
        self._items.extend(items)

    def get_stocked_items(self) -> Sequence[LearningItem]:
        return [i for i in self._items if i.status == "auto_stocked"]

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]:
        return []

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


def _completed_session(completed_at: datetime, menu_id: UUID | None = None) -> SessionState:
    return SessionState(
        menu_id=menu_id or uuid4(),
        status="completed",
        started_at=completed_at,
        completed_at=completed_at,
    )


class TestGetHistoryOverview:
    def test_empty(self) -> None:
        service = HistoryQueryService(
            session_repo=FakeSessionRepository(),
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        overview = service.get_history_overview()
        assert overview.calendar_markers == ()
        assert overview.wpm_trend == ()

    def test_calendar_markers_from_completed_sessions(self) -> None:
        session_repo = FakeSessionRepository()
        session_repo.save_state(_completed_session(datetime(2026, 4, 5, 10, 0)))
        session_repo.save_state(_completed_session(datetime(2026, 4, 5, 15, 0)))
        session_repo.save_state(_completed_session(datetime(2026, 4, 7, 10, 0)))

        service = HistoryQueryService(
            session_repo=session_repo,
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        overview = service.get_history_overview()
        assert len(overview.calendar_markers) == 2
        markers = {m.date: m.session_count for m in overview.calendar_markers}
        assert markers[date(2026, 4, 5)] == 2
        assert markers[date(2026, 4, 7)] == 1

    def test_wpm_trend_from_live_delivery(self) -> None:
        practice_repo = FakePracticeRepository()
        practice_repo.add_result(
            LiveDeliveryResult(
                passage_id=uuid4(),
                passed=True,
                sentence_statuses=(),
                duration_seconds=60.0,
                wpm=120.0,
                created_at=datetime(2026, 4, 5, 10, 0),
            )
        )
        practice_repo.add_result(
            LiveDeliveryResult(
                passage_id=uuid4(),
                passed=True,
                sentence_statuses=(),
                duration_seconds=60.0,
                wpm=130.0,
                created_at=datetime(2026, 4, 7, 10, 0),
            )
        )

        service = HistoryQueryService(
            session_repo=FakeSessionRepository(),
            practice_repo=practice_repo,
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        overview = service.get_history_overview()
        assert len(overview.wpm_trend) == 2
        assert overview.wpm_trend[0].wpm == 120.0
        assert overview.wpm_trend[1].wpm == 130.0


class TestGetDailySummary:
    def test_summary_for_date(self) -> None:
        session_repo = FakeSessionRepository()
        menu = SessionMenu(
            target_date=date(2026, 4, 5),
            pattern="a",
            blocks=(),
            confirmed=True,
        )
        session_repo.save_menu(menu)
        session_repo.save_state(
            SessionState(
                menu_id=menu.id,
                status="completed",
                started_at=datetime(2026, 4, 5, 9, 0),
                completed_at=datetime(2026, 4, 5, 10, 0),
            )
        )

        item_repo = FakeLearningItemRepository()
        item_repo.save_items([
            LearningItem(
                pattern="p1", explanation="e1", category="文法",
                priority=4, source_sentence_id=uuid4(), status="auto_stocked",
                created_at=datetime(2026, 4, 5, 9, 30),
            ),
        ])

        review_attempt_repo = FakeReviewAttemptRepository()
        review_attempt_repo.save_attempt(
            ReviewAttempt(
                variation_id=uuid4(), learning_item_id=uuid4(),
                attempt_number=1, correct=True, item_used=True,
                hint_level=0, timer_ratio=0.5,
                created_at=datetime(2026, 4, 5, 9, 15),
            )
        )

        practice_repo = FakePracticeRepository()
        practice_repo.add_result(
            LiveDeliveryResult(
                passage_id=uuid4(), passed=True, sentence_statuses=(),
                duration_seconds=60.0, wpm=125.0,
                created_at=datetime(2026, 4, 5, 9, 45),
            )
        )

        service = HistoryQueryService(
            session_repo=session_repo,
            practice_repo=practice_repo,
            item_repo=item_repo,
            review_attempt_repo=review_attempt_repo,
        )
        summary = service.get_daily_summary(date(2026, 4, 5))
        assert summary.date == date(2026, 4, 5)
        assert summary.session_count == 1
        assert summary.new_item_count == 1
        assert summary.review_count == 1
        assert summary.review_correct_count == 1
        assert summary.average_wpm == 125.0

    def test_summary_empty_date(self) -> None:
        service = HistoryQueryService(
            session_repo=FakeSessionRepository(),
            practice_repo=FakePracticeRepository(),
            item_repo=FakeLearningItemRepository(),
            review_attempt_repo=FakeReviewAttemptRepository(),
        )
        summary = service.get_daily_summary(date(2026, 4, 5))
        assert summary.session_count == 0
        assert summary.new_item_count == 0
