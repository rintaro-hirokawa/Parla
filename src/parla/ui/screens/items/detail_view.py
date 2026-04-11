"""View for learning item detail screen (SCREEN-C3)."""

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from parla.services.query_models import LearningItemDetail
from parla.ui.screens.items.detail_view_model import DetailViewModel


class DetailView(QWidget):
    """Learning item detail view."""

    def __init__(self, view_model: DetailViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        self._back_btn = QPushButton("← 戻る")
        header.addWidget(self._back_btn)
        self._title_label = QLabel()
        header.addWidget(self._title_label, 1)
        layout.addLayout(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Basic info
        info_group = QGroupBox("基本情報")
        info_form = QFormLayout(info_group)
        self._category_label = QLabel()
        info_form.addRow("カテゴリ:", self._category_label)
        self._sub_tag_label = QLabel()
        info_form.addRow("サブタグ:", self._sub_tag_label)
        self._status_label = QLabel()
        info_form.addRow("状態:", self._status_label)
        self._srs_label = QLabel()
        info_form.addRow("SRS段階:", self._srs_label)
        self._next_review_label = QLabel()
        info_form.addRow("次回復習日:", self._next_review_label)
        self._explanation_label = QLabel()
        self._explanation_label.setWordWrap(True)
        info_form.addRow("説明:", self._explanation_label)
        scroll_layout.addWidget(info_group)

        # Source info
        source_group = QGroupBox("ソース情報")
        source_layout = QVBoxLayout(source_group)
        self._source_title_label = QLabel()
        source_layout.addWidget(self._source_title_label)
        self._source_ja_label = QLabel()
        self._source_ja_label.setWordWrap(True)
        source_layout.addWidget(self._source_ja_label)
        self._source_en_label = QLabel()
        self._source_en_label.setWordWrap(True)
        source_layout.addWidget(self._source_en_label)
        scroll_layout.addWidget(source_group)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _connect_signals(self) -> None:
        self._vm.detail_loaded.connect(self._on_detail_loaded)
        self._vm.detail_not_found.connect(self._on_not_found)
        self._back_btn.clicked.connect(self._vm.go_back)

    def _on_detail_loaded(self, detail: LearningItemDetail) -> None:
        self._title_label.setText(detail.pattern)
        self._category_label.setText(detail.category)
        self._sub_tag_label.setText(detail.sub_tag or "---")
        self._status_label.setText(detail.status)
        self._srs_label.setText(str(detail.srs_stage))
        self._next_review_label.setText(
            str(detail.next_review_date) if detail.next_review_date else "---"
        )
        self._explanation_label.setText(detail.explanation)

        self._source_title_label.setText(detail.source_title)
        self._source_ja_label.setText(detail.source_sentence_ja)
        self._source_en_label.setText(detail.source_sentence_en)

    def _on_not_found(self) -> None:
        self._title_label.setText("項目が見つかりません")
