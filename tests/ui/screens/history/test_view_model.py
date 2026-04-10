"""Tests for HistoryViewModel (SCREEN-C4)."""

from datetime import date, datetime
from uuid import uuid4

from parla.domain.events import SessionCompleted
from parla.event_bus import EventBus
from parla.services.query_models import (
    CalendarMarker,
    DailySummary,
    HistoryOverview,
    WpmDataPoint,
)
from parla.ui.screens.history.view_model import HistoryViewModel


def _make_overview() -> HistoryOverview:
    return HistoryOverview(
        calendar_markers=(
            CalendarMarker(date=date(2026, 4, 1), session_count=1),
            CalendarMarker(date=date(2026, 4, 5), session_count=2),
        ),
        wpm_trend=(
            WpmDataPoint(recorded_at=datetime(2026, 4, 1), wpm=110.0),
            WpmDataPoint(recorded_at=datetime(2026, 4, 5), wpm=125.0),
        ),
    )


def _make_summary(target_date: date | None = None) -> DailySummary:
    return DailySummary(
        date=target_date or date(2026, 4, 5),
        session_count=2,
        passage_count=3,
        new_item_count=5,
        review_count=10,
        review_correct_count=8,
        average_wpm=130.0,
    )


class FakeHistoryQueryService:
    def __init__(self, overview=None, summary=None):
        self._overview = overview or HistoryOverview()
        self._summary = summary or DailySummary(date=date(2026, 1, 1))
        self.overview_calls: int = 0
        self.summary_calls: list[date] = []

    def get_history_overview(self):
        self.overview_calls += 1
        return self._overview

    def get_daily_summary(self, target_date):
        self.summary_calls.append(target_date)
        return self._summary


class TestLoadOverview:
    def test_load_overview_emits_overview_loaded(self, qtbot) -> None:
        overview = _make_overview()
        service = FakeHistoryQueryService(overview=overview)
        vm = HistoryViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.overview_loaded, timeout=1000) as blocker:
            vm.load_overview()

        assert blocker.args == [overview]
        assert vm.overview is overview

    def test_load_overview_empty(self, qtbot) -> None:
        service = FakeHistoryQueryService()
        vm = HistoryViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.overview_loaded, timeout=1000):
            vm.load_overview()

        assert vm.overview is not None


class TestSelectDate:
    def test_select_date_emits_daily_summary_loaded(self, qtbot) -> None:
        target = date(2026, 4, 5)
        summary = _make_summary(target)
        service = FakeHistoryQueryService(summary=summary)
        vm = HistoryViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.daily_summary_loaded, timeout=1000) as blocker:
            vm.select_date(target)

        assert blocker.args == [summary]
        assert vm.daily_summary is summary
        assert service.summary_calls == [target]


class TestEventHandling:
    def test_session_completed_triggers_reload(self, qtbot) -> None:
        service = FakeHistoryQueryService()
        bus = EventBus()
        vm = HistoryViewModel(bus, service)
        vm.activate()

        service.overview_calls = 0
        bus.emit(SessionCompleted(session_id=uuid4()))

        assert service.overview_calls == 1

    def test_no_reload_when_inactive(self, qtbot) -> None:
        service = FakeHistoryQueryService()
        bus = EventBus()
        HistoryViewModel(bus, service)
        # not activated

        bus.emit(SessionCompleted(session_id=uuid4()))

        assert service.overview_calls == 0
