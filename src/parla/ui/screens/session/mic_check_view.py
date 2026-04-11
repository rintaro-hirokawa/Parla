"""View for the mic check screen (SCREEN-E1)."""

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from parla.ui import theme
from parla.ui.audio.recorder import AudioRecorder
from parla.ui.screens.session.mic_check_view_model import MicCheckViewModel
from parla.ui.widgets.level_meter_widget import LevelMeterWidget
from parla.ui.widgets.waveform_widget import WaveformWidget


class MicCheckView(QWidget):
    """Mic check screen — device selection, level monitoring, start gating."""

    def __init__(
        self,
        view_model: MicCheckViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # Title
        title = QLabel("マイクを選択してください")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 600; color: {theme.rgb(theme.TEXT_PRIMARY)};"
        )
        root.addWidget(title)

        # Device combo
        self._device_combo = QComboBox()
        root.addWidget(self._device_combo)

        # Audio monitoring card
        monitor_card = QFrame()
        monitor_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        card_layout = QVBoxLayout(monitor_card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        self._waveform = WaveformWidget(parent=self)
        card_layout.addWidget(self._waveform)

        self._level_meter = LevelMeterWidget(parent=self)
        card_layout.addWidget(self._level_meter)

        root.addWidget(monitor_card)

        # Gain slider
        gain_row = QHBoxLayout()
        gain_label = QLabel("入力ゲイン")
        gain_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_SECONDARY)}; font-size: 12px;"
        )
        gain_row.addWidget(gain_label)
        self._gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._gain_slider.setRange(-6, 10)
        self._gain_slider.setValue(0)
        self._gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._gain_slider.setTickInterval(3)
        gain_row.addWidget(self._gain_slider, stretch=1)
        self._gain_label = QLabel("0 dB")
        self._gain_label.setStyleSheet(
            f"color: {theme.rgb(theme.ACCENT)}; font-size: 12px; font-weight: 600;"
        )
        gain_row.addWidget(self._gain_label)
        root.addLayout(gain_row)

        # Warning
        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet(
            f"color: {theme.rgb(theme.WARNING)}; font-size: 12px;"
        )
        root.addWidget(self._warning_label)

        root.addStretch()

        # Start button
        self._start_button = QPushButton("開始")
        self._start_button.setEnabled(False)
        root.addWidget(self._start_button)

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

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._vm.start_test()

    def hideEvent(self, event: QHideEvent) -> None:
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
