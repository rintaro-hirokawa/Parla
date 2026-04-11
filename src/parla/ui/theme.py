"""Parla UI theme constants and QSS generator.

Centralises colour palette, font definitions, spacing scale, and
application-wide Qt Style Sheet for the light theme.
"""

from PySide6.QtGui import QColor, QPen

# ---------------------------------------------------------------------------
# Colour palette (semantic names)
# ---------------------------------------------------------------------------

# Backgrounds
BG_PRIMARY = QColor(244, 246, 251)  # #f4f6fb
BG_CARD = QColor(255, 255, 255)  # #ffffff
BG_SURFACE = QColor(248, 249, 252)  # #f8f9fc

# Text
TEXT_PRIMARY = QColor(26, 26, 46)  # #1a1a2e
TEXT_SECONDARY = QColor(107, 114, 128)  # #6b7280
TEXT_TERTIARY = QColor(156, 163, 175)  # #9ca3af
TEXT_DISABLED = QColor(192, 197, 208)  # #c0c5d0

# Accent / primary action
ACCENT = QColor(79, 110, 247)  # #4f6ef7
ACCENT_HOVER = QColor(59, 93, 231)  # #3b5de7
ACCENT_LIGHT = QColor(240, 242, 255)  # #f0f2ff
ACCENT_BORDER = QColor(199, 208, 247)  # #c7d0f7
ACCENT_SUBTLE = QColor(238, 241, 254)  # #eef1fe

# Status — correct
CORRECT_BG = QColor(236, 253, 245)  # #ecfdf5
CORRECT_TEXT = QColor(5, 150, 105)  # #059669
CORRECT_BORDER = QColor(167, 243, 208)  # #a7f3d0

# Status — needs review
REVIEW_BG = QColor(254, 243, 199)  # #fef3c7
REVIEW_TEXT = QColor(180, 83, 9)  # #b45309
REVIEW_BORDER = QColor(253, 230, 138)  # #fde68a

# Warning / error
WARNING = QColor(245, 158, 11)  # #f59e0b
ERROR = QColor(239, 68, 68)  # #ef4444

# Borders / grid
BORDER = QColor(232, 234, 240)  # #e8eaf0
BORDER_LIGHT = QColor(238, 240, 245)  # #eef0f5
BORDER_SECONDARY = QColor(224, 228, 237)  # #e0e4ed
GRID_LINE = QColor(209, 213, 224)  # #d1d5e0

# Hints
HINT_BG1 = QColor(240, 242, 255)  # #f0f2ff
HINT_BG2 = QColor(248, 249, 252)  # #f8f9fc
HINT_TEXT2 = QColor(75, 85, 99)  # #4b5563
HINT_BORDER = QColor(209, 213, 224)  # #d1d5e0

# Waveform
WAVE_ACTIVE = QColor(79, 110, 247)  # #4f6ef7
WAVE_IDLE = QColor(199, 208, 247)  # #c7d0f7
WAVE_BG = QColor(248, 249, 252)  # #f8f9fc
WAVE_LINE = QColor(224, 228, 237)  # #e0e4ed

# Semi-transparent
HIGHLIGHT_BG = QColor(79, 110, 247, 30)
BAND_BG = QColor(79, 110, 247, 20)


# ---------------------------------------------------------------------------
# Pre-built pens (used by QPainter widgets)
# ---------------------------------------------------------------------------

PEN_GRID_LINE = QPen(GRID_LINE, 1)
PEN_BORDER = QPen(BORDER, 1)
PEN_ACCENT_BLUE_2 = QPen(ACCENT, 2)

# ---------------------------------------------------------------------------
# Font families
# ---------------------------------------------------------------------------

FONT_FAMILY = '"Noto Sans JP", "Yu Gothic UI", "Meiryo", "Segoe UI", sans-serif'

# ---------------------------------------------------------------------------
# Font sizes (point)
# ---------------------------------------------------------------------------

FONT_SIZE_XS = 7
FONT_SIZE_SM = 9
FONT_SIZE_MD = 11
FONT_SIZE_LG = 14
FONT_SIZE_XL = 18

# ---------------------------------------------------------------------------
# Spacing scale (px)
# ---------------------------------------------------------------------------

SPACING_XS = 2
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 12
SPACING_XL = 16
SPACING_XXL = 24

# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

WINDOW_INITIAL_SIZE = (1024, 768)
WINDOW_MIN_SIZE = (800, 600)


# ---------------------------------------------------------------------------
# QSS generator
# ---------------------------------------------------------------------------

def rgb(color: QColor) -> str:
    """Format QColor as ``rgb(r, g, b)`` for use in QSS."""
    return f"rgb({color.red()}, {color.green()}, {color.blue()})"


def rgba(color: QColor) -> str:
    """Format QColor as ``rgba(r, g, b, a)`` for use in QSS."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def build_app_qss() -> str:
    """Return the application-wide QSS string for the light theme."""
    return f"""
/* -- Base -- */
QWidget {{
    background-color: {rgb(BG_PRIMARY)};
    color: {rgb(TEXT_PRIMARY)};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD}pt;
}}

/* -- Labels -- */
QLabel {{
    background-color: transparent;
}}

/* -- Buttons -- */
QPushButton {{
    background-color: {rgb(ACCENT)};
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: {SPACING_SM}px {SPACING_XL}px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {rgb(ACCENT_HOVER)};
}}
QPushButton:pressed {{
    background-color: {rgb(ACCENT_HOVER)};
}}
QPushButton:disabled {{
    background-color: {rgb(BORDER_SECONDARY)};
    color: {rgb(TEXT_TERTIARY)};
}}

/* -- Text inputs -- */
QLineEdit, QPlainTextEdit {{
    background-color: {rgb(BG_CARD)};
    color: {rgb(TEXT_PRIMARY)};
    border: 1px solid {rgb(BORDER)};
    border-radius: 6px;
    padding: {SPACING_SM}px;
    selection-background-color: {rgba(HIGHLIGHT_BG)};
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: {rgb(ACCENT)};
}}

/* -- Scroll area -- */
QScrollArea {{
    background-color: {rgb(BG_PRIMARY)};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {rgb(BG_PRIMARY)};
}}
QScrollBar:vertical {{
    background-color: {rgb(BG_SURFACE)};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {rgb(GRID_LINE)};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* -- Tab bar -- */
QTabBar::tab {{
    background-color: {rgb(BG_CARD)};
    color: {rgb(TEXT_SECONDARY)};
    padding: {SPACING_SM}px {SPACING_LG}px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {rgb(TEXT_PRIMARY)};
    border-bottom-color: {rgb(ACCENT)};
}}
QTabBar::tab:hover {{
    color: {rgb(TEXT_PRIMARY)};
}}

/* -- Combo box -- */
QComboBox {{
    background-color: {rgb(BG_CARD)};
    color: {rgb(TEXT_PRIMARY)};
    border: 1px solid {rgb(BORDER)};
    border-radius: 6px;
    padding: {SPACING_SM}px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {rgb(BG_CARD)};
    color: {rgb(TEXT_PRIMARY)};
    selection-background-color: {rgb(ACCENT_LIGHT)};
    border: 1px solid {rgb(BORDER)};
}}

/* -- Slider -- */
QSlider::groove:horizontal {{
    background-color: {rgb(BORDER)};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {rgb(ACCENT)};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    border: 2px solid {rgb(BG_CARD)};
}}
QSlider::groove:vertical {{
    background-color: {rgb(BORDER)};
    width: 4px;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background-color: {rgb(ACCENT)};
    width: 14px;
    height: 14px;
    margin: 0 -5px;
    border-radius: 7px;
    border: 2px solid {rgb(BG_CARD)};
}}
"""
