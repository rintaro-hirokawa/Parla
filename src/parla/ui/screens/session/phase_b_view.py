"""View for Phase B feedback screen (SCREEN-E4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.ui import theme
from parla.ui.widgets.recording_controls import RecordingControlsWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QHideEvent, QShowEvent

    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.phase_b_view_model import PhaseBViewModel


class FeedbackCard(QWidget):
    """Single sentence feedback display."""

    _ERROR_STYLE = f"color: {theme.rgb(theme.ERROR)}; background: transparent;"

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self._utterance_label = QLabel("")
        self._model_label = QLabel("")
        self._status_label = QLabel("")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"センテンス {index + 1}"))
        layout.addWidget(self._utterance_label)
        layout.addWidget(self._model_label)
        layout.addWidget(self._status_label)

    def set_feedback(self, user_utterance: str, model_answer: str, is_acceptable: bool) -> None:
        self._utterance_label.setText(f"発話: {user_utterance}")
        self._model_label.setText(f"模範: {model_answer}")
        self._status_label.setText("正解" if is_acceptable else "要復習")

    def set_error(self, message: str) -> None:
        self._status_label.setStyleSheet(self._ERROR_STYLE)
        self._status_label.setText(f"エラー: {message}")

    def set_retry_status(self, attempt: int, correct: bool) -> None:
        status = "正解" if correct else "不正解"
        self._status_label.setText(f"リトライ{attempt}: {status}")


class PhaseBView(QWidget):
    """Phase B — one-sentence-at-a-time feedback display with retry and navigation."""

    def __init__(
        self,
        view_model: PhaseBViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Progress indicator ---
        self._progress_label = QLabel("")

        # --- Single feedback card area ---
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._current_card: FeedbackCard | None = None

        # --- Loading indicator ---
        self._loading_label = QLabel("フィードバックを生成中...")
        self._loading_label.setVisible(False)

        # --- Items and controls ---
        self._stocked_items: list[str] = []
        self._items_label = QLabel("")
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._edit_button = QPushButton("項目を編集")
        self._next_button = QPushButton("次へ")

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._progress_label)
        layout.addWidget(self._card_container, stretch=1)
        layout.addWidget(self._loading_label)
        layout.addWidget(self._items_label)
        layout.addWidget(self._recording)
        layout.addWidget(self._edit_button)
        layout.addWidget(self._next_button)

        # --- Connections ---
        self._vm.feedback_added.connect(self._on_feedback_added)
        self._vm.feedback_failed.connect(self._on_feedback_failed)
        self._vm.current_sentence_loading.connect(self._on_loading)
        self._vm.current_sentence_changed.connect(self._on_sentence_changed)
        self._vm.item_stocked.connect(self._on_item_stocked)
        self._vm.retry_result.connect(self._on_retry_result)
        self._recording.recording_finished.connect(self._on_retry_recording)
        self._edit_button.clicked.connect(self._vm.open_item_edit)
        self._next_button.clicked.connect(self._vm.advance_sentence)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._vm.activate()
        self._vm.show_initial()

    def hideEvent(self, event: QHideEvent) -> None:
        self._vm.deactivate()
        super().hideEvent(event)

    def _update_progress(self, current: int, total: int) -> None:
        self._progress_label.setText(f"センテンス {current + 1} / {total}")
        if current >= total - 1:
            self._next_button.setText("完了")
        else:
            self._next_button.setText("次へ")

    def _clear_card(self) -> None:
        if self._current_card is not None:
            self._card_layout.removeWidget(self._current_card)
            self._current_card.deleteLater()
            self._current_card = None

    def _on_feedback_added(self, index: int, user_utterance: str, model_answer: str, is_acceptable: bool) -> None:
        self._loading_label.setVisible(False)
        self._clear_card()
        self._stocked_items.clear()
        self._items_label.setText("")
        card = FeedbackCard(index, parent=self._card_container)
        card.set_feedback(user_utterance, model_answer, is_acceptable)
        self._card_layout.addWidget(card)
        self._current_card = card
        self._next_button.setEnabled(is_acceptable)

    def _on_feedback_failed(self, index: int, message: str) -> None:
        self._loading_label.setVisible(False)
        self._clear_card()
        card = FeedbackCard(index, parent=self._card_container)
        card.set_error(message)
        self._card_layout.addWidget(card)
        self._current_card = card

    def _on_loading(self, index: int) -> None:
        self._clear_card()
        self._loading_label.setVisible(True)
        self._next_button.setEnabled(False)

    def _on_sentence_changed(self, current: int, total: int) -> None:
        self._update_progress(current, total)

    def _on_item_stocked(self, index: int, pattern: str, explanation: str, is_reappearance: bool) -> None:
        marker = " (再出)" if is_reappearance else ""
        self._stocked_items.append(f"• {pattern}{marker} — {explanation}")
        self._items_label.setText("\n".join(self._stocked_items))

    def _on_retry_recording(self, audio_data: object) -> None:
        from parla.domain.audio import AudioData

        if isinstance(audio_data, AudioData):
            self._vm.retry_current(audio_data)

    def _on_retry_result(self, index: int, attempt: int, correct: bool) -> None:
        if self._current_card is not None and self._current_card.index == index:
            self._current_card.set_retry_status(attempt, correct)
        if correct:
            self._next_button.setEnabled(True)
