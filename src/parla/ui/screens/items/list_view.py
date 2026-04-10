"""View for learning item list screen (SCREEN-C2)."""

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

CATEGORY_OPTIONS: list[tuple[LearningItemCategory | None, str]] = [
    (None, "全て"),
    ("文法", "文法"),
    ("語彙", "語彙"),
    ("コロケーション", "コロケーション"),
    ("構文", "構文"),
    ("表現", "表現"),
]

STATUS_OPTIONS: list[tuple[LearningItemStatus | None, str]] = [
    (None, "全て"),
    ("auto_stocked", "auto_stocked"),
    ("review_later", "review_later"),
    ("dismissed", "dismissed"),
]

SRS_OPTIONS: list[tuple[int | None, str]] = [
    (None, "全て"),
    *((i, str(i)) for i in range(9)),
]


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
        for _, label in CATEGORY_OPTIONS:
            self._category_combo.addItem(label)
        filter_bar.addWidget(self._category_combo)

        self._status_combo = QComboBox()
        for _, label in STATUS_OPTIONS:
            self._status_combo.addItem(label)
        filter_bar.addWidget(self._status_combo)

        self._srs_combo = QComboBox()
        for _, label in SRS_OPTIONS:
            self._srs_combo.addItem(label)
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

    def _on_items_loaded(self, items: tuple[LearningItemRow, ...]) -> None:
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

        category = CATEGORY_OPTIONS[self._category_combo.currentIndex()][0]
        status = STATUS_OPTIONS[self._status_combo.currentIndex()][0]
        srs_stage = SRS_OPTIONS[self._srs_combo.currentIndex()][0]

        self._vm.apply_filter(category=category, status=status, srs_stage=srs_stage)

    def _on_clear_filter(self) -> None:
        self._updating = True
        self._category_combo.setCurrentIndex(0)
        self._status_combo.setCurrentIndex(0)
        self._srs_combo.setCurrentIndex(0)
        self._updating = False
        self._vm.apply_filter()
