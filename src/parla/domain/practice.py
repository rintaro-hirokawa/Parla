"""Phase C practice value objects and evaluation functions."""

from collections.abc import Sequence
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
    sentence_texts: tuple[str, ...] = ()
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


def evaluate_sentence_statuses(
    sentence_texts: Sequence[str],
    assessed_words: tuple[PronunciationWord, ...],
) -> list[SentenceStatus]:
    """Map assessed words to sentences and evaluate each sentence.

    For each sentence:
    1. Groups reference-aligned words (excluding Insertions)
    2. Reconstructs user text (excluding Omissions)
    3. Calculates similarity against model text
    4. Judges status based on similarity and omission ratio
    """
    from parla.domain.similarity import calculate_similarity, judge_sentence_status

    groups = map_words_to_sentence_groups(
        assessed_words, tuple(sentence_texts)
    )

    results: list[SentenceStatus] = []
    for i, (text, sentence_words) in enumerate(
        zip(sentence_texts, groups, strict=False)
    ):
        user_words = [w.word for w in sentence_words if w.error_type != "Omission"]
        user_text = " ".join(user_words) if user_words else "(no speech)"

        similarity = calculate_similarity(text, user_text)

        omission_count = sum(1 for w in sentence_words if w.error_type == "Omission")
        omission_ratio = omission_count / max(len(sentence_words), 1)

        status = judge_sentence_status(similarity, omission_ratio)

        results.append(
            SentenceStatus(
                sentence_index=i,
                recognized_text=user_text,
                model_text=text,
                similarity=similarity,
                status=status,
            )
        )

    return results
