"""Inline error banner with optional retry button."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from parla.ui import theme


class ErrorBanner(QWidget):
    """Displays an error message inline with an optional retry button.

    Hidden by default; call :meth:`show_error` to display.
    """

    retry_clicked = Signal()

    def __init__(self, *, retryable: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._retryable = retryable

        self._message_label = QLabel()
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(f"color: {theme.rgb(theme.ERROR)}; background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, theme.SPACING_SM, 0, theme.SPACING_SM)
        layout.addWidget(self._message_label, stretch=1)

        if retryable:
            self._retry_button = QPushButton("再試行")
            self._retry_button.clicked.connect(self.retry_clicked)
            layout.addWidget(self._retry_button)
        else:
            self._retry_button = None

        self.hide()

    @property
    def retryable(self) -> bool:
        return self._retryable

    @property
    def message(self) -> str:
        return self._message_label.text()

    def show_error(self, message: str) -> None:
        """Display the error message and make the banner visible."""
        self._message_label.setText(message)
        self.show()

    def clear(self) -> None:
        """Hide the banner and clear the message."""
        self._message_label.setText("")
        self.hide()
