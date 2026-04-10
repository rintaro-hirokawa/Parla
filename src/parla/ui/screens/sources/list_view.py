"""Source list screen view (SCREEN-D2)."""

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.services.query_models import SourceSummary
from parla.ui.screens.sources.list_view_model import SourceListViewModel

STATUS_OPTIONS: list[tuple[str | None, str]] = [
    (None, "すべて"),
    ("registered", "登録済み"),
    ("generating", "生成中"),
    ("generation_failed", "生成失敗"),
    ("not_started", "未開始"),
    ("in_progress", "学習中"),
    ("completed", "完了"),
]

CEFR_OPTIONS: list[tuple[str | None, str]] = [
    (None, "すべて"),
    ("A1", "A1"),
    ("A2", "A2"),
    ("B1", "B1"),
    ("B2", "B2"),
    ("C1", "C1"),
    ("C2", "C2"),
]

STATUS_LABELS = {
    "registered": "登録済み",
    "generating": "生成中",
    "generation_failed": "生成失敗",
    "not_started": "未開始",
    "in_progress": "学習中",
    "completed": "完了",
    "archived": "アーカイブ",
}


class SourceListView(QWidget):
    """Source list with filters, progress bars, and add button."""

    def __init__(self, view_model: SourceListViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._updating_filters = False

        layout = QVBoxLayout(self)

        # --- Filters ---
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("ステータス"))
        self._status_filter = QComboBox()
        for _, label in STATUS_OPTIONS:
            self._status_filter.addItem(label)
        self._status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._status_filter)

        filter_layout.addWidget(QLabel("CEFR"))
        self._cefr_filter = QComboBox()
        for _, label in CEFR_OPTIONS:
            self._cefr_filter.addItem(label)
        self._cefr_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._cefr_filter)

        layout.addLayout(filter_layout)

        # --- Source list ---
        self._source_list = QListWidget()
        layout.addWidget(self._source_list)

        # --- Add button ---
        self._add_button = QPushButton("ソースを追加")
        self._add_button.clicked.connect(self._vm.open_registration)
        layout.addWidget(self._add_button)

        # --- Signal connections ---
        self._vm.sources_loaded.connect(self._on_sources_loaded)

    def _on_sources_loaded(self, sources: Sequence[SourceSummary]) -> None:
        self._source_list.clear()
        for source in sources:
            status_label = STATUS_LABELS.get(source.status, source.status)
            progress_pct = int(source.progress_ratio * 100)
            text = f"{source.title}  [{source.cefr_level}]  {status_label}  {progress_pct}%"
            self._source_list.addItem(QListWidgetItem(text))

    def _on_filter_changed(self) -> None:
        if self._updating_filters:
            return
        status_idx = self._status_filter.currentIndex()
        cefr_idx = self._cefr_filter.currentIndex()

        status = STATUS_OPTIONS[status_idx][0]
        cefr = CEFR_OPTIONS[cefr_idx][0]

        self._vm.load_sources(status=status, cefr_level=cefr)
