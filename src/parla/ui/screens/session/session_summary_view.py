"""View for session end summary (SCREEN-F1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.session_summary_view_model import SessionSummaryViewModel


class SessionSummaryView(QWidget):
    """Displays session completion message."""

    def __init__(self, view_model: SessionSummaryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        self._title_label = QLabel("セッション完了")
        self._next_button = QPushButton("次へ")

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addStretch()
        layout.addWidget(self._next_button)

        self._vm.summary_loaded.connect(self._on_loaded)
        self._vm.error.connect(self._on_error)
        self._next_button.clicked.connect(self._vm.proceed)

    def _on_loaded(self) -> None:
        self._title_label.setText("セッション完了")

    def _on_error(self, message: str) -> None:
        self._title_label.setText(f"エラー: {message}")
