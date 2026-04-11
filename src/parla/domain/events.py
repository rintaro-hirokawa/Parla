"""Domain events. All events are defined in this single file for discoverability."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from parla.domain.session import SessionPattern
from parla.domain.source import CEFRLevel, EnglishVariant


class Event(BaseModel, frozen=True):
    """Base class for all domain events. Immutable value objects."""

# --- Slice 7: User Settings ---


class SettingsChanged(Event, frozen=True):
    """User settings have been updated."""

    cefr_level: CEFRLevel
    english_variant: EnglishVariant
    phonetic_display: bool


# --- Slice 1: Source registration & passage generation ---


class SourceRegistered(Event, frozen=True):
    """A source has been registered. Triggers passage generation."""

    source_id: UUID


class PassageGenerationStarted(Event, frozen=True):
    """Passage generation has started (status: generating)."""

    source_id: UUID


class PassageGenerationCompleted(Event, frozen=True):
    """Passage generation completed successfully (status: not_started)."""

    source_id: UUID
    passage_count: int
    total_sentences: int


class PassageGenerationFailed(Event, frozen=True):
    """Passage generation failed (status: generation_failed)."""

    source_id: UUID
    error_message: str


# --- Slice 2: Phase A → Phase B (feedback & retry) ---


class SentenceRecorded(Event, frozen=True):
    """User finished speaking a sentence in Phase A. Triggers feedback generation."""

    passage_id: UUID
    sentence_id: UUID


class FeedbackReady(Event, frozen=True):
    """Feedback generated successfully for a sentence."""

    passage_id: UUID
    sentence_id: UUID


class FeedbackFailed(Event, frozen=True):
    """Feedback generation failed for a sentence."""

    passage_id: UUID
    sentence_id: UUID
    error_message: str


class LearningItemStocked(Event, frozen=True):
    """A learning item was auto-stocked from feedback."""

    item_id: UUID
    pattern: str
    is_reappearance: bool


class RetryJudged(Event, frozen=True):
    """Retry judgment completed for a sentence in Phase B."""

    sentence_id: UUID
    attempt: int
    correct: bool


# --- Slice 3: Block 1 Review (SRS) ---


class VariationGenerationRequested(Event, frozen=True):
    """Request to generate a variation for a learning item."""

    learning_item_id: UUID
    source_id: UUID


class VariationReady(Event, frozen=True):
    """A variation has been generated and is ready for review."""

    variation_id: UUID
    learning_item_id: UUID


class VariationGenerationFailed(Event, frozen=True):
    """Variation generation failed for a learning item."""

    learning_item_id: UUID
    error_message: str


class ReviewAnswered(Event, frozen=True):
    """Initial review attempt judged. Triggers SRS update."""

    variation_id: UUID
    learning_item_id: UUID
    correct: bool
    item_used: bool
    hint_level: int
    timer_ratio: float


class ReviewRetryJudged(Event, frozen=True):
    """Review retry judged. Does NOT affect SRS (initial attempt only)."""

    variation_id: UUID
    attempt: int
    correct: bool


class SRSUpdated(Event, frozen=True):
    """SRS state updated after review."""

    learning_item_id: UUID
    old_stage: int
    new_stage: int
    next_review_date: date


# --- Slice 4: Phase C（通し練習）---


class ModelAudioRequested(Event, frozen=True):
    """TTS generation requested for a passage's dynamic model answers."""

    passage_id: UUID


class ModelAudioReady(Event, frozen=True):
    """TTS model audio generated and cached."""

    passage_id: UUID


class ModelAudioFailed(Event, frozen=True):
    """TTS generation failed."""

    passage_id: UUID
    error_message: str


class OverlappingCompleted(Event, frozen=True):
    """Overlapping practice evaluated."""

    passage_id: UUID
    pronunciation_score: float


class LiveDeliveryCompleted(Event, frozen=True):
    """Live delivery evaluated."""

    passage_id: UUID
    passed: bool
    error_rate: float
    error_rate_threshold: float
    wpm: float


class PassageAchievementRecorded(Event, frozen=True):
    """通し発話達成 recorded for a passage."""

    passage_id: UUID


# --- Slice 5: Session Composition & Menu ---


class MenuComposed(Event, frozen=True):
    """A session menu has been auto-composed."""

    menu_id: UUID
    target_date: date
    pattern: SessionPattern
    block_count: int


class MenuConfirmed(Event, frozen=True):
    """User confirmed tomorrow's menu. Triggers background generation."""

    menu_id: UUID
    target_date: date


class MenuRecomposed(Event, frozen=True):
    """Menu was recomposed after source change."""

    menu_id: UUID
    new_source_id: UUID


class BackgroundGenerationStarted(Event, frozen=True):
    """Background variation generation started for confirmed menu."""

    menu_id: UUID
    item_count: int


class BackgroundGenerationCompleted(Event, frozen=True):
    """All background variations generated for the menu."""

    menu_id: UUID
    success_count: int
    failure_count: int


class SessionStarted(Event, frozen=True):
    """A session has been started."""

    session_id: UUID
    menu_id: UUID


class SessionInterrupted(Event, frozen=True):
    """Session was interrupted mid-way."""

    session_id: UUID
    block_index: int


class SessionResumed(Event, frozen=True):
    """Session resumed from interruption point."""

    session_id: UUID
    block_index: int


class SessionCompleted(Event, frozen=True):
    """Session fully completed."""

    session_id: UUID
