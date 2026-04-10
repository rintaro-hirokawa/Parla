"""View for Phase B feedback screen (SCREEN-E4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from parla.ui.widgets.recording_controls import RecordingControlsWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.phase_b_view_model import PhaseBViewModel


class FeedbackCard(QWidget):
    """Single sentence feedback display."""

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
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
        self._status_label.setText(f"エラー: {message}")

    def set_retry_status(self, attempt: int, correct: bool) -> None:
        status = "正解" if correct else "不正解"
        self._status_label.setText(f"リトライ{attempt}: {status}")


class PhaseBView(QWidget):
    """Phase B — progressive feedback display with retry and navigation."""

    def __init__(
        self,
        view_model: PhaseBViewModel,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Feedback cards area ---
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards: dict[int, FeedbackCard] = {}

        scroll = QScrollArea()
        scroll.setWidget(self._cards_container)
        scroll.setWidgetResizable(True)

        # --- Items and controls ---
        self._stocked_items: list[str] = []
        self._items_label = QLabel("")
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._edit_button = QPushButton("項目を編集")
        self._next_button = QPushButton("次へ")

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(self._items_label)
        layout.addWidget(self._recording)
        layout.addWidget(self._edit_button)
        layout.addWidget(self._next_button)

        # --- Connections ---
        self._vm.feedback_added.connect(self._on_feedback_added)
        self._vm.feedback_failed.connect(self._on_feedback_failed)
        self._vm.item_stocked.connect(self._on_item_stocked)
        self._vm.retry_result.connect(self._on_retry_result)
        self._edit_button.clicked.connect(self._vm.open_item_edit)
        self._next_button.clicked.connect(self._vm.proceed)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._vm.deactivate()
        super().hideEvent(event)

    def _get_or_create_card(self, index: int) -> FeedbackCard:
        if index not in self._cards:
            card = FeedbackCard(index, parent=self._cards_container)
            self._cards_layout.addWidget(card)
            self._cards[index] = card
        return self._cards[index]

    def _on_feedback_added(self, index: int, user_utterance: str, model_answer: str, is_acceptable: bool) -> None:
        card = self._get_or_create_card(index)
        card.set_feedback(user_utterance, model_answer, is_acceptable)

    def _on_feedback_failed(self, index: int, message: str) -> None:
        card = self._get_or_create_card(index)
        card.set_error(message)

    def _on_item_stocked(self, pattern: str, is_reappearance: bool) -> None:
        marker = " (再出)" if is_reappearance else ""
        self._stocked_items.append(f"• {pattern}{marker}")
        self._items_label.setText("\n".join(self._stocked_items))

    def _on_retry_result(self, index: int, attempt: int, correct: bool) -> None:
        card = self._cards.get(index)
        if card is None:
            return
        card.set_retry_status(attempt, correct)
