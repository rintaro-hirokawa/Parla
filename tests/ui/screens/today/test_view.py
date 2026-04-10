"""Tests for TodayView."""

from datetime import date
from uuid import uuid4

from parla.event_bus import EventBus
from parla.services.query_models import MenuBlockSummary, TodayDashboard
from parla.ui.screens.today.view import TodayView
from parla.ui.screens.today.view_model import TodayViewModel

BLOCK_TYPE_LABELS = {"review": "復習", "new_material": "新規素材", "consolidation": "定着"}


class FakeSessionQueryService:
    def __init__(self, dashboard: TodayDashboard | None = None) -> None:
        self._dashboard = dashboard or TodayDashboard()

    def get_today_dashboard(self, *, today: date) -> TodayDashboard:
        return self._dashboard


def _make_view(qtbot, dashboard: TodayDashboard | None = None):
    bus = EventBus()
    query = FakeSessionQueryService(dashboard)
    vm = TodayViewModel(bus, query)
    view = TodayView(vm)
    qtbot.addWidget(view)
    vm.activate()
    vm.load_dashboard()
    return view, vm, bus


class TestNoMenuDisplay:
    def test_shows_no_menu_message(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, TodayDashboard(has_menu=False))
        assert not view._no_menu_label.isHidden()
        assert view._blocks_widget.isHidden()

    def test_start_button_disabled(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, TodayDashboard(has_menu=False))
        assert not view._start_button.isEnabled()


class TestConfirmedMenuDisplay:
    def test_shows_blocks(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern="a",
            blocks=(
                MenuBlockSummary(block_type="review", item_count=10, estimated_minutes=20.0),
                MenuBlockSummary(block_type="new_material", item_count=2, estimated_minutes=20.0),
            ),
            total_estimated_minutes=40.0,
            source_title="Test Source",
        )
        view, *_ = _make_view(qtbot, dash)

        assert view._no_menu_label.isHidden()
        assert not view._blocks_widget.isHidden()
        assert view._block_list.count() == 2

    def test_start_button_enabled(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern="a",
            blocks=(MenuBlockSummary(block_type="review", item_count=5, estimated_minutes=10.0),),
            total_estimated_minutes=10.0,
        )
        view, *_ = _make_view(qtbot, dash)
        assert view._start_button.isEnabled()


class TestUnconfirmedMenuDisplay:
    def test_start_button_disabled(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=False,
            menu_id=uuid4(),
            pattern="b",
            blocks=(MenuBlockSummary(block_type="review", item_count=5, estimated_minutes=10.0),),
            total_estimated_minutes=10.0,
        )
        view, *_ = _make_view(qtbot, dash)
        assert not view._start_button.isEnabled()


class TestStartButton:
    def test_click_emits_signal(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern="a",
            blocks=(MenuBlockSummary(block_type="review", item_count=5, estimated_minutes=10.0),),
            total_estimated_minutes=10.0,
        )
        view, vm, _ = _make_view(qtbot, dash)

        with qtbot.waitSignal(vm.start_session_requested, timeout=1000):
            view._start_button.click()
