"""Port for TTS audio generation with word-level timestamps."""

from typing import Protocol

from pydantic import BaseModel, Field


class RawWordTimestamp(BaseModel, frozen=True):
    """Word timestamp as returned by the TTS adapter."""

    word: str
    start_seconds: float
    end_seconds: float


class RawTTSResult(BaseModel, frozen=True):
    """TTS generation result from the adapter."""

    audio_data: bytes
    audio_format: str
    sample_rate: int
    channels: int = 1
    sample_width: int = 2
    duration_seconds: float = Field(ge=0.0)
    word_timestamps: tuple[RawWordTimestamp, ...]


class TTSGenerationPort(Protocol):
    """Generates TTS audio with word-level timestamps for model answers."""

    async def generate_with_timestamps(
        self,
        text: str,
        english_variant: str,
    ) -> RawTTSResult: ...
