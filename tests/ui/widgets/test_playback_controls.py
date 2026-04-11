"""Tests for PlaybackControlsWidget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from parla.ui.widgets.playback_controls import PlaybackControlsWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class TestButtonSignals:
    def test_play_pause_emits_signal(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.play_pause_clicked, timeout=1000):
            w._play_pause_btn.click()

    def test_reset_emits_signal(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.reset_requested, timeout=1000):
            w._reset_btn.click()

    def test_skip_forward_emits_signal(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.skip_requested, timeout=1000) as blocker:
            w._forward_btn.click()
        assert blocker.args == [2.0]

    def test_skip_backward_emits_signal(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.skip_requested, timeout=1000) as blocker:
            w._back_btn.click()
        assert blocker.args == [-2.0]


class TestSlots:
    def test_set_duration(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        w.set_duration(90.0)
        assert w._slider.maximum() == 90000
        assert "1:30" in w._time_label.text()

    def test_set_position(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        w.set_duration(60.0)
        w.set_position(5.0)
        assert w._slider.value() == 5000
        assert "0:05" in w._time_label.text()

    def test_set_playing_shows_pause(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        w.set_playing(True)
        assert w._play_pause_btn.text() == "⏸"

    def test_set_playing_shows_play(self, qtbot: QtBot) -> None:
        w = PlaybackControlsWidget()
        qtbot.addWidget(w)
        w.set_playing(True)
        w.set_playing(False)
        assert w._play_pause_btn.text() == "▶"
