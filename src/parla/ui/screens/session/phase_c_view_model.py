"""ViewModel for Phase C practice workspace (SCREEN-E6)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from PySide6.QtCore import Signal

from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    OverlappingCompleted,
    OverlappingLagDetected,
)
from parla.ui.base_view_model import BaseViewModel

if TYPE_CHECKING:
    from uuid import UUID

    from parla.domain.audio import AudioData
    from parla.event_bus import EventBus
    from parla.ui.screens.session.session_context import SessionContext

type PracticeMode = Literal["listening", "overlapping", "live_delivery"]

_ALL_MODES: tuple[PracticeMode, ...] = ("listening", "overlapping", "live_delivery")


class PhaseCViewModel(BaseViewModel):
    """Manages Phase C: listening, overlapping, and live delivery modes."""

    mode_changed = Signal(str)
    model_audio_ready = Signal()
    model_audio_failed = Signal(str)
    overlapping_result = Signal(float)  # pronunciation_score
    lag_detected = Signal(int)  # lag_count
    live_delivery_result = Signal(bool, float)  # passed, wpm
    phase_complete = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        practice_service: Any,
        audio_player: Any,
        session_context: SessionContext,
    ) -> None:
        super().__init__(event_bus)
        self._practice_service = practice_service
        self._player = audio_player
        self._ctx = session_context

        self._passage_id: UUID | None = None
        self._current_mode: PracticeMode = "listening"
        self._model_audio_loaded = False

        self._register_sync(ModelAudioReady, self._on_model_audio_ready)
        self._register_sync(ModelAudioFailed, self._on_model_audio_failed)
        self._register_sync(OverlappingCompleted, self._on_overlapping_completed)
        self._register_sync(OverlappingLagDetected, self._on_lag_detected)
        self._register_sync(LiveDeliveryCompleted, self._on_live_delivery_completed)

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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start(self, passage_id: UUID) -> None:
        self._passage_id = passage_id
        self._current_mode = "listening"
        self._model_audio_loaded = False

    def switch_mode(self, mode: PracticeMode) -> None:
        if mode not in _ALL_MODES:
            return
        self._current_mode = mode
        self.mode_changed.emit(mode)

    def set_speed(self, rate: float) -> None:
        self._player.set_speed(rate)

    def play_model(self, audio_data: AudioData) -> None:
        self._player.play_audio_data(audio_data)

    def submit_overlapping(self, audio: AudioData) -> None:
        if self._passage_id is None:
            return
        asyncio.ensure_future(
            self._practice_service.evaluate_overlapping(self._passage_id, audio)
        )

    def submit_live_delivery(self, audio: AudioData, duration_seconds: float) -> None:
        if self._passage_id is None:
            return
        asyncio.ensure_future(
            self._practice_service.evaluate_live_delivery(
                self._passage_id, audio, duration_seconds
            )
        )

    def complete(self) -> None:
        self.phase_complete.emit()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_model_audio_ready(self, event: ModelAudioReady) -> None:
        if event.passage_id != self._passage_id:
            return
        self._model_audio_loaded = True
        self.model_audio_ready.emit()

    def _on_model_audio_failed(self, event: ModelAudioFailed) -> None:
        if event.passage_id != self._passage_id:
            return
        self.model_audio_failed.emit(event.error_message)

    def _on_overlapping_completed(self, event: OverlappingCompleted) -> None:
        if event.passage_id != self._passage_id:
            return
        self.overlapping_result.emit(event.pronunciation_score)

    def _on_lag_detected(self, event: OverlappingLagDetected) -> None:
        if event.passage_id != self._passage_id:
            return
        self.lag_detected.emit(event.lag_count)

    def _on_live_delivery_completed(self, event: LiveDeliveryCompleted) -> None:
        if event.passage_id != self._passage_id:
            return
        self.live_delivery_result.emit(event.passed, event.wpm)
