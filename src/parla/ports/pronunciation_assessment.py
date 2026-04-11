"""Port for pronunciation assessment from audio.

Single port for both overlapping and live delivery modes.
The adapter handles streaming, difflib miscue correction, and Azure-specific details.
The domain receives clean, corrected word data.
"""

from typing import Literal, Protocol

from pydantic import BaseModel

from parla.domain.audio import AudioData

ErrorType = Literal["None", "Mispronunciation", "Omission", "Insertion"]


class RawAssessedWord(BaseModel, frozen=True):
    """Word-level assessment result from the adapter (post miscue correction)."""

    word: str
    accuracy_score: float
    error_type: ErrorType
    offset_seconds: float
    duration_seconds: float


class RawAssessmentResult(BaseModel, frozen=True):
    """Pronunciation assessment result from the adapter."""

    recognized_text: str
    words: tuple[RawAssessedWord, ...]
    accuracy_score: float
    fluency_score: float
    completeness_score: float
    prosody_score: float
    pronunciation_score: float


class StreamingAssessmentSession(Protocol):
    """A live streaming session that accepts PCM chunks incrementally."""

    def push_chunk(self, pcm_data: bytes) -> None:
        """Push a raw PCM chunk (16-bit mono) to the assessment stream."""
        ...

    async def finalize(self) -> RawAssessmentResult:
        """Close the stream and return the assessment result."""
        ...


class PronunciationAssessmentPort(Protocol):
    """Assesses pronunciation quality and word-level timing from audio."""

    async def assess(
        self,
        audio: AudioData,
        reference_text: str,
    ) -> RawAssessmentResult: ...

    def start_streaming(
        self,
        reference_text: str,
        *,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
    ) -> StreamingAssessmentSession: ...
