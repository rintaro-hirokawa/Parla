"""View for Phase A speaking screen (SCREEN-E3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
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
    from parla.ui.screens.session.phase_a_view_model import PhaseAViewModel


class PhaseAView(QWidget):
    """Phase A — sequential sentence recording with hints."""

    def __init__(
        self,
        view_model: PhaseAViewModel,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Widgets ---
        self._sentence_list = QListWidget()
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
        self._recording.recording_finished.connect(self._on_recording_finished)
        self._hint_button.clicked.connect(self._on_hint_clicked)

    def _highlight_current(self) -> None:
        idx = self._vm.current_index
        self._sentence_list.setCurrentRow(idx)
        self._current_label.setText(self._vm.current_ja)
        self._hint_button.setVisible(self._vm.has_hint_for_current())
        self._hint_label.setText("")

    def _on_sentence_changed(self, index: int) -> None:
        self._highlight_current()

    def _on_recording_finished(self, audio: object) -> None:
        self._vm.submit_recording(audio)  # type: ignore[arg-type]

    def _on_hint_clicked(self) -> None:
        items = self._vm.get_hint_items()
        texts = [getattr(item, "pattern", str(item)) for item in items]
        self._hint_label.setText("\n".join(texts))
