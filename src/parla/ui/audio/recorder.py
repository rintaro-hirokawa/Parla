"""Audio recording manager using QAudioSource."""

from __future__ import annotations

import array
import io
import math
import wave
from collections.abc import Callable

from PySide6.QtCore import QIODevice, QObject, Signal
from PySide6.QtMultimedia import QAudio, QAudioDevice, QAudioFormat, QAudioSource, QMediaDevices

from parla.domain.audio import AudioData

# Recording constants
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH
WAVEFORM_POINTS = 64  # downsampled waveform size per emission
MAX_INT16 = 32768.0


AudioSourceFactory = Callable[[QAudioDevice, QAudioFormat], QAudioSource]


def _default_audio_source_factory(device: QAudioDevice, fmt: QAudioFormat) -> QAudioSource:
    return QAudioSource(device, fmt)


def _build_format() -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleRate(SAMPLE_RATE)
    fmt.setChannelCount(CHANNELS)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    return fmt


class AudioRecorder(QObject):
    """Records PCM 16-bit mono 16kHz audio from a microphone.

    Emits real-time RMS level and waveform signals during recording.
    Produces an ``AudioData`` value object on completion.
    """

    recording_started = Signal()
    recording_stopped = Signal(AudioData)
    level_changed = Signal(float)
    waveform_updated = Signal(list)
    chunk_ready = Signal(bytes)  # raw PCM after gain
    error_occurred = Signal(str)

    def __init__(
        self,
        *,
        audio_source_factory: AudioSourceFactory | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = audio_source_factory or _default_audio_source_factory
        self._device: QAudioDevice | None = None
        self._source: QAudioSource | None = None
        self._io: QIODevice | None = None
        self._buffer = bytearray()
        self._recording = False
        self._gain: float = 1.0

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def available_devices(self) -> list[QAudioDevice]:
        return QMediaDevices.audioInputs()

    def select_device(self, device: QAudioDevice) -> None:
        self._device = device
        if self._recording:
            self._restart_source()

    def selected_device(self) -> QAudioDevice | None:
        return self._device

    # ------------------------------------------------------------------
    # Gain control
    # ------------------------------------------------------------------

    @property
    def gain(self) -> float:
        return self._gain

    def set_gain(self, factor: float) -> None:
        self._gain = max(0.5, min(factor, 3.0))

    # ------------------------------------------------------------------
    # Recording lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._recording:
            return

        device = self._device or QMediaDevices.defaultAudioInput()
        fmt = _build_format()
        self._source = self._factory(device, fmt)
        self._source.stateChanged.connect(self._on_state_changed)
        self._buffer = bytearray()
        self._io = self._source.start()
        self._io.readyRead.connect(self._on_data_ready)
        self._recording = True
        self.recording_started.emit()

    def stop(self) -> AudioData | None:
        if not self._recording:
            return None

        self._recording = False
        if self._source is not None:
            self._source.stop()

        audio = self._build_audio_data()
        self.recording_stopped.emit(audio)
        self._cleanup()
        return audio

    def cancel(self) -> None:
        if not self._recording:
            return
        self._recording = False
        if self._source is not None:
            self._source.stop()
        self._cleanup()

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_data_ready(self) -> None:
        if self._io is None:
            return
        data = self._io.readAll()
        raw = bytes(data) if isinstance(data, (bytes, bytearray)) else bytes(data.data())
        if not raw:
            return

        samples = array.array("h", raw)
        if self._gain != 1.0:
            samples = self._apply_gain(samples)
            raw = samples.tobytes()

        self._buffer.extend(raw)
        self.chunk_ready.emit(raw)
        self._emit_level(samples)
        self._emit_waveform(samples)

    def _apply_gain(self, samples: array.array[int]) -> array.array[int]:
        return array.array(
            "h",
            [max(-32768, min(32767, int(s * self._gain))) for s in samples],
        )

    def _restart_source(self) -> None:
        """Stop the current audio source and recreate with the selected device."""
        if self._source is not None:
            self._source.stop()
            self._source = None
            self._io = None
        device = self._device or QMediaDevices.defaultAudioInput()
        fmt = _build_format()
        self._source = self._factory(device, fmt)
        self._source.stateChanged.connect(self._on_state_changed)
        self._io = self._source.start()
        self._io.readyRead.connect(self._on_data_ready)

    def _emit_level(self, samples: array.array[int]) -> None:
        if not samples:
            self.level_changed.emit(0.0)
            return
        sum_sq = sum(s * s for s in samples)
        rms = math.sqrt(sum_sq / len(samples)) / MAX_INT16
        self.level_changed.emit(min(rms, 1.0))

    def _emit_waveform(self, samples: array.array[int]) -> None:
        n = len(samples)
        if n == 0:
            return
        if n <= WAVEFORM_POINTS:
            waveform = [s / MAX_INT16 for s in samples]
        else:
            step = n / WAVEFORM_POINTS
            waveform = [samples[int(i * step)] / MAX_INT16 for i in range(WAVEFORM_POINTS)]
        self.waveform_updated.emit(waveform)

    def _on_state_changed(self, state: QAudio.State) -> None:
        if self._source is None:
            return
        err = self._source.error()
        if err != QAudio.Error.NoError:  # type: ignore[comparison-overlap]  # PySide6 stub issue
            self.error_occurred.emit(f"Audio source error: {err.name}")

    def _build_audio_data(self) -> AudioData:
        pcm = bytes(self._buffer)
        duration = len(pcm) / BYTES_PER_SECOND if pcm else 0.0
        wav_data = self._pcm_to_wav(pcm)
        return AudioData(
            data=wav_data,
            format="wav",
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS,
            sample_width=SAMPLE_WIDTH,
            duration_seconds=duration,
        )

    @staticmethod
    def _pcm_to_wav(pcm: bytes) -> bytes:
        """Wrap raw PCM bytes in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return buf.getvalue()

    def _cleanup(self) -> None:
        self._source = None
        self._io = None
        self._buffer = bytearray()
