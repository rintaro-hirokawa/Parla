"""View for passage completion summary (SCREEN-E9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.passage_summary_view_model import PassageSummaryViewModel


class PassageSummaryView(QWidget):
    """Displays passage completion summary."""

    def __init__(self, view_model: PassageSummaryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        self._topic_label = QLabel("")
        self._stats_label = QLabel("")
        self._achievement_label = QLabel("")
        self._wpm_label = QLabel("")
        self._next_button = QPushButton("次へ")

        layout = QVBoxLayout(self)
        layout.addWidget(self._topic_label)
        layout.addWidget(self._stats_label)
        layout.addWidget(self._achievement_label)
        layout.addWidget(self._wpm_label)
        layout.addWidget(self._next_button)

        self._vm.summary_loaded.connect(self._on_loaded)
        self._vm.error.connect(self._on_error)
        self._next_button.clicked.connect(self._vm.proceed)

    def _on_loaded(self) -> None:
        self._topic_label.setText(self._vm.topic)
        self._stats_label.setText(
            f"センテンス: {self._vm.sentence_count} | 新規項目: {self._vm.new_item_count}"
        )
        if self._vm.has_achievement:
            self._achievement_label.setText("通し発話達成!")
        if self._vm.wpm is not None:
            self._wpm_label.setText(f"WPM: {self._vm.wpm:.1f}")

    def _on_error(self, message: str) -> None:
        self._stats_label.setText(f"エラー: {message}")
