"""Tests for ProgressDotsWidget."""

from parla.ui.widgets.progress_dots_widget import ProgressDotsWidget


class TestProgressDotsWidget:
    def test_initial_state(self, qtbot) -> None:
        w = ProgressDotsWidget()
        qtbot.addWidget(w)
        assert w._count == 0
        assert w._current == 0

    def test_set_count(self, qtbot) -> None:
        w = ProgressDotsWidget()
        qtbot.addWidget(w)
        w.set_count(5)
        assert w._count == 5
        assert w.width() > 0

    def test_set_current(self, qtbot) -> None:
        w = ProgressDotsWidget()
        qtbot.addWidget(w)
        w.set_count(5)
        w.set_current(3)
        assert w._current == 3

    def test_paint_does_not_crash(self, qtbot) -> None:
        w = ProgressDotsWidget()
        qtbot.addWidget(w)
        w.show()
        w.set_count(5)
        w.set_current(2)
        w.repaint()

    def test_zero_count_no_crash(self, qtbot) -> None:
        w = ProgressDotsWidget()
        qtbot.addWidget(w)
        w.show()
        w.set_count(0)
        w.repaint()
