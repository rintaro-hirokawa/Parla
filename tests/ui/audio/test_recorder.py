"""Tests for AudioRecorder."""

from __future__ import annotations

import io
import struct
import wave
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudio, QAudioDevice, QAudioFormat

from parla.domain.audio import AudioData
from parla.ui.audio.recorder import AudioRecorder


def _extract_pcm(wav_bytes: bytes) -> bytes:
    """Extract raw PCM data from WAV bytes."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.readframes(wf.getnframes())

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pcm_chunk(samples: list[int]) -> bytes:
    """Build raw PCM bytes (signed 16-bit LE) from sample values."""
    return struct.pack(f"<{len(samples)}h", *samples)


class FakeIODevice(QObject):
    """Simulates QIODevice returned by QAudioSource.start() in pull mode."""

    readyRead = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._data: bytes = b""

    def readAll(self) -> bytes:  # noqa: N802
        data = self._data
        self._data = b""
        return data

    def feed(self, data: bytes) -> None:
        """Inject PCM bytes and fire readyRead."""
        self._data = data
        self.readyRead.emit()


class FakeAudioSource(QObject):
    """Minimal stand-in for QAudioSource."""

    stateChanged = Signal(QAudio.State)

    def __init__(self, device: QAudioDevice, fmt: QAudioFormat) -> None:
        super().__init__()
        self._io = FakeIODevice()
        self._error = QAudio.Error.NoError
        self._state = QAudio.State.StoppedState

    def start(self) -> FakeIODevice:
        self._state = QAudio.State.ActiveState
        return self._io

    def stop(self) -> None:
        self._state = QAudio.State.StoppedState

    def error(self) -> QAudio.Error:
        return self._error

    def state(self) -> QAudio.State:
        return self._state

    # Test helpers
    def io(self) -> FakeIODevice:
        return self._io

    def inject_error(self, err: QAudio.Error) -> None:
        self._error = err
        self.stateChanged.emit(QAudio.State.StoppedState)


def _make_recorder(
    *,
    fake_source: FakeAudioSource | None = None,
) -> tuple[AudioRecorder, FakeAudioSource]:
    """Create an AudioRecorder with an injected fake source."""
    source = fake_source or FakeAudioSource(QAudioDevice(), QAudioFormat())

    def factory(device: QAudioDevice, fmt: QAudioFormat) -> FakeAudioSource:
        return source

    rec = AudioRecorder(audio_source_factory=factory)
    return rec, source


# ---------------------------------------------------------------------------
# TestDeviceEnumeration
# ---------------------------------------------------------------------------


class TestDeviceEnumeration:
    def test_available_devices_returns_list(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        devices = rec.available_devices()
        assert isinstance(devices, list)

    def test_select_device_stores_selection(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        device = QAudioDevice()
        rec.select_device(device)
        assert rec.selected_device() is device

    def test_default_device_when_none_selected(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        # selected_device returns None when no explicit selection
        assert rec.selected_device() is None


# ---------------------------------------------------------------------------
# TestRecordingLifecycle
# ---------------------------------------------------------------------------


class TestRecordingLifecycle:
    def test_start_emits_recording_started(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        with qtbot.waitSignal(rec.recording_started, timeout=1000):
            rec.start()

    def test_stop_emits_recording_stopped_with_audio_data(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        chunk = _make_pcm_chunk([1000, -1000, 500, -500])
        source.io().feed(chunk)

        with qtbot.waitSignal(rec.recording_stopped, timeout=1000) as blocker:
            result = rec.stop()

        assert isinstance(blocker.args[0], AudioData)
        assert result is not None
        assert isinstance(result, AudioData)

    def test_is_recording_true_while_active(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        assert rec.is_recording is False
        rec.start()
        assert rec.is_recording is True

    def test_is_recording_false_after_stop(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        rec.start()
        rec.stop()
        assert rec.is_recording is False

    def test_cancel_does_not_emit_stopped(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()
        source.io().feed(_make_pcm_chunk([100, 200]))

        with qtbot.assertNotEmitted(rec.recording_stopped):
            rec.cancel()

        assert rec.is_recording is False

    def test_start_while_recording_is_noop(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        rec.start()

        # Second start should not raise or change state
        rec.start()
        assert rec.is_recording is True

    def test_stop_without_start_returns_none(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        result = rec.stop()
        assert result is None


# ---------------------------------------------------------------------------
# TestAudioDataGeneration
# ---------------------------------------------------------------------------


class TestAudioDataGeneration:
    def test_audio_data_has_correct_format_fields(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()
        source.io().feed(_make_pcm_chunk([100] * 16))
        result = rec.stop()

        assert result is not None
        assert result.format == "wav"
        assert result.sample_rate == 16000
        assert result.channels == 1
        assert result.sample_width == 2

    def test_audio_data_is_valid_wav(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()
        source.io().feed(_make_pcm_chunk([100] * 16))
        result = rec.stop()

        assert result is not None
        assert result.data[:4] == b"RIFF"
        assert result.data[8:12] == b"WAVE"

    def test_audio_data_contains_all_buffered_pcm(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        chunk1 = _make_pcm_chunk([100, 200])
        chunk2 = _make_pcm_chunk([300, 400])
        source.io().feed(chunk1)
        source.io().feed(chunk2)

        result = rec.stop()
        assert result is not None
        pcm = _extract_pcm(result.data)
        assert pcm == chunk1 + chunk2

    def test_duration_computed_correctly(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        # 16000 samples = 1 second at 16kHz mono 16-bit
        samples = [0] * 16000
        source.io().feed(_make_pcm_chunk(samples))

        result = rec.stop()
        assert result is not None
        assert result.duration_seconds == pytest.approx(1.0)

    def test_empty_recording_has_zero_duration(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        rec.start()
        result = rec.stop()
        assert result is not None
        assert result.duration_seconds == 0.0
        pcm = _extract_pcm(result.data)
        assert pcm == b""


# ---------------------------------------------------------------------------
# TestRealtimeSignals
# ---------------------------------------------------------------------------


class TestRealtimeSignals:
    def test_level_changed_emitted_on_data(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        with qtbot.waitSignal(rec.level_changed, timeout=1000):
            source.io().feed(_make_pcm_chunk([10000, -10000, 5000]))

    def test_level_value_between_zero_and_one(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        levels: list[float] = []
        rec.level_changed.connect(levels.append)

        source.io().feed(_make_pcm_chunk([10000, -10000, 5000, -5000]))

        assert len(levels) == 1
        assert 0.0 <= levels[0] <= 1.0

    def test_silence_gives_zero_level(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        levels: list[float] = []
        rec.level_changed.connect(levels.append)

        source.io().feed(_make_pcm_chunk([0, 0, 0, 0]))

        assert len(levels) == 1
        assert levels[0] == 0.0

    def test_waveform_updated_emitted_with_float_list(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        waveforms: list[list[float]] = []
        rec.waveform_updated.connect(waveforms.append)

        source.io().feed(_make_pcm_chunk([16384, -16384] * 32))

        assert len(waveforms) == 1
        assert isinstance(waveforms[0], list)
        assert all(isinstance(v, float) for v in waveforms[0])
        assert all(-1.0 <= v <= 1.0 for v in waveforms[0])


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestDeviceSwitchWhileRecording
# ---------------------------------------------------------------------------


class TestDeviceSwitchWhileRecording:
    def test_select_device_restarts_source_while_recording(self, qtbot: QtBot) -> None:
        sources: list[FakeAudioSource] = []

        def factory(device: QAudioDevice, fmt: QAudioFormat) -> FakeAudioSource:
            src = FakeAudioSource(device, fmt)
            sources.append(src)
            return src

        rec = AudioRecorder(audio_source_factory=factory)
        rec.start()
        assert len(sources) == 1

        new_device = QAudioDevice()
        rec.select_device(new_device)

        # A new source should have been created
        assert len(sources) == 2
        assert rec.is_recording is True

        # New source should be active — feed data and verify level emitted
        with qtbot.waitSignal(rec.level_changed, timeout=1000):
            sources[1].io().feed(_make_pcm_chunk([10000, -10000]))

    def test_select_device_without_recording_does_not_restart(
        self, qtbot: QtBot
    ) -> None:
        sources: list[FakeAudioSource] = []

        def factory(device: QAudioDevice, fmt: QAudioFormat) -> FakeAudioSource:
            src = FakeAudioSource(device, fmt)
            sources.append(src)
            return src

        rec = AudioRecorder(audio_source_factory=factory)
        rec.select_device(QAudioDevice())

        assert len(sources) == 0


# ---------------------------------------------------------------------------
# TestGainControl
# ---------------------------------------------------------------------------


class TestGainControl:
    def test_default_gain_is_one(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        assert rec.gain == 1.0

    def test_set_gain_clamps_range(self, qtbot: QtBot) -> None:
        rec, _ = _make_recorder()
        rec.set_gain(0.1)
        assert rec.gain == 0.5
        rec.set_gain(5.0)
        assert rec.gain == 3.0
        rec.set_gain(2.0)
        assert rec.gain == 2.0

    def test_gain_amplifies_recorded_data(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.set_gain(2.0)
        rec.start()

        source.io().feed(_make_pcm_chunk([1000, -1000]))
        result = rec.stop()

        assert result is not None
        pcm = _extract_pcm(result.data)
        gained_samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert gained_samples == (2000, -2000)

    def test_gain_clamps_to_int16_range(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.set_gain(3.0)
        rec.start()

        source.io().feed(_make_pcm_chunk([20000, -20000]))
        result = rec.stop()

        assert result is not None
        pcm = _extract_pcm(result.data)
        gained_samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert gained_samples == (32767, -32768)

    def test_gain_one_passes_through_unchanged(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.set_gain(1.0)
        rec.start()

        original = _make_pcm_chunk([5000, -5000])
        source.io().feed(original)
        result = rec.stop()

        assert result is not None
        pcm = _extract_pcm(result.data)
        assert pcm == original

    def test_gain_affects_level_signal(self, qtbot: QtBot) -> None:
        rec_normal, source_normal = _make_recorder()
        rec_gained, source_gained = _make_recorder()
        rec_gained.set_gain(2.0)

        levels_normal: list[float] = []
        levels_gained: list[float] = []
        rec_normal.level_changed.connect(levels_normal.append)
        rec_gained.level_changed.connect(levels_gained.append)

        chunk = _make_pcm_chunk([5000, -5000, 3000, -3000])

        rec_normal.start()
        source_normal.io().feed(chunk)
        rec_normal.stop()

        rec_gained.start()
        source_gained.io().feed(chunk)
        rec_gained.stop()

        assert len(levels_normal) == 1
        assert len(levels_gained) == 1
        assert levels_gained[0] > levels_normal[0]


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_error_occurred_on_source_error(self, qtbot: QtBot) -> None:
        rec, source = _make_recorder()
        rec.start()

        with qtbot.waitSignal(rec.error_occurred, timeout=1000):
            source.inject_error(QAudio.Error.IOError)
