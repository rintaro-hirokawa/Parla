"""Tests for TimerWidget."""

from PySide6.QtTest import QTest

from parla.ui.widgets.timer_widget import TimerMode, TimerWidget


class TestTimerWidget:
    def test_initial_state_countup(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        assert widget.is_running is False
        assert widget.elapsed_ms == 0
        assert widget.elapsed_ratio() == 0.0

    def test_initial_state_countdown(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTDOWN, duration_ms=5000)
        qtbot.addWidget(widget)
        assert widget.is_running is False
        assert widget.elapsed_ms == 0

    def test_start_sets_running(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        widget.start()
        assert widget.is_running is True
        widget.stop()

    def test_stop_preserves_elapsed(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(150)
        widget.stop()
        assert widget.is_running is False
        assert widget.elapsed_ms > 0

    def test_reset_clears_elapsed(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(150)
        widget.reset()
        assert widget.is_running is False
        assert widget.elapsed_ms == 0

    def test_countdown_emits_timeout(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTDOWN, duration_ms=200)
        qtbot.addWidget(widget)
        with qtbot.waitSignal(widget.timeout, timeout=2000):
            widget.start()
        assert widget.is_running is False

    def test_countup_does_not_emit_timeout(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTUP)
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(300)
        widget.stop()
        # No assertion for signal — just verify it didn't crash
        # and is_running was properly set by stop()
        assert widget.is_running is False

    def test_elapsed_ratio_countdown(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTDOWN, duration_ms=1000)
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(300)
        widget.stop()
        ratio = widget.elapsed_ratio()
        assert 0.1 < ratio < 0.8

    def test_elapsed_ratio_countup_no_duration(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTUP)
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(150)
        widget.stop()
        assert widget.elapsed_ratio() == 0.0

    def test_set_mode_resets(self, qtbot):
        widget = TimerWidget(mode=TimerMode.COUNTUP)
        qtbot.addWidget(widget)
        widget.start()
        QTest.qWait(150)
        widget.set_mode(TimerMode.COUNTDOWN, duration_ms=5000)
        assert widget.is_running is False
        assert widget.elapsed_ms == 0

    def test_start_idempotent(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        widget.start()
        widget.start()  # Should not crash or restart
        assert widget.is_running is True
        widget.stop()

    def test_display_shows_time(self, qtbot):
        widget = TimerWidget()
        qtbot.addWidget(widget)
        # Initial display should show 00:00
        label = widget._label
        assert "00:00" in label.text()
