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

from parla.ui.screens.today.view import BLOCK_TYPE_LABELS

if TYPE_CHECKING:
    from PySide6.QtGui import QHideEvent, QShowEvent

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
        self._warning_label = QLabel("素材が不足しています。新しいソースを追加してください")
        self._warning_label.setWordWrap(True)
        self._warning_label.hide()
        self._add_source_button = QPushButton("ソース追加")
        self._add_source_button.hide()
        self._confirm_button = QPushButton("このメニューで確定")

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._blocks_label)
        layout.addWidget(QLabel("素材:"))
        layout.addWidget(self._source_combo)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._warning_label)
        layout.addWidget(self._add_source_button)
        layout.addWidget(self._confirm_button)

        self._vm.preview_loaded.connect(self._on_loaded)
        self._vm.generation_started.connect(self._on_gen_started)
        self._vm.generation_complete.connect(self._on_gen_complete)
        self._vm.material_exhausted.connect(self._on_material_exhausted)
        self._vm.error.connect(self._on_error)
        self._confirm_button.clicked.connect(self._vm.confirm)
        self._add_source_button.clicked.connect(self._vm.go_to_source_registration)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event: QHideEvent) -> None:
        self._vm.deactivate()
        super().hideEvent(event)

    def _on_loaded(self) -> None:
        preview = self._vm.preview
        if preview is None:
            return

        # Reset warning state — a valid menu was loaded
        self._warning_label.hide()
        self._add_source_button.hide()
        self._confirm_button.setEnabled(True)

        lines = []
        for b in preview.blocks:
            name = BLOCK_TYPE_LABELS.get(b.block_type, b.block_type)
            lines.append(f"  {name}: {b.item_count}問 ({b.estimated_minutes:.0f}分)")
        self._blocks_label.setText("\n".join(lines))

        self._source_combo.clear()
        for src in preview.active_sources:
            self._source_combo.addItem(f"{src.title} ({src.remaining_passages}残)", str(src.id))

    def _on_gen_started(self, item_count: int) -> None:
        self._progress_label.setText(f"バックグラウンド生成中... ({item_count}件)")

    def _on_gen_complete(self, success: int, failure: int) -> None:
        self._progress_label.setText(f"生成完了: 成功{success} / 失敗{failure}")

    def _on_material_exhausted(self) -> None:
        self._warning_label.show()
        self._add_source_button.show()
        if self._vm.preview is None:
            # No menu at all — disable confirmation
            self._confirm_button.setEnabled(False)

    def _on_error(self, message: str) -> None:
        self._progress_label.setText(f"エラー: {message}")
