"""English text label with phonetic symbols and word highlighting."""

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


@dataclass
class PhoneticWord:
    """A word paired with its phonetic transcription."""

    text: str
    phonetic: str


class PhoneticLabel(QWidget):
    """Displays English text with phonetic symbols below each word.

    Supports ON/OFF toggle for phonetics and single-word highlighting.
    Used in E6 (phase C workspace).
    """

    _WORD_SPACING = 8
    _LINE_SPACING = 4
    _PADDING = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._words: Sequence[PhoneticWord] = ()
        self._phonetic_visible: bool = True
        self._highlighted_index: int | None = None

        self._text_font = QFont()
        self._text_font.setPointSize(14)

        self._phonetic_font = QFont()
        self._phonetic_font.setPointSize(9)
        self._phonetic_font.setItalic(True)

    @property
    def is_phonetic_visible(self) -> bool:
        return self._phonetic_visible

    @property
    def highlighted_index(self) -> int | None:
        return self._highlighted_index

    def set_words(self, words: Sequence[PhoneticWord]) -> None:
        self._words = words
        self._highlighted_index = None
        self.updateGeometry()
        self.update()

    def set_phonetic_visible(self, visible: bool) -> None:
        self._phonetic_visible = visible
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
        return self._calculate_size(self.width() if self.width() > 0 else 400)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 30)

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._words:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        text_fm = QFontMetrics(self._text_font)
        phonetic_fm = QFontMetrics(self._phonetic_font)

        text_height = text_fm.height()
        phonetic_height = phonetic_fm.height() if self._phonetic_visible else 0
        line_height = text_height + phonetic_height + self._LINE_SPACING

        x = self._PADDING
        y = self._PADDING
        max_width = self.width() - self._PADDING * 2

        for i, word in enumerate(self._words):
            word_width = text_fm.horizontalAdvance(word.text)
            col_width = word_width
            if self._phonetic_visible:
                phonetic_width = phonetic_fm.horizontalAdvance(word.phonetic)
                col_width = max(word_width, phonetic_width)

            # Wrap to next line if needed
            if x > self._PADDING and x + col_width > max_width:
                x = self._PADDING
                y += line_height + self._LINE_SPACING

            # Highlight background
            if i == self._highlighted_index:
                painter.fillRect(
                    x - 2, y - 1, col_width + 4, line_height + 2,
                    QColor(255, 220, 80, 80),
                )

            # Draw text
            painter.setFont(self._text_font)
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(x, y + text_fm.ascent(), word.text)

            # Draw phonetic
            if self._phonetic_visible and word.phonetic:
                painter.setFont(self._phonetic_font)
                painter.setPen(QColor(150, 150, 150))
                painter.drawText(x, y + text_height + phonetic_fm.ascent(), word.phonetic)

            x += col_width + self._WORD_SPACING

        painter.end()

    def _calculate_size(self, available_width: int) -> QSize:
        text_fm = QFontMetrics(self._text_font)
        phonetic_fm = QFontMetrics(self._phonetic_font)

        text_height = text_fm.height()
        phonetic_height = phonetic_fm.height() if self._phonetic_visible else 0
        line_height = text_height + phonetic_height + self._LINE_SPACING

        max_width = available_width - self._PADDING * 2
        x = self._PADDING
        lines = 1

        for word in self._words:
            word_width = text_fm.horizontalAdvance(word.text)
            col_width = word_width
            if self._phonetic_visible:
                phonetic_width = phonetic_fm.horizontalAdvance(word.phonetic)
                col_width = max(word_width, phonetic_width)

            if x > self._PADDING and x + col_width > max_width:
                x = self._PADDING
                lines += 1
            x += col_width + self._WORD_SPACING

        total_height = lines * line_height + (lines - 1) * self._LINE_SPACING + self._PADDING * 2
        return QSize(available_width, total_height)
