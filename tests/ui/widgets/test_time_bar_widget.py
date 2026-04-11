"""Tests for TimeBarWidget."""

from parla.ui.widgets.time_bar_widget import TimeBarWidget


class TestTimeBarWidget:
    def test_initial_state(self, qtbot) -> None:
        w = TimeBarWidget()
        qtbot.addWidget(w)
        assert w._ratio == 1.0
        assert w._state == "normal"

    def test_set_state_clamps_ratio(self, qtbot) -> None:
        w = TimeBarWidget()
        qtbot.addWidget(w)
        w.set_state(1.5, "normal")
        assert w._ratio == 1.0
        w.set_state(-0.5, "caution")
        assert w._ratio == 0.0
        assert w._state == "caution"

    def test_advance_pulse(self, qtbot) -> None:
        w = TimeBarWidget()
        qtbot.addWidget(w)
        w.set_state(0.1, "danger")
        w.advance_pulse(0.033)
        assert w._pulse_phase > 0

    def test_paint_does_not_crash(self, qtbot) -> None:
        w = TimeBarWidget()
        qtbot.addWidget(w)
        w.show()
        for state in ("normal", "caution", "danger"):
            w.set_state(0.5, state)
            w.repaint()
