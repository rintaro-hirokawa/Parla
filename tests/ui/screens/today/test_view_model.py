"""Tests for TodayViewModel."""

from datetime import date
from uuid import uuid4

from parla.domain.events import MenuConfirmed, SessionCompleted
from parla.event_bus import EventBus
from parla.services.query_models import MenuBlockSummary, TodayDashboard
from parla.ui.screens.today.view_model import TodayViewModel


class FakeSessionQueryService:
    def __init__(self, dashboard: TodayDashboard | None = None) -> None:
        self._dashboard = dashboard or TodayDashboard()
        self.call_count = 0

    def get_today_dashboard(self, *, today: date) -> TodayDashboard:
        self.call_count += 1
        return self._dashboard


def _no_menu_dashboard() -> TodayDashboard:
    return TodayDashboard(has_menu=False)


def _confirmed_dashboard() -> TodayDashboard:
    menu_id = uuid4()
    return TodayDashboard(
        has_menu=True,
        menu_confirmed=True,
        menu_id=menu_id,
        pattern="a",
        blocks=(
            MenuBlockSummary(block_type="review", item_count=10, estimated_minutes=20.0),
            MenuBlockSummary(block_type="new_material", item_count=2, estimated_minutes=20.0),
        ),
        total_estimated_minutes=40.0,
        source_title="Test Source",
    )


def _unconfirmed_dashboard() -> TodayDashboard:
    return TodayDashboard(
        has_menu=True,
        menu_confirmed=False,
        menu_id=uuid4(),
        pattern="b",
        blocks=(MenuBlockSummary(block_type="review", item_count=5, estimated_minutes=10.0),),
        total_estimated_minutes=10.0,
    )


class TestLoadDashboard:
    def test_emits_dashboard_loaded(self, qtbot) -> None:
        bus = EventBus()
        dash = _confirmed_dashboard()
        query = FakeSessionQueryService(dash)
        vm = TodayViewModel(bus, query)
        vm.activate()

        with qtbot.waitSignal(vm.dashboard_loaded, timeout=1000) as blocker:
            vm.load_dashboard()

        assert blocker.args[0] is dash

    def test_emits_start_enabled_true_for_confirmed(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_confirmed_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()

        with qtbot.waitSignal(vm.start_enabled_changed, timeout=1000) as blocker:
            vm.load_dashboard()

        assert blocker.args == [True]

    def test_emits_start_enabled_false_for_no_menu(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_no_menu_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()

        with qtbot.waitSignal(vm.start_enabled_changed, timeout=1000) as blocker:
            vm.load_dashboard()

        assert blocker.args == [False]

    def test_emits_start_enabled_false_for_unconfirmed(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_unconfirmed_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()

        with qtbot.waitSignal(vm.start_enabled_changed, timeout=1000) as blocker:
            vm.load_dashboard()

        assert blocker.args == [False]


class TestStartLearning:
    def test_emits_signal_when_can_start(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_confirmed_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()
        vm.load_dashboard()

        with qtbot.waitSignal(vm.start_session_requested, timeout=1000):
            vm.start_learning()

    def test_does_not_emit_when_cannot_start(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_no_menu_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()
        vm.load_dashboard()

        with qtbot.assertNotEmitted(vm.start_session_requested):
            vm.start_learning()


class TestEventReload:
    def test_menu_confirmed_reloads_dashboard(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_confirmed_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()
        vm.load_dashboard()
        assert query.call_count == 1

        bus.emit(MenuConfirmed(menu_id=uuid4(), target_date=date.today()))

        assert query.call_count == 2

    def test_session_completed_reloads_dashboard(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSessionQueryService(_confirmed_dashboard())
        vm = TodayViewModel(bus, query)
        vm.activate()
        vm.load_dashboard()
        assert query.call_count == 1

        bus.emit(SessionCompleted(session_id=uuid4()))

        assert query.call_count == 2
