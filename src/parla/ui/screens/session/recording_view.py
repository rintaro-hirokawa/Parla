"""View for recording screen (SCREEN-E3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.ui.widgets.recording_controls import RecordingControlsWidget
from parla.ui.widgets.timer_widget import TimerWidget

if TYPE_CHECKING:
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.recording_view_model import RecordingViewModel


class RecordingView(QWidget):
    """Sequential sentence recording with hints."""

    def __init__(
        self,
        view_model: RecordingViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Widgets ---
        self._sentence_list = QListWidget()
        self._sentence_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._sentence_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._current_label = QLabel("")
        self._timer = TimerWidget(parent=self)
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._hint_button = QPushButton("ヒント")
        self._hint_label = QLabel("")

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._sentence_list)
        layout.addWidget(self._current_label)
        layout.addWidget(self._timer)
        layout.addWidget(self._recording)
        layout.addWidget(self._hint_button)
        layout.addWidget(self._hint_label)

        # Populate sentence list
        for ja in self._vm.sentence_ja_list():
            self._sentence_list.addItem(QListWidgetItem(ja))
        self._highlight_current()

        # --- Connections ---
        self._vm.current_sentence_changed.connect(self._on_sentence_changed)
        self._vm.hint_revealed.connect(self._on_hint)
        self._recording.recording_finished.connect(self._on_recording_finished)
        self._hint_button.clicked.connect(self._vm.reveal_hint)

    def _highlight_current(self) -> None:
        idx = self._vm.current_index
        for i in range(self._sentence_list.count()):
            item = self._sentence_list.item(i)
            if item is not None:
                font = item.font()
                font.setBold(i == idx)
                item.setFont(font)
        self._current_label.setText(self._vm.current_ja)
        self._hint_label.setText("")

    def _on_sentence_changed(self, index: int) -> None:
        self._highlight_current()

    def _on_hint(self, _level: int, text: str) -> None:
        self._hint_label.setText(text)

    def _on_recording_finished(self, audio: object) -> None:
        self._vm.submit_recording(audio)  # type: ignore[arg-type]
