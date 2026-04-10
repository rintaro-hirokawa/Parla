"""Parla UI theme constants and QSS generator.

Centralises colour palette, font definitions, spacing scale, and
application-wide Qt Style Sheet for the dark theme.
"""

from PySide6.QtGui import QColor, QPen

# ---------------------------------------------------------------------------
# Colour palette (semantic names)
# ---------------------------------------------------------------------------

# Backgrounds
BG_PRIMARY = QColor(30, 30, 30)
BG_SECONDARY = QColor(40, 40, 40)
BG_SURFACE = QColor(50, 50, 50)

# Text
TEXT_PRIMARY = QColor(230, 230, 230)
TEXT_SECONDARY = QColor(150, 150, 150)
TEXT_DISABLED = QColor(120, 120, 120)

# Accent / status
ACCENT_GREEN = QColor(0, 200, 100)
ACCENT_GREEN_HOVER = QColor(0, 220, 110)
ACCENT_GREEN_PRESSED = QColor(0, 170, 85)
ACCENT_BLUE = QColor(80, 180, 255)
ACCENT_TEAL = QColor(0, 180, 120)
ACCENT_YELLOW = QColor(255, 220, 80)
WARNING = QColor(220, 80, 40)
ERROR = QColor(220, 60, 60)

# Borders / grid
BORDER = QColor(80, 80, 80)
GRID_LINE = QColor(60, 60, 60)

# Semi-transparent
HIGHLIGHT_BG = QColor(255, 220, 80, 80)
BAND_BG = QColor(0, 150, 100, 40)

# ---------------------------------------------------------------------------
# Pre-built pens (used by QPainter widgets)
# ---------------------------------------------------------------------------

PEN_GRID_LINE = QPen(GRID_LINE, 1)
PEN_BORDER = QPen(BORDER, 1)
PEN_ACCENT_BLUE_2 = QPen(ACCENT_BLUE, 2)

# ---------------------------------------------------------------------------
# Font families
# ---------------------------------------------------------------------------

FONT_FAMILY = '"Noto Sans JP", "Yu Gothic UI", "Meiryo", sans-serif'

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
    """Return the application-wide QSS string for the dark theme."""
    return f"""
/* ── Base ── */
QWidget {{
    background-color: {rgb(BG_PRIMARY)};
    color: {rgb(TEXT_PRIMARY)};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD}pt;
}}

/* ── Labels ── */
QLabel {{
    background-color: transparent;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {rgb(ACCENT_GREEN)};
    color: {rgb(BG_PRIMARY)};
    border: none;
    border-radius: 4px;
    padding: {SPACING_SM}px {SPACING_XL}px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {rgb(ACCENT_GREEN_HOVER)};
}}
QPushButton:pressed {{
    background-color: {rgb(ACCENT_GREEN_PRESSED)};
}}
QPushButton:disabled {{
    background-color: {rgb(BG_SURFACE)};
    color: {rgb(TEXT_DISABLED)};
}}

/* ── Text inputs ── */
QLineEdit, QPlainTextEdit {{
    background-color: {rgb(BG_SECONDARY)};
    color: {rgb(TEXT_PRIMARY)};
    border: 1px solid {rgb(BORDER)};
    border-radius: 4px;
    padding: {SPACING_SM}px;
    selection-background-color: {rgba(HIGHLIGHT_BG)};
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: {rgb(ACCENT_GREEN)};
}}

/* ── Scroll area ── */
QScrollArea {{
    background-color: {rgb(BG_PRIMARY)};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {rgb(BG_PRIMARY)};
}}
QScrollBar:vertical {{
    background-color: {rgb(BG_SECONDARY)};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {rgb(BORDER)};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Tab bar ── */
QTabBar::tab {{
    background-color: {rgb(BG_SECONDARY)};
    color: {rgb(TEXT_SECONDARY)};
    padding: {SPACING_SM}px {SPACING_LG}px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {rgb(TEXT_PRIMARY)};
    border-bottom-color: {rgb(ACCENT_GREEN)};
}}
QTabBar::tab:hover {{
    color: {rgb(TEXT_PRIMARY)};
}}

/* ── Combo box ── */
QComboBox {{
    background-color: {rgb(BG_SECONDARY)};
    color: {rgb(TEXT_PRIMARY)};
    border: 1px solid {rgb(BORDER)};
    border-radius: 4px;
    padding: {SPACING_SM}px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {rgb(BG_SECONDARY)};
    color: {rgb(TEXT_PRIMARY)};
    selection-background-color: {rgb(BG_SURFACE)};
    border: 1px solid {rgb(BORDER)};
}}

/* ── Slider ── */
QSlider::groove:horizontal {{
    background-color: {rgb(BG_SECONDARY)};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {rgb(ACCENT_GREEN)};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::groove:vertical {{
    background-color: {rgb(BG_SECONDARY)};
    width: 4px;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background-color: {rgb(ACCENT_GREEN)};
    width: 14px;
    height: 14px;
    margin: 0 -5px;
    border-radius: 7px;
}}
"""
