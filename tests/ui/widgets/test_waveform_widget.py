"""Tests for WaveformWidget."""

from unittest.mock import patch

from parla.ui.widgets.waveform_widget import WaveformWidget


class TestWaveformWidget:
    def test_initial_state(self, qtbot):
        widget = WaveformWidget(buffer_size=512)
        qtbot.addWidget(widget)
        assert widget.buffer_size == 512

    def test_default_buffer_size(self, qtbot):
        widget = WaveformWidget()
        qtbot.addWidget(widget)
        assert widget.buffer_size == 1024

    def test_update_samples_stores_data(self, qtbot):
        widget = WaveformWidget(buffer_size=8)
        qtbot.addWidget(widget)
        widget.update_samples([0.5, -0.3, 0.1])
        assert len(widget._buffer) == 8
        # Last 3 values should be our samples, rest are 0.0
        assert list(widget._buffer)[-3:] == [0.5, -0.3, 0.1]

    def test_update_samples_triggers_repaint(self, qtbot):
        widget = WaveformWidget(buffer_size=8)
        qtbot.addWidget(widget)
        with patch.object(widget, "update") as mock_update:
            widget.update_samples([0.5])
            mock_update.assert_called_once()

    def test_buffer_wraps_around(self, qtbot):
        widget = WaveformWidget(buffer_size=4)
        qtbot.addWidget(widget)
        widget.update_samples([0.1, 0.2, 0.3, 0.4])
        widget.update_samples([0.5, 0.6])
        assert len(widget._buffer) == 4
        assert list(widget._buffer) == [0.3, 0.4, 0.5, 0.6]

    def test_clear_resets_buffer(self, qtbot):
        widget = WaveformWidget(buffer_size=4)
        qtbot.addWidget(widget)
        widget.update_samples([0.5, 0.3])
        widget.clear()
        assert all(v == 0.0 for v in widget._buffer)

    def test_samples_clamped(self, qtbot):
        widget = WaveformWidget(buffer_size=4)
        qtbot.addWidget(widget)
        widget.update_samples([2.0, -1.5, 0.5])
        values = list(widget._buffer)[-3:]
        assert values == [1.0, -1.0, 0.5]

    def test_paint_no_crash(self, qtbot):
        widget = WaveformWidget(buffer_size=16)
        qtbot.addWidget(widget)
        widget.update_samples([0.1, -0.2, 0.5, -0.8])
        widget.show()
        qtbot.waitExposed(widget)

    def test_paint_empty_no_crash(self, qtbot):
        widget = WaveformWidget()
        qtbot.addWidget(widget)
        widget.show()
        qtbot.waitExposed(widget)

    def test_size_hint(self, qtbot):
        widget = WaveformWidget()
        qtbot.addWidget(widget)
        hint = widget.sizeHint()
        assert hint.width() > 0
        assert hint.height() > 0
