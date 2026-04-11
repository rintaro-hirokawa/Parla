"""Audio playback manager using QMediaPlayer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

if TYPE_CHECKING:
    from pathlib import Path

    from parla.domain.audio import AudioData

# Speed limits
MIN_SPEED = 0.5
MAX_SPEED = 2.0


class AudioPlayer(QObject):
    """Plays audio (MP3 or WAV) with speed control and position tracking.

    Position is reported in seconds for use in overlapping word highlighting.
    """

    playback_started = Signal()
    playback_finished = Signal()
    playback_position_changed = Signal(float)
    playback_error = Signal(str)
    duration_changed = Signal(float)

    def __init__(
        self,
        *,
        player: Any | None = None,
        audio_output: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._player: Any = player or QMediaPlayer(self)
        self._audio_output: Any = audio_output or QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # Internal buffer for in-memory playback (must outlive playback)
        self._buffer: QBuffer | None = None
        self._buffer_data: QByteArray | None = None

        # Connect player signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_error)

        self._playing = False

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play_audio_data(self, audio_data: AudioData) -> None:
        """Play audio from an in-memory AudioData object."""
        self._stop_current()

        raw = audio_data.data

        self._buffer_data = QByteArray(raw)
        self._buffer = QBuffer(self._buffer_data)
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._player.setSourceDevice(self._buffer)
        self._player.play()

    def play_file(self, path: str | Path) -> None:
        """Play audio from a file path."""
        self._stop_current()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()

    def pause(self) -> None:
        self._player.pause()

    def resume(self) -> None:
        self._player.play()

    # ------------------------------------------------------------------
    # Speed control
    # ------------------------------------------------------------------

    def set_speed(self, rate: float) -> None:
        clamped = max(MIN_SPEED, min(MAX_SPEED, rate))
        self._player.setPlaybackRate(clamped)

    @property
    def speed(self) -> float:
        return float(self._player.playbackRate())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def position_seconds(self) -> float:
        return int(self._player.position()) / 1000.0

    @property
    def duration_seconds(self) -> float:
        return int(self._player.duration()) / 1000.0

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_position_changed(self, ms: int) -> None:
        self.playback_position_changed.emit(ms / 1000.0)

    def _on_duration_changed(self, ms: int) -> None:
        self.duration_changed.emit(ms / 1000.0)

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._playing = True
            self.playback_started.emit()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            was_playing = self._playing
            self._playing = False
            if was_playing:
                self.playback_finished.emit()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._playing = False

    def _on_error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self.playback_error.emit(message)

    def _stop_current(self) -> None:
        """Stop any current playback and release buffer."""
        if self._playing:
            self._player.stop()
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
            self._buffer_data = None
