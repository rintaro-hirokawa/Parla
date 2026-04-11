"""Session header widget — always visible at top during a session."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from parla.ui import theme
from parla.ui.screens.session.session_context import SessionContext


class SessionHeaderWidget(QWidget):
    """Top bar: progress label (left), phase label (center), timer (right).

    Connects directly to ``SessionContext`` signals.
    """

    def __init__(self, context: SessionContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context

        self.setStyleSheet(
            f"background: {theme.rgb(theme.BG_CARD)}; "
            f"border-bottom: 1px solid {theme.rgb(theme.BORDER)};"
        )
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_SECONDARY)}; font-size: 13px; border: none;"
        )
        layout.addWidget(self._progress_label)

        layout.addStretch()

        self._elapsed_label = QLabel("00:00")
        self._elapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._elapsed_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_PRIMARY)}; font-size: 15px; "
            f"font-weight: 600; font-family: Consolas, monospace; border: none;"
        )
        layout.addWidget(self._elapsed_label)

        layout.addStretch()

        self._word_count_label = QLabel("0 words")
        self._word_count_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; border: none;"
        )
        layout.addWidget(self._word_count_label)

        self._wpm_label = QLabel("0.0 WPM")
        self._wpm_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; "
            f"margin-left: 12px; border: none;"
        )
        layout.addWidget(self._wpm_label)

        # Connect to context signals
        self._ctx.progress_changed.connect(self._on_progress)
        self._ctx.elapsed_changed.connect(self._on_elapsed)
        self._ctx.words_changed.connect(self._on_words)
        self._ctx.wpm_changed.connect(self._on_wpm)

    # ------------------------------------------------------------------
    # Public accessors for testing
    # ------------------------------------------------------------------

    def progress_text(self) -> str:
        return self._progress_label.text()

    def elapsed_text(self) -> str:
        return self._elapsed_label.text()

    def word_count_text(self) -> str:
        return self._word_count_label.text()

    def wpm_text(self) -> str:
        return self._wpm_label.text()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_progress(self) -> None:
        self._progress_label.setText(self._ctx.progress_label)

    def _on_elapsed(self, _seconds: int) -> None:
        self._elapsed_label.setText(self._ctx.elapsed_display)

    def _on_words(self, count: int) -> None:
        self._word_count_label.setText(f"{count} words")

    def _on_wpm(self, wpm: float) -> None:
        self._wpm_label.setText(f"{wpm:.1f} WPM")
