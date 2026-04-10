"""Tests for AudioPlayer."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer

from parla.domain.audio import AudioData
from parla.ui.audio.player import AudioPlayer, _pcm_to_wav_bytes

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot


# ---------------------------------------------------------------------------
# Fake QMediaPlayer / QAudioOutput
# ---------------------------------------------------------------------------


class FakeMediaPlayer(QObject):
    """Stand-in for QMediaPlayer with real signals for pytest-qt."""

    positionChanged = Signal(int)  # ms
    durationChanged = Signal(int)  # ms
    playbackStateChanged = Signal(QMediaPlayer.PlaybackState)
    errorOccurred = Signal(QMediaPlayer.Error, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rate: float = 1.0
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self._source_url: QUrl | None = None
        self._source_device: object | None = None

    def setSource(self, url: QUrl) -> None:  # noqa: N802
        self._source_url = url

    def setSourceDevice(self, device: object, url: QUrl | None = None) -> None:  # noqa: N802
        self._source_device = device

    def play(self) -> None:
        self._state = QMediaPlayer.PlaybackState.PlayingState
        self.playbackStateChanged.emit(self._state)

    def stop(self) -> None:
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self.playbackStateChanged.emit(self._state)

    def pause(self) -> None:
        self._state = QMediaPlayer.PlaybackState.PausedState
        self.playbackStateChanged.emit(self._state)

    def setPlaybackRate(self, rate: float) -> None:  # noqa: N802
        self._rate = rate

    def playbackRate(self) -> float:  # noqa: N802
        return self._rate

    def position(self) -> int:
        return 0

    def duration(self) -> int:
        return 0

    def setAudioOutput(self, output: object) -> None:  # noqa: N802
        pass

    def playbackState(self) -> QMediaPlayer.PlaybackState:  # noqa: N802
        return self._state


class FakeAudioOutput(QObject):
    """Stand-in for QAudioOutput."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(fake: FakeMediaPlayer | None = None) -> tuple[AudioPlayer, FakeMediaPlayer]:
    """Create an AudioPlayer with an injected fake player."""
    fm = fake or FakeMediaPlayer()
    player = AudioPlayer(player=fm, audio_output=FakeAudioOutput())
    return player, fm


def _make_wav_audio_data(n_samples: int = 160) -> AudioData:
    """Create a small WAV AudioData with raw PCM."""
    pcm = struct.pack(f"<{n_samples}h", *([1000] * n_samples))
    return AudioData(
        data=pcm,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=n_samples / 16000,
    )


def _make_mp3_audio_data() -> AudioData:
    """Create a fake MP3 AudioData (bytes aren't real MP3 but sufficient for API test)."""
    return AudioData(
        data=b"\xff\xfb\x90\x00" + b"\x00" * 100,
        format="mp3",
        sample_rate=44100,
        channels=1,
        sample_width=2,
        duration_seconds=1.0,
    )


# ---------------------------------------------------------------------------
# TestPlaybackLifecycle
# ---------------------------------------------------------------------------


class TestPlaybackLifecycle:
    def test_play_audio_data_emits_playback_started(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        with qtbot.waitSignal(player.playback_started, timeout=1000):
            player.play_audio_data(_make_wav_audio_data())

    def test_play_file_emits_playback_started(self, qtbot: QtBot, tmp_path: Path) -> None:
        f = tmp_path / "test.wav"
        f.write_bytes(b"\x00" * 100)
        player, fm = _make_player()
        with qtbot.waitSignal(player.playback_started, timeout=1000):
            player.play_file(f)

    def test_stop_emits_playback_finished(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.play_audio_data(_make_wav_audio_data())

        with qtbot.waitSignal(player.playback_finished, timeout=1000):
            player.stop()

    def test_is_playing_reflects_state(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        assert player.is_playing is False

        player.play_audio_data(_make_wav_audio_data())
        assert player.is_playing is True

        player.stop()
        assert player.is_playing is False

    def test_pause_and_resume(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.play_audio_data(_make_wav_audio_data())
        assert player.is_playing is True

        player.pause()
        assert player.is_playing is False

        player.resume()
        assert player.is_playing is True


# ---------------------------------------------------------------------------
# TestSpeedControl
# ---------------------------------------------------------------------------


class TestSpeedControl:
    def test_default_speed_is_1_0(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        assert player.speed == pytest.approx(1.0)

    def test_set_speed_updates_playback_rate(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.set_speed(1.5)
        assert player.speed == pytest.approx(1.5)
        assert fm.playbackRate() == pytest.approx(1.5)

    def test_speed_clamped_to_minimum(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.set_speed(0.1)
        assert player.speed == pytest.approx(0.5)

    def test_speed_clamped_to_maximum(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.set_speed(5.0)
        assert player.speed == pytest.approx(2.0)

    def test_speed_change_during_playback(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        player.play_audio_data(_make_wav_audio_data())
        player.set_speed(0.75)
        assert fm.playbackRate() == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# TestPositionTracking
# ---------------------------------------------------------------------------


class TestPositionTracking:
    def test_position_changed_emits_seconds(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        positions: list[float] = []
        player.playback_position_changed.connect(positions.append)

        fm.positionChanged.emit(2500)  # 2500 ms

        assert len(positions) == 1
        assert positions[0] == pytest.approx(2.5)

    def test_duration_changed_emitted(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        durations: list[float] = []
        player.duration_changed.connect(durations.append)

        fm.durationChanged.emit(10000)  # 10000 ms

        assert len(durations) == 1
        assert durations[0] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# TestFormatHandling
# ---------------------------------------------------------------------------


class TestFormatHandling:
    def test_play_wav_audio_data_uses_buffer(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        audio = _make_wav_audio_data()
        player.play_audio_data(audio)
        # source device should have been set (not source URL)
        assert fm._source_device is not None

    def test_play_mp3_audio_data_uses_buffer(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        audio = _make_mp3_audio_data()
        player.play_audio_data(audio)
        assert fm._source_device is not None

    def test_pcm_to_wav_bytes_has_correct_header(self) -> None:
        pcm = struct.pack("<4h", 100, 200, 300, 400)
        audio = AudioData(
            data=pcm,
            format="wav",
            sample_rate=16000,
            channels=1,
            sample_width=2,
            duration_seconds=4 / 16000,
        )
        wav = _pcm_to_wav_bytes(audio)

        # RIFF header
        assert wav[:4] == b"RIFF"
        # WAVE marker
        assert wav[8:12] == b"WAVE"
        # fmt chunk
        assert wav[12:16] == b"fmt "
        # data chunk
        assert wav[36:40] == b"data"

        # Data size field (bytes 40-43)
        data_size = struct.unpack_from("<I", wav, 40)[0]
        assert data_size == len(pcm)

        # Sample rate (bytes 24-27)
        sr = struct.unpack_from("<I", wav, 24)[0]
        assert sr == 16000

        # Channels (bytes 22-23)
        ch = struct.unpack_from("<H", wav, 22)[0]
        assert ch == 1

        # Bits per sample (bytes 34-35)
        bps = struct.unpack_from("<H", wav, 34)[0]
        assert bps == 16

        # PCM data follows header
        assert wav[44:] == pcm

    def test_play_file_sets_source_url(self, qtbot: QtBot, tmp_path: Path) -> None:
        f = tmp_path / "test.wav"
        f.write_bytes(b"\x00" * 100)
        player, fm = _make_player()
        player.play_file(f)
        assert fm._source_url is not None


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_error_signal_emitted_on_player_error(self, qtbot: QtBot) -> None:
        player, fm = _make_player()
        errors: list[str] = []
        player.playback_error.connect(errors.append)

        fm.errorOccurred.emit(QMediaPlayer.Error.ResourceError, "file not found")

        assert len(errors) == 1
        assert "file not found" in errors[0]
