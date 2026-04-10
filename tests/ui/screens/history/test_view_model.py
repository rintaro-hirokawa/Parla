"""Tests for HistoryViewModel (SCREEN-C4)."""

from datetime import date
from uuid import uuid4

from parla.domain.events import SessionCompleted
from parla.event_bus import EventBus
from parla.ui.screens.history.view_model import HistoryViewModel
from tests.ui.screens.history.conftest import FakeHistoryQueryService, make_overview, make_summary


class TestLoadOverview:
    def test_load_overview_emits_overview_loaded(self, qtbot) -> None:
        overview = make_overview()
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
        summary = make_summary(target)
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
