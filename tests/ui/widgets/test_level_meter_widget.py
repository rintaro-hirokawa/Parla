"""Tests for LevelMeterWidget."""

from unittest.mock import patch

from parla.ui.widgets.level_meter_widget import LevelMeterWidget, _rms_to_db


class TestLevelMeterWidget:
    def test_initial_level_is_zero(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        assert widget.level == 0.0

    def test_set_level_updates_property(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.5)
        assert widget.level == 0.5

    def test_warning_below_threshold(self, qtbot):
        widget = LevelMeterWidget(warning_threshold=0.1)
        qtbot.addWidget(widget)
        widget.set_level(0.05)
        assert widget.is_warning is True

    def test_no_warning_above_threshold(self, qtbot):
        widget = LevelMeterWidget(warning_threshold=0.1)
        qtbot.addWidget(widget)
        widget.set_level(0.5)
        assert widget.is_warning is False

    def test_no_warning_at_threshold(self, qtbot):
        widget = LevelMeterWidget(warning_threshold=0.1)
        qtbot.addWidget(widget)
        widget.set_level(0.1)
        assert widget.is_warning is False

    def test_level_clamped_above_one(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(1.5)
        assert widget.level == 1.0

    def test_level_clamped_below_zero(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(-0.3)
        assert widget.level == 0.0

    def test_set_level_triggers_repaint(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        with patch.object(widget, "update") as mock_update:
            widget.set_level(0.7)
            mock_update.assert_called_once()

    def test_paint_no_crash(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.6)
        widget.show()
        qtbot.waitExposed(widget)

    def test_paint_warning_no_crash(self, qtbot):
        widget = LevelMeterWidget(warning_threshold=0.5)
        qtbot.addWidget(widget)
        widget.set_level(0.1)
        widget.show()
        qtbot.waitExposed(widget)

    def test_size_hint(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        hint = widget.sizeHint()
        assert hint.width() > 0
        assert hint.height() > 0


class TestDbConversion:
    def test_rms_to_db_full_scale(self):
        assert _rms_to_db(1.0) == 0.0

    def test_rms_to_db_half(self):
        db = _rms_to_db(0.5)
        assert -7.0 < db < -6.0  # ~-6.02 dB

    def test_rms_to_db_zero_returns_floor(self):
        assert _rms_to_db(0.0) == -60.0

    def test_rms_to_db_tiny_returns_floor(self):
        assert _rms_to_db(0.0001) == -60.0  # -80 dB clamped to -60


class TestDbProperties:
    def test_level_db_at_zero(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        assert widget.level_db == -60.0

    def test_level_db_updates(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(1.0)
        assert widget.level_db == 0.0

    def test_level_db_at_half(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.5)
        assert -7.0 < widget.level_db < -6.0

    def test_peak_db_tracks_maximum(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.8)
        widget.set_level(0.3)
        # Peak should still be at the higher value
        assert widget.peak_db > _rms_to_db(0.3)


class TestClipping:
    def test_not_clipping_initially(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        assert widget.is_clipping is False

    def test_clipping_at_high_level(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.95)  # ~-0.45 dBFS, above -1 dB threshold
        assert widget.is_clipping is True

    def test_not_clipping_at_moderate_level(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(0.5)  # ~-6 dBFS
        assert widget.is_clipping is False

    def test_paint_clipping_no_crash(self, qtbot):
        widget = LevelMeterWidget()
        qtbot.addWidget(widget)
        widget.set_level(1.0)
        widget.show()
        qtbot.waitExposed(widget)
