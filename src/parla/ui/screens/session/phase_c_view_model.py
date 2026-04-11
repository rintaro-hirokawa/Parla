"""ViewModel for Phase C practice workspace (SCREEN-E6)."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import Signal

from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    OverlappingCompleted,
)
from parla.ui.base_view_model import BaseViewModel

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.audio import AudioData
    from parla.domain.practice import WordTimestamp
    from parla.event_bus import EventBus
    from parla.ports.pronunciation_assessment import StreamingAssessmentSession
    from parla.services.practice_service import PracticeService
    from parla.services.session_query_service import SessionQueryService
    from parla.ui.audio.player import AudioPlayer
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.session_context import SessionContext

type PracticeMode = Literal["listening", "overlapping", "live_delivery"]

_ALL_MODES: tuple[PracticeMode, ...] = ("listening", "overlapping", "live_delivery")


class PhaseCViewModel(BaseViewModel):
    """Manages Phase C: listening, overlapping, and live delivery modes."""

    mode_changed = Signal(str)
    model_audio_ready = Signal()
    model_audio_failed = Signal(str)
    overlapping_result = Signal(float)  # pronunciation_score
    live_delivery_result = Signal(bool, float, float, float)  # passed, error_rate, error_rate_threshold, wpm
    complete_enabled_changed = Signal(bool)
    phase_complete = Signal()
    error = Signal(str)

    # Playback transport signals
    playback_position_changed = Signal(float)  # seconds
    playback_duration_changed = Signal(float)  # seconds
    playback_state_changed = Signal(str)  # "playing" / "paused" / "stopped"

    # Per-word overlapping results
    overlapping_words_ready = Signal(object)  # OverlappingSummary
    live_delivery_detail_ready = Signal(object)  # LiveDeliverySummary

    def __init__(
        self,
        *,
        event_bus: EventBus,
        practice_service: PracticeService,
        audio_player: AudioPlayer,
        recorder: AudioRecorder,
        session_context: SessionContext,
        session_query_service: SessionQueryService | None = None,
    ) -> None:
        super().__init__(event_bus)
        self._practice_service = practice_service
        self._player = audio_player
        self._recorder = recorder
        self._ctx = session_context
        self._session_query = session_query_service

        self._passage_id: UUID | None = None
        self._current_mode: PracticeMode = "listening"
        self._model_audio_loaded = False
        self._live_delivery_passed = False
        self._sentence_texts: tuple[str, ...] = ()
        self._sentence_ja_texts: tuple[str, ...] = ()
        self._word_timestamps: tuple[WordTimestamp, ...] = ()
        self._streaming_session: StreamingAssessmentSession | None = None

        self._register_sync(ModelAudioReady, self._on_model_audio_ready)
        self._register_sync(ModelAudioFailed, self._on_model_audio_failed)
        self._register_sync(OverlappingCompleted, self._on_overlapping_completed)
        self._register_sync(LiveDeliveryCompleted, self._on_live_delivery_completed)

        # Relay player signals
        self._player.playback_position_changed.connect(self.playback_position_changed)
        self._player.duration_changed.connect(self.playback_duration_changed)
        self._player.playback_started.connect(lambda: self.playback_state_changed.emit("playing"))
        self._player.playback_finished.connect(self._on_playback_finished)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> PracticeMode:
        return self._current_mode

    @property
    def available_modes(self) -> tuple[PracticeMode, ...]:
        return _ALL_MODES

    @property
    def is_model_audio_loaded(self) -> bool:
        return self._model_audio_loaded

    @property
    def is_complete_enabled(self) -> bool:
        return self._live_delivery_passed

    @property
    def sentence_texts(self) -> tuple[str, ...]:
        return self._sentence_texts

    @property
    def sentence_ja_texts(self) -> tuple[str, ...]:
        return self._sentence_ja_texts

    @property
    def word_timestamps(self) -> tuple[WordTimestamp, ...]:
        return self._word_timestamps

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start(
        self,
        passage_id: UUID,
        *,
        sentence_ja_texts: tuple[str, ...] = (),
    ) -> None:
        self._passage_id = passage_id
        self._current_mode = "listening"
        self._model_audio_loaded = False
        self._sentence_texts = ()
        self._sentence_ja_texts = sentence_ja_texts
        self._word_timestamps = ()

        # Model audio may already be ready (generated during Phase B)
        existing = self._practice_service.get_model_audio(passage_id)
        if existing is not None:
            self._model_audio_loaded = True
            self._sentence_texts = existing.sentence_texts
            self._word_timestamps = existing.word_timestamps

    def switch_mode(self, mode: PracticeMode) -> None:
        if mode not in _ALL_MODES:
            return
        self._current_mode = mode
        self.mode_changed.emit(mode)

    def set_speed(self, rate: float) -> None:
        self._player.set_speed(rate)

    def play_model(self) -> None:
        """Alias for toggle_play_pause (backward compatibility)."""
        self.toggle_play_pause()

    def toggle_play_pause(self) -> None:
        if self._passage_id is None:
            return
        if self._player.is_playing:
            self._player.pause()
            self.playback_state_changed.emit("paused")
            if self._current_mode == "overlapping" and self._recorder.is_recording:
                self._recorder.stop()
                self._stop_overlapping_stream()
            return
        if self._player.is_paused:
            self._player.resume()
            return
        # Stopped — load and play
        model_audio = self._practice_service.get_model_audio(self._passage_id)
        if model_audio is None:
            self.model_audio_failed.emit("モデル音声が見つかりません")
            return
        self._player.play_audio_data(model_audio.audio)
        if self._current_mode == "overlapping":
            self._start_overlapping_stream()
            self._recorder.start()

    def seek(self, seconds: float) -> None:
        self._player.seek(seconds)

    def skip(self, delta: float) -> None:
        pos = self._player.position_seconds + delta
        pos = max(0.0, min(pos, self._player.duration_seconds))
        self._player.seek(pos)

    def reset_to_start(self) -> None:
        self._player.seek(0.0)

    def submit_overlapping(self, audio: AudioData) -> None:
        if self._passage_id is None:
            return
        asyncio.ensure_future(
            self._practice_service.evaluate_overlapping(self._passage_id, audio)
        )

    def submit_live_delivery(self, audio: AudioData) -> None:
        if self._passage_id is None:
            return
        asyncio.ensure_future(
            self._practice_service.evaluate_live_delivery(self._passage_id, audio)
        )

    def on_recording_started(self) -> None:
        """Handle recording start from RecordingControlsWidget."""
        if self._current_mode == "live_delivery":
            self._start_live_delivery_stream()

    def on_recording_finished(self, audio_data: AudioData) -> None:
        """Handle recording completion from RecordingControlsWidget."""
        if self._current_mode == "live_delivery":
            if self._streaming_session is not None:
                self._finalize_live_delivery_stream()
            else:
                self.submit_live_delivery(audio_data)

    def retry_model_audio(self) -> None:
        """Re-request model audio generation after a failure."""
        if self._passage_id is not None:
            self._practice_service.request_model_audio(self._passage_id)

    def complete(self) -> None:
        self._player.stop()
        self.phase_complete.emit()

    # ------------------------------------------------------------------
    # Streaming assessment
    # ------------------------------------------------------------------

    def _start_overlapping_stream(self) -> None:
        """Start a streaming assessment session for the current passage."""
        if self._passage_id is None:
            return
        session = self._practice_service.start_overlapping_stream(self._passage_id)
        if session is not None:
            self._streaming_session = session
            self._recorder.chunk_ready.connect(self._on_recorder_chunk)

    def _start_live_delivery_stream(self) -> None:
        """Start a streaming assessment session for live delivery."""
        if self._passage_id is None:
            return
        session = self._practice_service.start_live_delivery_stream(self._passage_id)
        if session is not None:
            self._streaming_session = session
            self._recorder.chunk_ready.connect(self._on_recorder_chunk)

    def _finalize_live_delivery_stream(self) -> None:
        """Disconnect chunk forwarding and finalize the live delivery stream."""
        with contextlib.suppress(RuntimeError):
            self._recorder.chunk_ready.disconnect(self._on_recorder_chunk)
        if self._streaming_session is not None and self._passage_id is not None:
            session = self._streaming_session
            self._streaming_session = None
            asyncio.ensure_future(
                self._practice_service.finalize_live_delivery_stream(
                    self._passage_id, session
                )
            )

    def _on_recorder_chunk(self, pcm_data: bytes) -> None:
        """Forward PCM chunk from recorder to the Azure streaming session."""
        if self._streaming_session is not None:
            self._streaming_session.push_chunk(pcm_data)

    def current_sentence_index(self, position_seconds: float) -> int:
        """Return the sentence index that contains the given playback position."""
        if not self._sentence_texts or not self._word_timestamps:
            return -1
        word_counts = [len(s.split()) for s in self._sentence_texts]
        offset = 0
        for i, count in enumerate(word_counts):
            if offset >= len(self._word_timestamps):
                break
            end_idx = min(offset + count - 1, len(self._word_timestamps) - 1)
            end_t = self._word_timestamps[end_idx].end_seconds
            if position_seconds <= end_t:
                return i
            offset += count
        return len(word_counts) - 1

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_playback_finished(self) -> None:
        self.playback_state_changed.emit("stopped")
        if self._current_mode == "overlapping" and self._recorder.is_recording:
            self._recorder.stop()
            self._stop_overlapping_stream()

    def _stop_overlapping_stream(self) -> None:
        """Disconnect chunk forwarding and finalize the streaming session."""
        with contextlib.suppress(RuntimeError):
            self._recorder.chunk_ready.disconnect(self._on_recorder_chunk)
        if self._streaming_session is not None and self._passage_id is not None:
            session = self._streaming_session
            self._streaming_session = None
            asyncio.ensure_future(
                self._practice_service.finalize_overlapping_stream(
                    self._passage_id, session
                )
            )

    def _on_model_audio_ready(self, event: ModelAudioReady) -> None:
        if event.passage_id != self._passage_id:
            return
        self._model_audio_loaded = True
        existing = self._practice_service.get_model_audio(event.passage_id)
        if existing is not None:
            self._sentence_texts = existing.sentence_texts
            self._word_timestamps = existing.word_timestamps
        self.model_audio_ready.emit()

    def _on_model_audio_failed(self, event: ModelAudioFailed) -> None:
        if event.passage_id != self._passage_id:
            return
        self.model_audio_failed.emit(event.error_message)

    def _on_overlapping_completed(self, event: OverlappingCompleted) -> None:
        if event.passage_id != self._passage_id:
            return
        self.overlapping_result.emit(event.pronunciation_score)

        if self._session_query is not None:
            summary = self._session_query.get_overlapping_summary(event.passage_id)
            if summary is not None:
                self.overlapping_words_ready.emit(summary)

    def _on_live_delivery_completed(self, event: LiveDeliveryCompleted) -> None:
        if event.passage_id != self._passage_id:
            return
        if event.passed and not self._live_delivery_passed:
            self._live_delivery_passed = True
            self.complete_enabled_changed.emit(True)
        self.live_delivery_result.emit(event.passed, event.error_rate, event.error_rate_threshold, event.wpm)

        if self._session_query is not None:
            summary = self._session_query.get_live_delivery_summary(event.passage_id)
            if summary is not None:
                self.live_delivery_detail_ready.emit(summary)
