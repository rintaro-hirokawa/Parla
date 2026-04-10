"""View for learning item detail screen (SCREEN-C3)."""

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from parla.services.query_models import LearningItemDetail
from parla.ui.screens.items.detail_view_model import DetailViewModel
from parla.ui.widgets.wpm_chart import WpmChartWidget


class DetailView(QWidget):
    """Learning item detail view with growth story and WPM chart."""

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

        # Growth story
        story_group = QGroupBox("成長ストーリー")
        story_layout = QVBoxLayout(story_group)
        utterance_layout = QHBoxLayout()
        utterance_layout.addWidget(QLabel("初出時発話:"))
        self._first_utterance_label = QLabel()
        self._first_utterance_label.setWordWrap(True)
        utterance_layout.addWidget(self._first_utterance_label, 1)
        story_layout.addLayout(utterance_layout)

        self._review_table = QTableWidget()
        self._review_table.setColumnCount(4)
        self._review_table.setHorizontalHeaderLabels(["日時", "バリエーション(日)", "正誤", "ヒントレベル"])
        self._review_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        story_layout.addWidget(self._review_table)
        scroll_layout.addWidget(story_group)

        # WPM chart
        wpm_group = QGroupBox("WPM推移")
        wpm_layout = QVBoxLayout(wpm_group)
        self._wpm_chart = WpmChartWidget()
        wpm_layout.addWidget(self._wpm_chart)
        scroll_layout.addWidget(wpm_group)

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

        self._first_utterance_label.setText(detail.first_utterance or "---")

        self._review_table.setRowCount(len(detail.review_history))
        for i, entry in enumerate(detail.review_history):
            self._review_table.setItem(i, 0, QTableWidgetItem(str(entry.attempt_date)))
            self._review_table.setItem(i, 1, QTableWidgetItem(entry.variation_ja))
            self._review_table.setItem(i, 2, QTableWidgetItem("○" if entry.correct else "×"))
            self._review_table.setItem(i, 3, QTableWidgetItem(str(entry.hint_level)))

        self._wpm_chart.set_data(detail.wpm_trend)

    def _on_not_found(self) -> None:
        self._title_label.setText("項目が見つかりません")
