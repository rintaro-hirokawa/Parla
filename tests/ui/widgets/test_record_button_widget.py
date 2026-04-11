"""Tests for RecordButtonWidget."""

from parla.ui.widgets.record_button_widget import RecordButtonWidget


class TestRecordButtonWidget:
    def test_initial_state(self, qtbot) -> None:
        w = RecordButtonWidget()
        qtbot.addWidget(w)
        assert not w.recording

    def test_set_recording(self, qtbot) -> None:
        w = RecordButtonWidget()
        qtbot.addWidget(w)
        w.set_recording(True)
        assert w.recording
        w.set_recording(False)
        assert not w.recording

    def test_click_emits_signal(self, qtbot) -> None:
        from PySide6.QtCore import Qt

        w = RecordButtonWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.clicked, timeout=1000):
            qtbot.mouseClick(w, Qt.MouseButton.LeftButton)

    def test_paint_both_states(self, qtbot) -> None:
        w = RecordButtonWidget()
        qtbot.addWidget(w)
        w.show()
        w.set_recording(False)
        w.repaint()
        w.set_recording(True)
        w.advance_pulse(0.1)
        w.repaint()
