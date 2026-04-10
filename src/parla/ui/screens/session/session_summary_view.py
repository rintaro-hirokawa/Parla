"""View for session end summary (SCREEN-F1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from parla.ui.widgets.wpm_chart import WpmChartWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.session_summary_view_model import SessionSummaryViewModel


class SessionSummaryView(QWidget):
    """Displays session end summary with WPM chart."""

    def __init__(self, view_model: SessionSummaryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        self._title_label = QLabel("セッション完了")
        self._stats_label = QLabel("")
        self._wpm_chart = WpmChartWidget(parent=self)
        self._next_button = QPushButton("次へ")

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._stats_label)
        layout.addWidget(self._wpm_chart)
        layout.addWidget(self._next_button)

        self._vm.summary_loaded.connect(self._on_loaded)
        self._vm.error.connect(self._on_error)
        self._next_button.clicked.connect(self._vm.proceed)

    def _on_loaded(self) -> None:
        lines = [
            f"所要時間: {self._vm.duration_minutes:.0f}分",
            f"パッセージ: {self._vm.passage_count}",
            f"新規項目: {self._vm.new_item_count}",
            f"復習: {self._vm.review_correct_count}/{self._vm.review_count}",
            f"平均WPM: {self._vm.average_wpm:.1f}",
        ]
        self._stats_label.setText("\n".join(lines))

    def _on_error(self, message: str) -> None:
        self._stats_label.setText(f"エラー: {message}")
