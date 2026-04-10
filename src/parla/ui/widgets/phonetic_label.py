"""English text label with phonetic symbols and word highlighting."""

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from parla.ui import theme


@dataclass
class PhoneticWord:
    """A word paired with its phonetic transcription."""

    text: str
    phonetic: str


@dataclass
class _WordLayout:
    """Pre-computed position for a single word."""

    index: int
    x: int
    y: int
    col_width: int


class PhoneticLabel(QWidget):
    """Displays English text with phonetic symbols below each word.

    Supports ON/OFF toggle for phonetics and single-word highlighting.
    Used in E6 (phase C workspace).
    """

    _WORD_SPACING = theme.SPACING_MD
    _LINE_SPACING = theme.SPACING_SM
    _PADDING = theme.SPACING_SM

    _TEXT_COLOR = theme.TEXT_PRIMARY
    _PHONETIC_COLOR = theme.TEXT_SECONDARY
    _HIGHLIGHT_COLOR = theme.HIGHLIGHT_BG

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._words: Sequence[PhoneticWord] = ()
        self._phonetic_visible: bool = True
        self._highlighted_index: int | None = None
        self._layout_cache: list[_WordLayout] = []
        self._cached_line_height: int = 0
        self._cached_lines: int = 0

        self._text_font = QFont()
        self._text_font.setPointSize(theme.FONT_SIZE_LG)
        self._text_fm = QFontMetrics(self._text_font)

        self._phonetic_font = QFont()
        self._phonetic_font.setPointSize(theme.FONT_SIZE_SM)
        self._phonetic_font.setItalic(True)
        self._phonetic_fm = QFontMetrics(self._phonetic_font)

    @property
    def is_phonetic_visible(self) -> bool:
        return self._phonetic_visible

    @property
    def highlighted_index(self) -> int | None:
        return self._highlighted_index

    def set_words(self, words: Sequence[PhoneticWord]) -> None:
        self._words = words
        self._highlighted_index = None
        self._invalidate_layout()
        self.updateGeometry()
        self.update()

    def set_phonetic_visible(self, visible: bool) -> None:
        self._phonetic_visible = visible
        self._invalidate_layout()
        self.updateGeometry()
        self.update()

    def highlight_word(self, index: int) -> None:
        if 0 <= index < len(self._words):
            self._highlighted_index = index
            self.update()

    def clear_highlight(self) -> None:
        self._highlighted_index = None
        self.update()

    def sizeHint(self) -> QSize:
        if not self._words:
            return QSize(100, 30)
        available = self.width() if self.width() > 0 else 400
        self._ensure_layout(available)
        total_height = (
            self._cached_lines * self._cached_line_height
            + (self._cached_lines - 1) * self._LINE_SPACING
            + self._PADDING * 2
        )
        return QSize(available, total_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 30)

    def resizeEvent(self, event: object) -> None:
        self._invalidate_layout()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._words:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._ensure_layout(self.width())
        text_ascent = self._text_fm.ascent()
        text_height = self._text_fm.height()
        phonetic_ascent = self._phonetic_fm.ascent()

        for wl in self._layout_cache:
            word = self._words[wl.index]

            if wl.index == self._highlighted_index:
                painter.fillRect(
                    wl.x - 2, wl.y - 1, wl.col_width + 4, self._cached_line_height + 2,
                    self._HIGHLIGHT_COLOR,
                )

            painter.setFont(self._text_font)
            painter.setPen(self._TEXT_COLOR)
            painter.drawText(wl.x, wl.y + text_ascent, word.text)

            if self._phonetic_visible and word.phonetic:
                painter.setFont(self._phonetic_font)
                painter.setPen(self._PHONETIC_COLOR)
                painter.drawText(wl.x, wl.y + text_height + phonetic_ascent, word.phonetic)

        painter.end()

    def _invalidate_layout(self) -> None:
        self._layout_cache.clear()

    def _ensure_layout(self, available_width: int) -> None:
        """Compute word positions if cache is empty."""
        if self._layout_cache and self._words:
            return

        text_height = self._text_fm.height()
        phonetic_height = self._phonetic_fm.height() if self._phonetic_visible else 0
        self._cached_line_height = text_height + phonetic_height + self._LINE_SPACING

        max_width = available_width - self._PADDING * 2
        x = self._PADDING
        y = self._PADDING
        lines = 1

        for i, word in enumerate(self._words):
            word_width = self._text_fm.horizontalAdvance(word.text)
            col_width = word_width
            if self._phonetic_visible:
                phonetic_width = self._phonetic_fm.horizontalAdvance(word.phonetic)
                col_width = max(word_width, phonetic_width)

            if x > self._PADDING and x + col_width > max_width:
                x = self._PADDING
                y += self._cached_line_height + self._LINE_SPACING
                lines += 1

            self._layout_cache.append(_WordLayout(index=i, x=x, y=y, col_width=col_width))
            x += col_width + self._WORD_SPACING

        self._cached_lines = lines
