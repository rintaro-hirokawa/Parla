"""View for the mic check screen (SCREEN-E1)."""

import math
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from parla.ui.screens.session.mic_check_view_model import MicCheckViewModel
from parla.ui.widgets.level_meter_widget import LevelMeterWidget
from parla.ui.widgets.waveform_widget import WaveformWidget


class MicCheckView(QWidget):
    """Mic check screen — device selection, level monitoring, start gating."""

    def __init__(
        self,
        view_model: MicCheckViewModel,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        # --- Widgets ---
        self._device_combo = QComboBox()
        self._waveform = WaveformWidget(parent=self)
        self._level_meter = LevelMeterWidget(parent=self)
        self._gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._gain_slider.setRange(-6, 10)  # dB
        self._gain_slider.setValue(0)
        self._gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._gain_slider.setTickInterval(3)
        self._gain_label = QLabel("0 dB")
        self._warning_label = QLabel("")
        self._start_button = QPushButton("開始")
        self._start_button.setEnabled(False)

        # --- Layout ---
        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("入力ゲイン"))
        gain_row.addWidget(self._gain_slider, stretch=1)
        gain_row.addWidget(self._gain_label)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("マイクを選択してください"))
        layout.addWidget(self._device_combo)
        layout.addWidget(self._waveform)
        layout.addWidget(self._level_meter)
        layout.addLayout(gain_row)
        layout.addWidget(self._warning_label)
        layout.addWidget(self._start_button)

        # --- Populate devices ---
        for name in self._vm.device_names():
            self._device_combo.addItem(name)

        # --- Connect recorder signals to display widgets ---
        recorder.waveform_updated.connect(self._waveform.update_samples)
        recorder.level_changed.connect(self._level_meter.set_level)

        # --- Connect ViewModel signals ---
        self._vm.start_enabled_changed.connect(self._on_start_enabled)
        self._vm.level_warning.connect(self._on_warning)
        self._vm.error.connect(self._on_error)

        # --- Connect user actions ---
        self._device_combo.currentIndexChanged.connect(self._vm.select_device)
        self._gain_slider.valueChanged.connect(self._on_gain_changed)
        self._start_button.clicked.connect(self._vm.confirm_start)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._vm.start_test()

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._vm.stop_test()
        super().hideEvent(event)

    def _on_start_enabled(self, enabled: bool) -> None:
        self._start_button.setEnabled(enabled)
        if enabled:
            self._warning_label.setText("")

    def _on_warning(self) -> None:
        self._warning_label.setText("入力レベルが低すぎます。マイクに近づいて話してください。")

    def _on_gain_changed(self, db: int) -> None:
        factor = math.pow(10, db / 20)
        self._vm.set_gain(factor)
        self._gain_label.setText(f"{db:+d} dB")

    def _on_error(self, message: str) -> None:
        self._warning_label.setText(f"エラー: {message}")
