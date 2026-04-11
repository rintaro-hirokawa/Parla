"""Today's Learning tab view (SCREEN-C1)."""

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.domain.session import BlockType
from parla.services.query_models import TodayDashboard
from parla.ui.screens.today.view_model import TodayViewModel

BLOCK_TYPE_LABELS = {BlockType.REVIEW: "復習", BlockType.NEW_MATERIAL: "新規素材", BlockType.CONSOLIDATION: "定着"}


class TodayView(QWidget):
    """Displays today's session menu and start button."""

    def __init__(self, view_model: TodayViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        layout = QVBoxLayout(self)

        # --- No source CTA ---
        self._no_source_widget = QWidget()
        no_source_layout = QVBoxLayout(self._no_source_widget)
        no_source_layout.setContentsMargins(0, 0, 0, 0)
        no_source_layout.addWidget(QLabel("学習を始めるにはソースを登録してください"))
        self._add_source_button = QPushButton("ソースを追加")
        self._add_source_button.clicked.connect(self._vm.go_to_source_registration)
        no_source_layout.addWidget(self._add_source_button)
        layout.addWidget(self._no_source_widget)
        self._no_source_widget.hide()

        # --- No menu message ---
        self._no_menu_label = QLabel("メニューがまだ確定されていません")
        layout.addWidget(self._no_menu_label)

        # --- Blocks display ---
        self._blocks_widget = QWidget()
        blocks_layout = QVBoxLayout(self._blocks_widget)
        blocks_layout.setContentsMargins(0, 0, 0, 0)

        self._source_label = QLabel()
        blocks_layout.addWidget(self._source_label)

        self._block_list = QListWidget()
        blocks_layout.addWidget(self._block_list)

        self._total_label = QLabel()
        blocks_layout.addWidget(self._total_label)

        layout.addWidget(self._blocks_widget)
        self._blocks_widget.hide()

        # --- Resumable session ---
        self._resume_label = QLabel("中断中のセッションがあります")
        self._resume_label.hide()
        layout.addWidget(self._resume_label)

        # --- Start button ---
        self._start_button = QPushButton("学習開始")
        self._start_button.setEnabled(False)
        self._start_button.clicked.connect(self._vm.start_learning)
        layout.addWidget(self._start_button)

        layout.addStretch()

        # --- Signal connections ---
        self._vm.dashboard_loaded.connect(self._on_dashboard_loaded)
        self._vm.start_enabled_changed.connect(self._start_button.setEnabled)

    def _on_dashboard_loaded(self, dashboard: TodayDashboard) -> None:
        has_content = dashboard.has_menu and len(dashboard.blocks) > 0

        self._no_source_widget.setVisible(not dashboard.has_sources and not has_content)
        self._no_menu_label.setVisible(dashboard.has_sources and not has_content)
        self._blocks_widget.setVisible(has_content)

        self._block_list.clear()
        if has_content:
            self._source_label.setText(f"ソース: {dashboard.source_title}" if dashboard.source_title else "")
            for block in dashboard.blocks:
                label = BLOCK_TYPE_LABELS.get(block.block_type, block.block_type)
                text = f"{label}  —  {block.item_count}項目  ({block.estimated_minutes:.0f}分)"
                self._block_list.addItem(QListWidgetItem(text))
            self._total_label.setText(f"合計: {dashboard.total_estimated_minutes:.0f}分")

        self._resume_label.setVisible(dashboard.has_resumable_session)
