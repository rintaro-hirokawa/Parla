"""Tests for the theme module."""

from PySide6.QtGui import QColor, QPen

from parla.ui import theme


class TestColourConstants:
    def test_all_bg_colours_are_qcolor(self) -> None:
        assert isinstance(theme.BG_PRIMARY, QColor)
        assert isinstance(theme.BG_CARD, QColor)
        assert isinstance(theme.BG_SURFACE, QColor)

    def test_all_text_colours_are_qcolor(self) -> None:
        assert isinstance(theme.TEXT_PRIMARY, QColor)
        assert isinstance(theme.TEXT_SECONDARY, QColor)
        assert isinstance(theme.TEXT_DISABLED, QColor)

    def test_all_accent_colours_are_qcolor(self) -> None:
        assert isinstance(theme.ACCENT, QColor)
        assert isinstance(theme.ACCENT_HOVER, QColor)
        assert isinstance(theme.ACCENT_LIGHT, QColor)
        assert isinstance(theme.WARNING, QColor)
        assert isinstance(theme.ERROR, QColor)

    def test_border_colours_are_qcolor(self) -> None:
        assert isinstance(theme.BORDER, QColor)
        assert isinstance(theme.GRID_LINE, QColor)
        assert isinstance(theme.HIGHLIGHT_BG, QColor)
        assert isinstance(theme.BAND_BG, QColor)

    def test_highlight_bg_has_alpha(self) -> None:
        assert theme.HIGHLIGHT_BG.alpha() < 255

    def test_band_bg_has_alpha(self) -> None:
        assert theme.BAND_BG.alpha() < 255


class TestPens:
    def test_pre_built_pens_are_qpen(self) -> None:
        assert isinstance(theme.PEN_GRID_LINE, QPen)
        assert isinstance(theme.PEN_BORDER, QPen)
        assert isinstance(theme.PEN_ACCENT_BLUE_2, QPen)


class TestFontConstants:
    def test_font_sizes_are_positive_ints(self) -> None:
        for size in (
            theme.FONT_SIZE_XS,
            theme.FONT_SIZE_SM,
            theme.FONT_SIZE_MD,
            theme.FONT_SIZE_LG,
            theme.FONT_SIZE_XL,
        ):
            assert isinstance(size, int)
            assert size > 0

    def test_font_family_is_nonempty_string(self) -> None:
        assert isinstance(theme.FONT_FAMILY, str)
        assert len(theme.FONT_FAMILY) > 0


class TestSpacingConstants:
    def test_spacing_values_are_positive_ints(self) -> None:
        for val in (
            theme.SPACING_XS,
            theme.SPACING_SM,
            theme.SPACING_MD,
            theme.SPACING_LG,
            theme.SPACING_XL,
            theme.SPACING_XXL,
        ):
            assert isinstance(val, int)
            assert val > 0

    def test_spacing_scale_is_monotonic(self) -> None:
        values = [
            theme.SPACING_XS,
            theme.SPACING_SM,
            theme.SPACING_MD,
            theme.SPACING_LG,
            theme.SPACING_XL,
            theme.SPACING_XXL,
        ]
        for a, b in zip(values, values[1:], strict=False):
            assert a < b


class TestWindowGeometry:
    def test_initial_size_tuple(self) -> None:
        w, h = theme.WINDOW_INITIAL_SIZE
        assert w > 0 and h > 0

    def test_min_size_tuple(self) -> None:
        w, h = theme.WINDOW_MIN_SIZE
        assert w > 0 and h > 0

    def test_min_not_exceeds_initial(self) -> None:
        assert theme.WINDOW_MIN_SIZE[0] <= theme.WINDOW_INITIAL_SIZE[0]
        assert theme.WINDOW_MIN_SIZE[1] <= theme.WINDOW_INITIAL_SIZE[1]


class TestBuildAppQss:
    def test_returns_nonempty_string(self) -> None:
        qss = theme.build_app_qss()
        assert isinstance(qss, str)
        assert len(qss) > 0

    def test_contains_base_widget_rule(self) -> None:
        qss = theme.build_app_qss()
        assert "QWidget" in qss

    def test_contains_button_rule(self) -> None:
        qss = theme.build_app_qss()
        assert "QPushButton" in qss

    def test_contains_tab_bar_rule(self) -> None:
        qss = theme.build_app_qss()
        assert "QTabBar" in qss

    def test_qss_applies_without_error(self, qtbot, qapp) -> None:
        qapp.setStyleSheet(theme.build_app_qss())
        # No exception means success; reset to avoid side-effects
        qapp.setStyleSheet("")
