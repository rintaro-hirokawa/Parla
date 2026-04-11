"""View for feedback screen (SCREEN-E4).

Card-based feedback display with progress dots, status badges,
retry section, and inline learning items editing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parla.ui import theme
from parla.ui.widgets.progress_dots_widget import ProgressDotsWidget
from parla.ui.widgets.record_button_widget import RecordButtonWidget
from parla.ui.widgets.status_badge_widget import StatusBadgeWidget
from parla.ui.widgets.time_bar_widget import TimeBarWidget
from parla.ui.widgets.waveform_widget import WaveformWidget

if TYPE_CHECKING:
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.feedback_view_model import FeedbackViewModel


class FeedbackView(QWidget):
    """One-sentence-at-a-time feedback display with retry and learning items."""

    def __init__(
        self,
        view_model: FeedbackViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._recorder = recorder

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Time Bar (hidden by default, shown during retry) ---
        self._time_bar = TimeBarWidget()
        self._time_bar.setVisible(False)
        root.addWidget(self._time_bar)

        # --- Progress Dots ---
        dots_container = QWidget()
        dots_layout = QHBoxLayout(dots_container)
        dots_layout.setContentsMargins(28, 16, 28, 8)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_dots = ProgressDotsWidget()
        self._progress_dots.set_count(self._vm.sentence_count)
        dots_layout.addWidget(self._progress_dots)
        root.addWidget(dots_container)

        # --- Scrollable Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(32, 20, 32, 24)
        self._content_layout.setSpacing(16)

        # Feedback card
        self._feedback_card = QFrame()
        self._feedback_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        self._fb_layout = QVBoxLayout(self._feedback_card)
        self._fb_layout.setContentsMargins(28, 24, 28, 24)
        self._fb_layout.setSpacing(0)

        # FB header
        fb_header = QHBoxLayout()
        self._sentence_label = QLabel("Sentence 1")
        self._sentence_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; font-weight: 500;"
        )
        fb_header.addWidget(self._sentence_label)
        fb_header.addStretch()
        self._status_badge = StatusBadgeWidget()
        fb_header.addWidget(self._status_badge)
        self._fb_layout.addLayout(fb_header)

        # Japanese question
        self._ja_label = QLabel()
        self._ja_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ja_label.setWordWrap(True)
        self._ja_label.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {theme.rgb(theme.TEXT_PRIMARY)}; "
            f"padding: 12px 8px 20px; border-bottom: 1px solid {theme.rgb(theme.BG_SURFACE)};"
        )
        self._fb_layout.addWidget(self._ja_label)

        # English rows container
        self._english_rows = QWidget()
        eng_layout = QVBoxLayout(self._english_rows)
        eng_layout.setContentsMargins(0, 18, 0, 0)
        eng_layout.setSpacing(14)

        # You row
        you_row = QHBoxLayout()
        you_label = QLabel("YOU")
        you_label.setFixedWidth(48)
        you_label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {theme.rgb(theme.TEXT_SECONDARY)}; "
            f"letter-spacing: 0.06em; padding-top: 4px;"
        )
        you_row.addWidget(you_label, alignment=Qt.AlignmentFlag.AlignTop)
        self._user_text = QLabel()
        self._user_text.setWordWrap(True)
        self._user_text.setStyleSheet(
            f"background: {theme.rgb(theme.BG_SURFACE)}; "
            f"color: {theme.rgb(theme.TEXT_PRIMARY)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER_LIGHT)}; "
            f"border-radius: 10px; padding: 8px 16px; font-size: 16px;"
        )
        you_row.addWidget(self._user_text, stretch=1)
        eng_layout.addLayout(you_row)

        # Model row
        model_row = QHBoxLayout()
        model_label = QLabel("MODEL")
        model_label.setFixedWidth(48)
        model_label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {theme.rgb(theme.ACCENT)}; "
            f"letter-spacing: 0.06em; padding-top: 4px;"
        )
        model_row.addWidget(model_label, alignment=Qt.AlignmentFlag.AlignTop)
        self._model_text = QLabel()
        self._model_text.setWordWrap(True)
        self._model_text.setStyleSheet(
            f"background: {theme.rgb(theme.ACCENT_LIGHT)}; "
            f"color: {theme.rgb(theme.TEXT_PRIMARY)}; "
            f"border: 1px solid {theme.rgb(theme.ACCENT_BORDER)}; "
            f"border-radius: 10px; padding: 8px 16px; font-size: 16px; font-weight: 500;"
        )
        model_row.addWidget(self._model_text, stretch=1)
        eng_layout.addLayout(model_row)

        self._fb_layout.addWidget(self._english_rows)

        # Loading state
        self._loading_widget = QWidget()
        loading_layout = QVBoxLayout(self._loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setContentsMargins(0, 40, 0, 40)
        loading_label = QLabel("フィードバックを生成しています")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.setStyleSheet(f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 13px;")
        loading_layout.addWidget(loading_label)
        self._loading_widget.setVisible(False)
        self._fb_layout.addWidget(self._loading_widget)

        self._content_layout.addWidget(self._feedback_card)

        # Items card (only for new material mode)
        self._items_card = QFrame()
        self._items_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        items_card_layout = QVBoxLayout(self._items_card)
        items_card_layout.setContentsMargins(24, 20, 24, 20)

        items_header = QHBoxLayout()
        items_title = QLabel("Auto-stocked Items")
        items_title.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; font-weight: 500;"
        )
        items_header.addWidget(items_title)
        self._items_count_badge = QLabel("0")
        self._items_count_badge.setStyleSheet(
            f"background: {theme.rgb(theme.ACCENT_SUBTLE)}; "
            f"color: {theme.rgb(theme.ACCENT)}; "
            f"font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 10px;"
        )
        items_header.addWidget(self._items_count_badge)
        items_header.addStretch()
        self._items_edit_btn = QPushButton("\u270E")
        self._items_edit_btn.setFixedSize(26, 26)
        self._items_edit_btn.setStyleSheet(
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"background: {theme.rgb(theme.BG_CARD)}; border-radius: 6px; "
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 13px; padding: 0px;"
        )
        self._items_edit_btn.clicked.connect(self._vm.open_item_edit)
        items_header.addWidget(self._items_edit_btn)
        items_card_layout.addLayout(items_header)

        self._items_list = QVBoxLayout()
        items_card_layout.addLayout(self._items_list)

        if self._vm.show_items:
            self._content_layout.addWidget(self._items_card)
        else:
            self._items_card.setVisible(False)

        # Retry section
        self._retry_section = QFrame()
        self._retry_section.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        retry_layout = QVBoxLayout(self._retry_section)
        retry_layout.setContentsMargins(24, 20, 24, 20)

        retry_title = QLabel("Retry")
        retry_title.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; font-weight: 500;"
        )
        retry_layout.addWidget(retry_title)

        self._retry_start_btn = QPushButton("再チャレンジ")
        self._retry_start_btn.setStyleSheet(
            f"background: {theme.rgb(theme.BG_CARD)}; color: {theme.rgb(theme.ACCENT)}; "
            f"border: 1px solid {theme.rgb(theme.ACCENT_BORDER)}; "
            f"border-radius: 10px; padding: 11px; font-size: 14px; font-weight: 600;"
        )
        self._retry_start_btn.clicked.connect(self._on_retry_start)
        retry_layout.addWidget(self._retry_start_btn)

        # Retry recording area (hidden initially)
        self._retry_rec_area = QWidget()
        rec_layout = QHBoxLayout(self._retry_rec_area)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        rec_layout.setSpacing(16)
        self._retry_waveform = WaveformWidget()
        rec_layout.addWidget(self._retry_waveform, stretch=1)
        self._retry_record_btn = RecordButtonWidget(size=48)
        self._retry_record_btn.clicked.connect(self._on_retry_record_click)
        rec_layout.addWidget(self._retry_record_btn)
        self._retry_rec_area.setVisible(False)
        retry_layout.addWidget(self._retry_rec_area)

        self._retry_status = QLabel()
        self._retry_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._retry_status.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px;"
        )
        retry_layout.addWidget(self._retry_status)

        self._retry_section.setVisible(False)
        self._content_layout.addWidget(self._retry_section)

        self._content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # --- Bottom Actions ---
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {theme.rgb(theme.BG_PRIMARY)};")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(32, 0, 32, 24)
        self._next_button = QPushButton("次へ")
        self._next_button.setEnabled(False)
        self._next_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._next_button.clicked.connect(self._vm.advance_sentence)
        bottom_layout.addWidget(self._next_button)
        root.addWidget(bottom)

        # --- Connections ---
        self._vm.feedback_added.connect(self._on_feedback_added)
        self._vm.feedback_failed.connect(self._on_feedback_failed)
        self._vm.item_stocked.connect(self._on_item_stocked)
        self._vm.retry_result.connect(self._on_retry_result)
        self._vm.current_sentence_loading.connect(self._on_loading)
        self._vm.current_sentence_changed.connect(self._on_sentence_changed)

        self._item_widgets: list[QWidget] = []
        self._item_count = 0

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        self._vm.activate()
        self._vm.show_initial()

    def hideEvent(self, event: object) -> None:  # noqa: N802
        super().hideEvent(event)  # type: ignore[arg-type]
        self._vm.deactivate()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sentence_changed(self, current: int, total: int) -> None:
        self._progress_dots.set_current(current)
        self._sentence_label.setText(f"Sentence {current + 1}")
        self._reset_retry_ui()
        self._item_count = 0
        self._clear_items()

    def _on_feedback_added(
        self, idx: int, user_utterance: str, model_answer: str, is_acceptable: bool
    ) -> None:
        self._loading_widget.setVisible(False)
        self._english_rows.setVisible(True)
        self._user_text.setText(user_utterance)
        self._model_text.setText(model_answer)
        self._ja_label.setText(self._vm.current_ja)

        if is_acceptable:
            self._status_badge.set_status("correct", "正解")
            self._retry_section.setVisible(False)
        else:
            self._status_badge.set_status("needs-review", "要復習")
            self._retry_section.setVisible(True)

        self._next_button.setEnabled(self._vm.is_current_passed)
        if idx >= self._vm.sentence_count - 1:
            self._next_button.setText("完了")
        else:
            self._next_button.setText("次へ")

    def _on_feedback_failed(self, idx: int, error_message: str) -> None:
        self._loading_widget.setVisible(False)
        self._status_badge.set_status("needs-review", "エラー")
        self._ja_label.setText(error_message)

    def _on_item_stocked(
        self, idx: int, pattern: str, explanation: str, is_reappearance: bool
    ) -> None:
        self._item_count += 1
        self._items_count_badge.setText(str(self._item_count))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(10)

        pat_label = QLabel(pattern)
        pat_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {theme.rgb(theme.TEXT_PRIMARY)};"
        )
        row_layout.addWidget(pat_label)

        if is_reappearance:
            reapp = QLabel("再出")
            reapp.setStyleSheet(
                f"font-size: 10px; font-weight: 600; "
                f"color: {theme.rgb(theme.REVIEW_TEXT)}; "
                f"background: {theme.rgb(theme.REVIEW_BG)}; "
                f"border: 1px solid {theme.rgb(theme.REVIEW_BORDER)}; "
                f"padding: 1px 6px; border-radius: 8px;"
            )
            row_layout.addWidget(reapp)

        exp_label = QLabel(explanation)
        exp_label.setStyleSheet(
            f"font-size: 13px; color: {theme.rgb(theme.TEXT_SECONDARY)};"
        )
        row_layout.addWidget(exp_label)
        row_layout.addStretch()

        self._items_list.addWidget(row)
        self._item_widgets.append(row)

    def _on_loading(self, idx: int) -> None:
        self._loading_widget.setVisible(True)
        self._english_rows.setVisible(False)
        self._status_badge.set_status("loading", "生成中...")
        self._ja_label.setText(self._vm.current_ja)
        self._retry_section.setVisible(False)
        self._next_button.setEnabled(False)

    def _on_retry_result(self, idx: int, attempt: int, correct: bool) -> None:
        self._retry_rec_area.setVisible(False)
        self._retry_record_btn.set_recording(False)
        if correct:
            self._retry_status.setText("正解!")
            self._status_badge.set_status("correct", f"リトライ{attempt}: 正解")
            self._retry_section.setVisible(False)
            self._english_rows.setVisible(True)
        else:
            self._retry_status.setText(f"不正解 ({attempt}/3)")
            self._status_badge.set_status("needs-review", f"リトライ{attempt}: 不正解")
            self._retry_start_btn.setVisible(True)
        self._next_button.setEnabled(self._vm.is_current_passed)

    # ------------------------------------------------------------------
    # Retry flow
    # ------------------------------------------------------------------

    def _on_retry_start(self) -> None:
        self._retry_start_btn.setVisible(False)
        self._english_rows.setVisible(False)
        self._retry_status.setText("")
        # Start recording immediately
        self._retry_rec_area.setVisible(True)
        self._recorder.start()
        self._retry_record_btn.set_recording(True)
        self._retry_status.setText("録音中...")
        self._retry_status.setStyleSheet(
            f"color: {theme.rgb(theme.ERROR)}; font-size: 12px;"
        )

    def _on_retry_record_click(self) -> None:
        if self._retry_record_btn.recording:
            # Stop
            audio = self._recorder.stop()
            self._retry_record_btn.set_recording(False)
            self._retry_status.setText("判定中...")
            self._retry_status.setStyleSheet(
                f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px;"
            )
            if audio is not None:
                self._vm.retry_current(audio)

    def _reset_retry_ui(self) -> None:
        self._retry_section.setVisible(False)
        self._retry_start_btn.setVisible(True)
        self._retry_rec_area.setVisible(False)
        self._retry_status.setText("")

    def _clear_items(self) -> None:
        for w in self._item_widgets:
            w.setParent(None)
            w.deleteLater()
        self._item_widgets.clear()
        self._items_count_badge.setText("0")
