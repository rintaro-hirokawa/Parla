"""Today's Learning tab view (SCREEN-C1)."""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parla.domain.session import BlockType
from parla.services.query_models import TodayDashboard
from parla.ui import theme
from parla.ui.screens.today.view_model import TodayViewModel

BLOCK_TYPE_LABELS = {BlockType.REVIEW: "復習", BlockType.NEW_MATERIAL: "新規素材", BlockType.CONSOLIDATION: "定着"}


class TodayView(QWidget):
    """Displays today's session menu and start button."""

    def __init__(self, view_model: TodayViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # --- No source CTA ---
        self._no_source_widget = QWidget()
        no_source_layout = QVBoxLayout(self._no_source_widget)
        no_source_layout.setContentsMargins(0, 0, 0, 0)
        no_source_layout.setSpacing(12)
        cta_label = QLabel("学習を始めるにはソースを登録してください")
        cta_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_SECONDARY)}; font-size: 14px;"
        )
        no_source_layout.addWidget(cta_label)
        self._add_source_button = QPushButton("ソースを追加")
        self._add_source_button.clicked.connect(self._vm.go_to_source_registration)
        no_source_layout.addWidget(self._add_source_button)
        layout.addWidget(self._no_source_widget)
        self._no_source_widget.hide()

        # --- No menu message ---
        self._no_menu_label = QLabel("メニューがまだ確定されていません")
        self._no_menu_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 14px;"
        )
        layout.addWidget(self._no_menu_label)

        # --- Blocks display (card) ---
        self._blocks_widget = QFrame()
        self._blocks_widget.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        blocks_layout = QVBoxLayout(self._blocks_widget)
        blocks_layout.setContentsMargins(24, 20, 24, 20)
        blocks_layout.setSpacing(8)

        self._source_label = QLabel()
        self._source_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_SECONDARY)}; font-size: 12px; font-weight: 500; border: none;"
        )
        blocks_layout.addWidget(self._source_label)

        self._block_rows_layout = QVBoxLayout()
        self._block_rows_layout.setSpacing(6)
        blocks_layout.addLayout(self._block_rows_layout)

        self._total_label = QLabel()
        self._total_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_PRIMARY)}; font-size: 13px; "
            f"font-weight: 600; padding-top: 8px; border: none;"
        )
        blocks_layout.addWidget(self._total_label)

        layout.addWidget(self._blocks_widget)
        self._blocks_widget.hide()

        # --- Resumable session ---
        self._resume_label = QLabel("中断中のセッションがあります")
        self._resume_label.setStyleSheet(
            f"color: {theme.rgb(theme.WARNING)}; font-size: 13px; font-weight: 500;"
        )
        self._resume_label.hide()
        layout.addWidget(self._resume_label)

        layout.addStretch()

        # --- Start button ---
        self._start_button = QPushButton("学習開始")
        self._start_button.setEnabled(False)
        self._start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._start_button.setStyleSheet(
            "padding: 14px; font-size: 15px; font-weight: 600; border-radius: 10px;"
        )
        self._start_button.clicked.connect(self._vm.start_learning)
        layout.addWidget(self._start_button)

        # --- Signal connections ---
        self._vm.dashboard_loaded.connect(self._on_dashboard_loaded)
        self._vm.start_enabled_changed.connect(self._start_button.setEnabled)

        self._block_widgets: list[QWidget] = []

    def _on_dashboard_loaded(self, dashboard: TodayDashboard) -> None:
        has_content = dashboard.has_menu and len(dashboard.blocks) > 0

        self._no_source_widget.setVisible(not dashboard.has_sources and not has_content)
        self._no_menu_label.setVisible(dashboard.has_sources and not has_content)
        self._blocks_widget.setVisible(has_content)

        # Clear block rows
        for w in self._block_widgets:
            w.setParent(None)
            w.deleteLater()
        self._block_widgets.clear()

        if has_content:
            self._source_label.setText(
                f"ソース: {dashboard.source_title}" if dashboard.source_title else ""
            )
            for block in dashboard.blocks:
                label = BLOCK_TYPE_LABELS.get(block.block_type, block.block_type)
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(8, 6, 8, 6)
                row_layout.setSpacing(8)
                type_lbl = QLabel(label)
                type_lbl.setStyleSheet(
                    f"font-size: 13px; font-weight: 500; color: {theme.rgb(theme.TEXT_PRIMARY)}; border: none;"
                )
                row_layout.addWidget(type_lbl)
                row_layout.addStretch()
                count_lbl = QLabel(f"{block.item_count}項目")
                count_lbl.setStyleSheet(
                    f"font-size: 12px; color: {theme.rgb(theme.TEXT_SECONDARY)}; border: none;"
                )
                row_layout.addWidget(count_lbl)
                time_lbl = QLabel(f"{block.estimated_minutes:.0f}分")
                time_lbl.setStyleSheet(
                    f"font-size: 12px; color: {theme.rgb(theme.TEXT_TERTIARY)}; border: none;"
                )
                row_layout.addWidget(time_lbl)
                self._block_rows_layout.addWidget(row)
                self._block_widgets.append(row)

            self._total_label.setText(f"合計: {dashboard.total_estimated_minutes:.0f}分")

        self._resume_label.setVisible(dashboard.has_resumable_session)
