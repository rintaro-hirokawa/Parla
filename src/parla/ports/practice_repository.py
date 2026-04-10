"""Port for Phase C practice result persistence."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from parla.domain.practice import (
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
)


class PracticeRepository(Protocol):
    """Persists Phase C practice results and achievements."""

    def save_model_audio(self, model_audio: ModelAudio) -> None: ...

    def get_model_audio(self, passage_id: UUID) -> ModelAudio | None: ...

    def save_overlapping_result(self, result: OverlappingResult) -> None: ...

    def save_live_delivery_result(self, result: LiveDeliveryResult) -> None: ...

    def get_live_delivery_results(self, passage_id: UUID) -> Sequence[LiveDeliveryResult]: ...

    def save_achievement(self, passage_id: UUID, achieved_at: datetime) -> None: ...

    def has_achievement(self, passage_id: UUID) -> bool: ...
