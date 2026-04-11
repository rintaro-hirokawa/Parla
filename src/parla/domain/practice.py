"""Phase C practice value objects and evaluation functions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from parla.domain.audio import AudioData  # noqa: TC001  # Pydantic field needs runtime

if TYPE_CHECKING:
    from collections.abc import Sequence


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
    sentence_texts: tuple[str, ...] = ()
    generated_at: datetime = Field(default_factory=datetime.now)


class PronunciationWord(BaseModel, frozen=True):
    """Single word from Azure Pronunciation Assessment (post miscue correction)."""

    word: str
    accuracy_score: float = Field(ge=0.0, le=100.0)
    error_type: Literal["None", "Mispronunciation", "Omission", "Insertion"]
    offset_seconds: float = -1.0
    duration_seconds: float = 0.0


class OverlappingResult(BaseModel, frozen=True):
    """Result of overlapping practice evaluation."""

    id: UUID = Field(default_factory=uuid4)
    passage_id: UUID
    words: tuple[PronunciationWord, ...]
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
    words: tuple[PronunciationWord, ...]
    accuracy_score: float
    fluency_score: float
    prosody_score: float
    pronunciation_score: float
    created_at: datetime = Field(default_factory=datetime.now)


#: Maximum ratio of error words (Mispronunciation + Omission) allowed to pass.
ERROR_RATE_THRESHOLD: float = 0.15


def calculate_error_rate(words: Sequence[PronunciationWord]) -> float:
    """Calculate ratio of error words (Mispronunciation/Omission) excluding Insertions.

    Insertions are excluded from both numerator and denominator because they
    represent extra words not in the reference text.
    """
    ref_aligned = [w for w in words if w.error_type != "Insertion"]
    if not ref_aligned:
        return 0.0
    error_count = sum(1 for w in ref_aligned if w.error_type in ("Mispronunciation", "Omission"))
    return error_count / len(ref_aligned)


def judge_passed(words: Sequence[PronunciationWord]) -> bool:
    """Judge overall pass/fail based on error rate threshold."""
    return calculate_error_rate(words) < ERROR_RATE_THRESHOLD


def map_words_to_sentence_groups(
    words: tuple[PronunciationWord, ...],
    sentence_texts: tuple[str, ...],
) -> tuple[tuple[PronunciationWord, ...], ...]:
    """Map assessed words to sentence groups, excluding Insertions.

    Splits reference-aligned words sequentially by each sentence's word count.
    """
    ref_aligned = [w for w in words if w.error_type != "Insertion"]
    sentence_word_counts = [len(s.split()) for s in sentence_texts]

    groups: list[tuple[PronunciationWord, ...]] = []
    offset = 0
    for count in sentence_word_counts:
        groups.append(tuple(ref_aligned[offset : offset + count]))
        offset += count
    return tuple(groups)
