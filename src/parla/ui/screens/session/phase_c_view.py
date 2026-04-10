"""View for Phase C practice workspace (SCREEN-E6)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from parla.ui.widgets.recording_controls import RecordingControlsWidget

if TYPE_CHECKING:
    from parla.ui.screens.session.phase_c_view_model import PhaseCViewModel


class PhaseCView(QWidget):
    """Phase C — listening, overlapping, and live delivery modes."""

    def __init__(
        self,
        view_model: PhaseCViewModel,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Widgets ---
        self._mode_combo = QComboBox()
        for mode in self._vm.available_modes:
            label = {"listening": "リスニング", "overlapping": "オーバーラッピング", "live_delivery": "本番発話"}
            self._mode_combo.addItem(label.get(mode, mode), mode)

        self._text_label = QLabel("")
        self._status_label = QLabel("")
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._play_button = QPushButton("モデル再生")
        self._speed_slider = QSlider()
        self._speed_slider.setMinimum(75)
        self._speed_slider.setMaximum(125)
        self._speed_slider.setValue(100)
        self._speed_label = QLabel("1.0x")
        self._complete_button = QPushButton("完了")

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._mode_combo)
        layout.addWidget(self._text_label)
        layout.addWidget(self._play_button)
        layout.addWidget(self._speed_slider)
        layout.addWidget(self._speed_label)
        layout.addWidget(self._recording)
        layout.addWidget(self._status_label)
        layout.addWidget(self._complete_button)

        # --- Connections ---
        self._mode_combo.currentIndexChanged.connect(self._on_mode_selected)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        self._complete_button.clicked.connect(self._vm.complete)

        self._vm.mode_changed.connect(self._on_mode_changed)
        self._vm.model_audio_ready.connect(self._on_audio_ready)
        self._vm.model_audio_failed.connect(self._on_audio_failed)
        self._vm.overlapping_result.connect(self._on_overlapping)
        self._vm.lag_detected.connect(self._on_lag)
        self._vm.live_delivery_result.connect(self._on_delivery)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._vm.deactivate()
        super().hideEvent(event)

    def _on_mode_selected(self, index: int) -> None:
        mode = self._mode_combo.itemData(index)
        if mode:
            self._vm.switch_mode(mode)

    def _on_mode_changed(self, mode: str) -> None:
        self._status_label.setText("")

    def _on_speed_changed(self, value: int) -> None:
        rate = value / 100.0
        self._speed_label.setText(f"{rate:.2f}x")
        self._vm.set_speed(rate)

    def _on_audio_ready(self) -> None:
        self._play_button.setEnabled(True)
        self._status_label.setText("モデル音声準備完了")

    def _on_audio_failed(self, message: str) -> None:
        self._status_label.setText(f"TTS エラー: {message}")

    def _on_overlapping(self, score: float) -> None:
        self._status_label.setText(f"発音スコア: {score:.1f}")

    def _on_lag(self, count: int) -> None:
        current = self._status_label.text()
        self._status_label.setText(f"{current} | 遅延箇所: {count}")

    def _on_delivery(self, passed: bool, wpm: float) -> None:
        result = "合格" if passed else "不合格"
        self._status_label.setText(f"{result} — {wpm:.1f} WPM")
