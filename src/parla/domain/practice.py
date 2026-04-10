"""Phase C practice value objects."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from parla.domain.audio import AudioData


class WordTimestamp(BaseModel, frozen=True):
    """Reference timestamp for a single word from TTS generation."""

    word: str
    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(ge=0.0)


class ModelAudio(BaseModel, frozen=True):
    """TTS-generated model answer audio with reference timestamps."""

    passage_id: UUID
    audio: AudioData
    word_timestamps: tuple[WordTimestamp, ...]
    generated_at: datetime = Field(default_factory=datetime.now)


class PronunciationWord(BaseModel, frozen=True):
    """Single word from Azure Pronunciation Assessment (post miscue correction)."""

    word: str
    accuracy_score: float = Field(ge=0.0, le=100.0)
    error_type: Literal["None", "Mispronunciation", "Omission", "Insertion"]
    offset_seconds: float = -1.0
    duration_seconds: float = 0.0


class SentenceStatus(BaseModel, frozen=True):
    """Per-sentence evaluation result for live delivery."""

    sentence_index: int = Field(ge=0)
    recognized_text: str
    model_text: str
    similarity: float = Field(ge=0.0, le=1.0)
    status: Literal["correct", "paraphrase", "error"]


class OverlappingResult(BaseModel, frozen=True):
    """Result of overlapping practice evaluation."""

    id: UUID = Field(default_factory=uuid4)
    passage_id: UUID
    words: tuple[PronunciationWord, ...]
    timing_deviations: tuple[float, ...]
    accuracy_score: float
    fluency_score: float
    prosody_score: float
    pronunciation_score: float
    created_at: datetime = Field(default_factory=datetime.now)


class LiveDeliveryResult(BaseModel, frozen=True):
    """Result of live delivery evaluation."""

    id: UUID = Field(default_factory=uuid4)
    passage_id: UUID
    passed: bool
    sentence_statuses: tuple[SentenceStatus, ...]
    duration_seconds: float = Field(ge=0.0)
    wpm: float = Field(ge=0.0)
    created_at: datetime = Field(default_factory=datetime.now)
