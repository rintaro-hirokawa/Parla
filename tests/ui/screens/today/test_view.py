"""Tests for TodayView."""

from datetime import date
from uuid import uuid4

from parla.domain.session import BlockType, SessionPattern
from parla.event_bus import EventBus
from parla.services.query_models import MenuBlockSummary, TodayDashboard
from parla.ui.screens.today.view import TodayView
from parla.ui.screens.today.view_model import TodayViewModel


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


class TestNoSourceDisplay:
    def test_shows_no_source_cta(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, TodayDashboard(has_sources=False, has_menu=False))
        assert not view._no_source_widget.isHidden()
        assert view._no_menu_label.isHidden()
        assert view._blocks_widget.isHidden()

    def test_add_source_button_emits_signal(self, qtbot) -> None:
        view, vm, _ = _make_view(qtbot, TodayDashboard(has_sources=False, has_menu=False))
        with qtbot.waitSignal(vm.navigate_to_source_registration, timeout=1000):
            view._add_source_button.click()


class TestNoMenuDisplay:
    def test_shows_no_menu_message(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, TodayDashboard(has_sources=True, has_menu=False))
        assert not view._no_menu_label.isHidden()
        assert view._no_source_widget.isHidden()
        assert view._blocks_widget.isHidden()

    def test_start_button_disabled(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, TodayDashboard(has_sources=True, has_menu=False))
        assert not view._start_button.isEnabled()


class TestConfirmedMenuDisplay:
    def test_shows_blocks(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern=SessionPattern.REVIEW_AND_NEW,
            blocks=(
                MenuBlockSummary(block_type=BlockType.REVIEW, item_count=10, estimated_minutes=20.0),
                MenuBlockSummary(block_type=BlockType.NEW_MATERIAL, item_count=2, estimated_minutes=20.0),
            ),
            total_estimated_minutes=40.0,
            source_title="Test Source",
        )
        view, *_ = _make_view(qtbot, dash)

        assert view._no_menu_label.isHidden()
        assert not view._blocks_widget.isHidden()
        assert len(view._block_widgets) == 2

    def test_start_button_enabled(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern=SessionPattern.REVIEW_AND_NEW,
            blocks=(MenuBlockSummary(block_type=BlockType.REVIEW, item_count=5, estimated_minutes=10.0),),
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
            pattern=SessionPattern.REVIEW_ONLY,
            blocks=(MenuBlockSummary(block_type=BlockType.REVIEW, item_count=5, estimated_minutes=10.0),),
            total_estimated_minutes=10.0,
        )
        view, *_ = _make_view(qtbot, dash)
        assert not view._start_button.isEnabled()


class TestResumableSession:
    def test_shows_resume_label(self, qtbot) -> None:
        dash = TodayDashboard(
            has_sources=True,
            has_menu=False,
            has_resumable_session=True,
            resumable_session_id=uuid4(),
        )
        view, *_ = _make_view(qtbot, dash)
        assert not view._resume_label.isHidden()

    def test_hides_resume_label_when_no_session(self, qtbot) -> None:
        dash = TodayDashboard(has_sources=True, has_menu=False)
        view, *_ = _make_view(qtbot, dash)
        assert view._resume_label.isHidden()


class TestDashboardStateTransition:
    def test_transitions_from_no_source_to_has_menu(self, qtbot) -> None:
        """ダッシュボード再読み込みで表示が切り替わることを検証。"""
        bus = EventBus()
        # Start with no sources
        dash1 = TodayDashboard(has_sources=False, has_menu=False)
        query = FakeSessionQueryService(dash1)
        vm = TodayViewModel(bus, query)
        view = TodayView(vm)
        qtbot.addWidget(view)
        vm.activate()
        vm.load_dashboard()

        assert not view._no_source_widget.isHidden()
        assert view._blocks_widget.isHidden()

        # Simulate: sources added and menu composed
        dash2 = TodayDashboard(
            has_sources=True,
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern=SessionPattern.NEW_ONLY,
            blocks=(MenuBlockSummary(block_type=BlockType.NEW_MATERIAL, item_count=2, estimated_minutes=15.0),),
            total_estimated_minutes=15.0,
        )
        query._dashboard = dash2
        vm.load_dashboard()

        assert view._no_source_widget.isHidden()
        assert view._no_menu_label.isHidden()
        assert not view._blocks_widget.isHidden()
        assert view._start_button.isEnabled()


class TestStartButton:
    def test_click_emits_signal(self, qtbot) -> None:
        dash = TodayDashboard(
            has_menu=True,
            menu_confirmed=True,
            menu_id=uuid4(),
            pattern=SessionPattern.REVIEW_AND_NEW,
            blocks=(MenuBlockSummary(block_type=BlockType.REVIEW, item_count=5, estimated_minutes=10.0),),
            total_estimated_minutes=10.0,
        )
        view, vm, _ = _make_view(qtbot, dash)

        with qtbot.waitSignal(vm.start_session_requested, timeout=1000):
            view._start_button.click()
