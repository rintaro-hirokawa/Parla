"""Tests for CalendarWidget."""

from datetime import date

from parla.services.query_models import CalendarMarker
from parla.ui.widgets.calendar_widget import CalendarWidget


class TestCalendarWidget:
    def test_set_markers_stores_data(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        markers = [
            CalendarMarker(date=date(2026, 4, 1), session_count=1),
            CalendarMarker(date=date(2026, 4, 5), session_count=3),
        ]
        widget.set_markers(markers)
        assert len(widget.markers) == 2
        assert widget.markers[date(2026, 4, 1)] == 1
        assert widget.markers[date(2026, 4, 5)] == 3

    def test_empty_markers(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        widget.set_markers([])
        assert widget.markers == {}

    def test_set_month(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        widget.set_month(2026, 3)
        assert widget.monthShown() == 3
        assert widget.yearShown() == 2026

    def test_date_selected_signal(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        with qtbot.waitSignal(widget.date_selected, timeout=1000) as blocker:
            widget._on_clicked(widget.selectedDate())
        # Should receive a datetime.date object
        assert isinstance(blocker.args[0], date)

    def test_paint_with_markers_no_crash(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        markers = [
            CalendarMarker(date=date(2026, 4, 10), session_count=2),
        ]
        widget.set_markers(markers)
        widget.set_month(2026, 4)
        widget.show()
        qtbot.waitExposed(widget)

    def test_overwrite_markers(self, qtbot):
        widget = CalendarWidget()
        qtbot.addWidget(widget)
        widget.set_markers([CalendarMarker(date=date(2026, 4, 1), session_count=1)])
        widget.set_markers([CalendarMarker(date=date(2026, 5, 1), session_count=2)])
        assert date(2026, 4, 1) not in widget.markers
        assert widget.markers[date(2026, 5, 1)] == 2
