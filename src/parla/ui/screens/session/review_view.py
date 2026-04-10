"""View for the Block 1/3 review screen (SCREEN-E2)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.ui.widgets.recording_controls import RecordingControlsWidget
from parla.ui.widgets.timer_widget import TimerWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.review_view_model import ReviewViewModel

AUTO_ADVANCE_MS = 1500


class ReviewView(QWidget):
    """Review screen — shows variation question, records answer, shows result."""

    def __init__(
        self,
        view_model: ReviewViewModel,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Widgets ---
        self._prompt_label = QLabel("")
        self._hint_label = QLabel("")
        self._result_label = QLabel("")
        self._model_answer_label = QLabel("")
        self._timer = TimerWidget(parent=self)
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._hint_button = QPushButton("ヒント")
        self._retry_button = QPushButton("リトライ")
        self._retry_button.hide()

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._prompt_label)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._timer)
        layout.addWidget(self._recording)
        layout.addWidget(self._hint_button)
        layout.addWidget(self._result_label)
        layout.addWidget(self._model_answer_label)
        layout.addWidget(self._retry_button)

        # --- Auto-advance timer ---
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.setInterval(AUTO_ADVANCE_MS)
        self._advance_timer.timeout.connect(self._on_auto_advance)

        # --- Connections ---
        self._vm.question_ready.connect(self._on_question)
        self._vm.hint_revealed.connect(self._on_hint)
        self._vm.result_ready.connect(self._on_result)
        self._vm.retry_result.connect(self._on_retry_result)
        self._vm.error.connect(self._on_error)

        self._in_retry = False

        self._hint_button.clicked.connect(self._vm.reveal_hint)
        self._recording.recording_finished.connect(self._on_recording_finished)
        self._retry_button.clicked.connect(self._on_retry_clicked)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._vm.deactivate()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_question(self) -> None:
        self._in_retry = False
        self._prompt_label.setText(self._vm.current_ja)
        self._hint_label.setText("")
        self._result_label.setText("")
        self._model_answer_label.setText("")
        self._retry_button.hide()

    def _on_hint(self, level: int, text: str) -> None:
        self._hint_label.setText(f"ヒント{level}: {text}")

    def _on_result(self, correct: bool, model_answer: str) -> None:
        if correct:
            self._result_label.setText("正解!")
            self._advance_timer.start()
        else:
            self._result_label.setText("不正解")
            self._model_answer_label.setText(f"模範解答: {model_answer}")
            self._retry_button.show()

    def _on_retry_result(self, attempt: int, correct: bool) -> None:
        if correct:
            self._result_label.setText(f"リトライ{attempt}: 正解!")
            self._retry_button.hide()
            self._advance_timer.start()
        else:
            self._result_label.setText(f"リトライ{attempt}: 不正解")

    def _on_error(self, message: str) -> None:
        self._result_label.setText(f"エラー: {message}")

    def _on_recording_finished(self, audio: object) -> None:
        if self._in_retry:
            self._vm.submit_retry(audio)  # type: ignore[arg-type]
        else:
            self._vm.submit_recording(audio)  # type: ignore[arg-type]

    def _on_retry_clicked(self) -> None:
        self._in_retry = True

    def _on_auto_advance(self) -> None:
        self._vm.advance()
