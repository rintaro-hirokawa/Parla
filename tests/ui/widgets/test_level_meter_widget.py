"""Tests for LevelMeterWidget."""

from unittest.mock import patch

from parla.ui.widgets.level_meter_widget import LevelMeterWidget


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
