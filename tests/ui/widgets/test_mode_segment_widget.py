"""Tests for ModeSegmentWidget."""

from parla.ui.widgets.mode_segment_widget import ModeSegmentWidget


class TestModeSegmentWidget:
    def test_initial_mode(self, qtbot) -> None:
        w = ModeSegmentWidget([("a", "A"), ("b", "B"), ("c", "C")])
        qtbot.addWidget(w)
        assert w.current_mode == "a"

    def test_set_mode(self, qtbot) -> None:
        w = ModeSegmentWidget([("a", "A"), ("b", "B"), ("c", "C")])
        qtbot.addWidget(w)
        w.set_mode("b")
        assert w.current_mode == "b"

    def test_signal_emitted_on_mode_change(self, qtbot) -> None:
        w = ModeSegmentWidget([("a", "A"), ("b", "B")])
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.mode_changed, timeout=1000):
            w.set_mode("b")

    def test_no_signal_on_same_mode(self, qtbot) -> None:
        w = ModeSegmentWidget([("a", "A"), ("b", "B")])
        qtbot.addWidget(w)
        signals = []
        w.mode_changed.connect(signals.append)
        w.set_mode("a")  # already active
        assert len(signals) == 0
