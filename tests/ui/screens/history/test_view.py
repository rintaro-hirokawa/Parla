"""Tests for HistoryView (SCREEN-C4)."""

from datetime import date

from parla.event_bus import EventBus
from parla.services.query_models import DailySummary
from parla.ui.screens.history.view import HistoryView
from parla.ui.screens.history.view_model import HistoryViewModel
from tests.ui.screens.history.conftest import FakeHistoryQueryService, make_overview, make_summary


def _make_view(qtbot, overview=None, summary=None):
    bus = EventBus()
    service = FakeHistoryQueryService(overview=overview, summary=summary)
    vm = HistoryViewModel(bus, service)
    view = HistoryView(vm)
    qtbot.addWidget(view)
    vm.activate()
    return view, vm, bus


class TestOverviewDisplay:
    def test_calendar_markers_set(self, qtbot) -> None:
        overview = make_overview()
        view, vm, _bus = _make_view(qtbot, overview=overview)
        vm.load_overview()

        markers = view._calendar.markers
        assert date(2026, 4, 1) in markers
        assert date(2026, 4, 5) in markers
        assert markers[date(2026, 4, 5)] == 2

    def test_wpm_chart_populated(self, qtbot) -> None:
        overview = make_overview()
        view, vm, _bus = _make_view(qtbot, overview=overview)
        vm.load_overview()

        assert len(view._wpm_chart.data_points) == 2


class TestDailySummary:
    def test_summary_labels_populated(self, qtbot) -> None:
        summary = make_summary()
        view, vm, _bus = _make_view(qtbot, summary=summary)
        vm.select_date(date(2026, 4, 5))

        assert "2" in view._session_count_label.text()
        assert "3" in view._passage_count_label.text()
        assert "5" in view._new_item_label.text()
        assert "10" in view._review_count_label.text()
        assert "80" in view._review_accuracy_label.text()
        assert "130" in view._avg_wpm_label.text()

    def test_summary_zero_reviews_shows_placeholder(self, qtbot) -> None:
        summary = DailySummary(
            date=date(2026, 4, 1),
            session_count=1,
            review_count=0,
            review_correct_count=0,
        )
        view, vm, _bus = _make_view(qtbot, summary=summary)
        vm.select_date(date(2026, 4, 1))

        assert "---" in view._review_accuracy_label.text()


class TestCalendarInteraction:
    def test_date_click_loads_summary(self, qtbot) -> None:
        summary = make_summary()
        view, vm, _bus = _make_view(qtbot, summary=summary)

        with qtbot.waitSignal(vm.daily_summary_loaded, timeout=1000):
            view._calendar.date_selected.emit(date(2026, 4, 5))
