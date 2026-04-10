"""Composite recording controls: waveform + level meter + record button."""

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from parla.ui.widgets.level_meter_widget import LevelMeterWidget
from parla.ui.widgets.waveform_widget import WaveformWidget


class RecordingControlsWidget(QWidget):
    """Composite widget combining waveform, level meter, and record button.

    Used in E1, E2, E3, E6 for audio recording with visual feedback.
    The recorder must be a QObject with signals: samples_ready, level_updated,
    recording_done, and methods: start_recording(), stop_recording(), is_recording().
    """

    recording_finished = Signal(object)  # AudioData

    def __init__(
        self,
        recorder: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._recorder = recorder
        self._is_recording = False

        self._waveform = WaveformWidget(parent=self)
        self._level_meter = LevelMeterWidget(parent=self)
        self._record_button = QPushButton("Record", self)

        layout = QHBoxLayout(self)
        layout.addWidget(self._waveform, stretch=1)
        layout.addWidget(self._level_meter)
        layout.addWidget(self._record_button)

        self._record_button.clicked.connect(self._toggle_recording)
        self._recorder.samples_ready.connect(self._on_samples)
        self._recorder.level_updated.connect(self._level_meter.set_level)
        self._recorder.recording_done.connect(self._on_recording_done)

    @property
    def waveform(self) -> WaveformWidget:
        return self._waveform

    @property
    def level_meter(self) -> LevelMeterWidget:
        return self._level_meter

    def _toggle_recording(self) -> None:
        if self._is_recording:
            self._recorder.stop_recording()
            self._is_recording = False
            self._record_button.setText("Record")
        else:
            self._recorder.start_recording()
            self._is_recording = True
            self._record_button.setText("Stop")

    def _on_samples(self, samples: list[float]) -> None:
        self._waveform.update_samples(samples)

    def _on_recording_done(self, audio_data: object) -> None:
        self._is_recording = False
        self._record_button.setText("Record")
        self.recording_finished.emit(audio_data)
