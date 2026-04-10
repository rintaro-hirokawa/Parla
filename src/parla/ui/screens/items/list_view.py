"""View for learning item list screen (SCREEN-C2)."""

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.domain.learning_item import LearningItemCategory, LearningItemStatus
from parla.services.query_models import LearningItemRow
from parla.ui.screens.items.list_view_model import ListViewModel

_CATEGORIES = ("全て", "文法", "語彙", "コロケーション", "構文", "表現")
_STATUSES = ("全て", "auto_stocked", "review_later", "dismissed")
_SRS_STAGES = ("全て", "0", "1", "2", "3", "4", "5", "6", "7", "8")


class ListView(QWidget):
    """Learning item list view with filter controls."""

    def __init__(self, view_model: ListViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._updating = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        filter_bar = QHBoxLayout()

        self._category_combo = QComboBox()
        self._category_combo.addItems(_CATEGORIES)
        filter_bar.addWidget(self._category_combo)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUSES)
        filter_bar.addWidget(self._status_combo)

        self._srs_combo = QComboBox()
        self._srs_combo.addItems(_SRS_STAGES)
        filter_bar.addWidget(self._srs_combo)

        self._clear_btn = QPushButton("リセット")
        filter_bar.addWidget(self._clear_btn)

        layout.addLayout(filter_bar)

        self._item_list = QListWidget()
        layout.addWidget(self._item_list)

    def _connect_signals(self) -> None:
        self._vm.items_loaded.connect(self._on_items_loaded)
        self._item_list.itemClicked.connect(self._on_item_clicked)
        self._category_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._srs_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._clear_btn.clicked.connect(self._on_clear_filter)

    def _on_items_loaded(self, items: list[LearningItemRow]) -> None:
        self._item_list.clear()
        for row in items:
            item = QListWidgetItem(f"{row.pattern} ({row.category}) - SRS {row.srs_stage}")
            item.setData(Qt.ItemDataRole.UserRole, row.id)
            self._item_list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        item_id = item.data(Qt.ItemDataRole.UserRole)
        if item_id is not None:
            self._vm.select_item(item_id)

    def _on_filter_changed(self) -> None:
        if self._updating:
            return

        cat_idx = self._category_combo.currentIndex()
        status_idx = self._status_combo.currentIndex()
        srs_idx = self._srs_combo.currentIndex()

        category = cast(LearningItemCategory, _CATEGORIES[cat_idx]) if cat_idx > 0 else None
        status = cast(LearningItemStatus, _STATUSES[status_idx]) if status_idx > 0 else None
        srs_stage = int(_SRS_STAGES[srs_idx]) if srs_idx > 0 else None

        self._vm.apply_filter(category=category, status=status, srs_stage=srs_stage)

    def _on_clear_filter(self) -> None:
        self._updating = True
        self._category_combo.setCurrentIndex(0)
        self._status_combo.setCurrentIndex(0)
        self._srs_combo.setCurrentIndex(0)
        self._updating = False
        self._vm.clear_filter()
