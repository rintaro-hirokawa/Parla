"""Tests for WpmChartWidget."""

from datetime import datetime

from parla.services.query_models import WpmDataPoint
from parla.ui.widgets.wpm_chart import WpmChartWidget


def _make_points(wpms: list[float]) -> list[WpmDataPoint]:
    return [
        WpmDataPoint(recorded_at=datetime(2026, 4, 1 + i), wpm=w)
        for i, w in enumerate(wpms)
    ]


class TestWpmChartWidget:
    def test_set_data_stores_points(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        points = _make_points([120.0, 130.0, 140.0])
        widget.set_data(points)
        assert len(widget.data_points) == 3

    def test_set_cefr_target(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        widget.set_cefr_target("B1")
        assert widget.cefr_level == "B1"

    def test_clear_resets_state(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        widget.set_data(_make_points([100.0]))
        widget.set_cefr_target("B2")
        widget.clear()
        assert len(widget.data_points) == 0
        assert widget.cefr_level is None

    def test_paint_with_data_no_crash(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        widget.set_data(_make_points([100.0, 120.0, 115.0, 130.0]))
        widget.set_cefr_target("B1")
        widget.show()
        qtbot.waitExposed(widget)

    def test_paint_empty_no_crash(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        widget.show()
        qtbot.waitExposed(widget)

    def test_single_data_point(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        widget.set_data(_make_points([150.0]))
        widget.show()
        qtbot.waitExposed(widget)

    def test_size_hint(self, qtbot):
        widget = WpmChartWidget()
        qtbot.addWidget(widget)
        hint = widget.sizeHint()
        assert hint.width() > 0
        assert hint.height() > 0
