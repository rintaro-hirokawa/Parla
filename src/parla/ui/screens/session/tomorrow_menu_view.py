"""View for tomorrow's menu confirmation (SCREEN-F2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from parla.ui.screens.session.tomorrow_menu_view_model import TomorrowMenuViewModel


class TomorrowMenuView(QWidget):
    """Tomorrow's menu preview with source change and confirmation."""

    def __init__(self, view_model: TomorrowMenuViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        self._title_label = QLabel("明日のメニュー")
        self._blocks_label = QLabel("")
        self._source_combo = QComboBox()
        self._progress_label = QLabel("")
        self._confirm_button = QPushButton("このメニューで確定")

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._blocks_label)
        layout.addWidget(QLabel("素材:"))
        layout.addWidget(self._source_combo)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._confirm_button)

        self._vm.preview_loaded.connect(self._on_loaded)
        self._vm.generation_started.connect(self._on_gen_started)
        self._vm.generation_complete.connect(self._on_gen_complete)
        self._vm.error.connect(self._on_error)
        self._confirm_button.clicked.connect(self._vm.confirm)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._vm.deactivate()
        super().hideEvent(event)

    def _on_loaded(self) -> None:
        preview = self._vm.preview
        if preview is None:
            return

        lines = []
        for b in preview.blocks:
            label = {"review": "復習", "new_material": "新規素材", "consolidation": "定着"}
            name = label.get(b.block_type, b.block_type)
            lines.append(f"  {name}: {b.item_count}問 ({b.estimated_minutes:.0f}分)")
        self._blocks_label.setText("\n".join(lines))

        self._source_combo.clear()
        for src in preview.active_sources:
            self._source_combo.addItem(f"{src.title} ({src.remaining_passages}残)", str(src.id))

    def _on_gen_started(self, item_count: int) -> None:
        self._progress_label.setText(f"バックグラウンド生成中... ({item_count}件)")

    def _on_gen_complete(self, success: int, failure: int) -> None:
        self._progress_label.setText(f"生成完了: 成功{success} / 失敗{failure}")

    def _on_error(self, message: str) -> None:
        self._progress_label.setText(f"エラー: {message}")
