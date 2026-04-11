"""View for the learning item edit sheet (SCREEN-E5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from parla.ui.screens.session.item_edit_view_model import ItemEditViewModel


class ItemEditView(QDialog):
    """Modal dialog for editing learning items from Phase B."""

    def __init__(self, view_model: ItemEditViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setWindowTitle("学習項目の編集")

        self._items_layout = QVBoxLayout()
        self._close_button = QPushButton("閉じる")

        layout = QVBoxLayout(self)
        layout.addLayout(self._items_layout)
        layout.addWidget(self._close_button)

        self._close_button.clicked.connect(self._on_close)
        self._vm.item_updated.connect(self._refresh)
        self._vm.item_dismissed.connect(self._refresh)

        self._populate()

    def _populate(self) -> None:
        # Clear existing
        while self._items_layout.count():
            child = self._items_layout.takeAt(0)
            if child is not None and (w := child.widget()) is not None:
                w.deleteLater()

        for item in self._vm.items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.addWidget(QLabel(item.pattern))
            row_layout.addWidget(QLabel(item.explanation))
            dismiss_btn = QPushButton("除外")
            dismiss_btn.clicked.connect(lambda checked, iid=item.id: self._vm.dismiss_item(iid))
            row_layout.addWidget(dismiss_btn)
            self._items_layout.addWidget(row)

    def _refresh(self, _item_id: str) -> None:
        self._populate()

    def _on_close(self) -> None:
        self._vm.dismiss()
        self.accept()
