"""Read model DTOs for Query Services.

Query Services are read-only components in the service layer.
Rules:
- No side effects, no EventBus emit, no state changes
- Return UI-oriented DTOs (this module), not domain entities
- Aggregate data from multiple repositories as needed
- ViewModel / View must not contain SQL or aggregation logic
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from parla.domain.learning_item import LearningItemCategory, LearningItemStatus
from parla.domain.session import BlockType, SessionPattern
from parla.domain.source import CEFRLevel, EnglishVariant, SourceStatus

# --- AppStateQueryService DTOs ---


class BootstrapState(BaseModel, frozen=True):
    """Application startup state for routing decisions."""

    needs_setup: bool
    has_resumable_session: bool
    resumable_session_id: UUID | None = None
    has_today_menu: bool
    today_menu_confirmed: bool = False


# --- SourceQueryService DTOs ---


class SourceSummary(BaseModel, frozen=True):
    """Source list row for D2 / F2."""

    id: UUID
    title: str
    cefr_level: CEFRLevel
    english_variant: EnglishVariant
    status: SourceStatus
    passage_count: int = 0
    learned_passage_count: int = 0
    created_at: datetime

    @property
    def progress_ratio(self) -> float:
        if self.passage_count == 0:
            return 0.0
        return self.learned_passage_count / self.passage_count

    @property
    def is_completed(self) -> bool:
        return self.passage_count > 0 and self.learned_passage_count == self.passage_count


# --- LearningItemQueryService DTOs ---


class LearningItemRow(BaseModel, frozen=True):
    """Learning item list row for C2."""

    id: UUID
    pattern: str
    explanation: str
    category: LearningItemCategory
    sub_tag: str = ""
    status: LearningItemStatus
    srs_stage: int = 0
    next_review_date: date | None = None
    source_title: str = ""
    source_sentence_ja: str = ""
    created_at: datetime


class LearningItemFilter(BaseModel, frozen=True):
    """Filter criteria for learning item list."""

    category: LearningItemCategory | None = None
    status: LearningItemStatus | None = None
    srs_stage: int | None = None
    source_id: UUID | None = None


class LearningItemDetail(BaseModel, frozen=True):
    """Learning item detail for C3."""

    id: UUID
    pattern: str
    explanation: str
    category: LearningItemCategory
    sub_tag: str = ""
    status: LearningItemStatus
    srs_stage: int = 0
    ease_factor: float = 1.0
    next_review_date: date | None = None
    correct_context_count: int = 0
    source_title: str = ""
    source_sentence_ja: str = ""
    source_sentence_en: str = ""
    first_utterance: str = ""
    created_at: datetime


class SentenceItemRow(BaseModel, frozen=True):
    """Learning item associated with a sentence (for hints / E4 display)."""

    id: UUID
    pattern: str
    explanation: str
    category: LearningItemCategory
    status: LearningItemStatus
    is_reappearance: bool = False


# --- SessionQueryService DTOs ---


class MenuBlockSummary(BaseModel, frozen=True):
    """Block summary within a menu display."""

    block_type: BlockType
    item_count: int = 0
    estimated_minutes: float = 0.0


class TodayDashboard(BaseModel, frozen=True):
    """Today's learning tab data for C1."""

    has_sources: bool = False
    has_menu: bool = False
    menu_confirmed: bool = False
    menu_id: UUID | None = None
    pattern: SessionPattern | None = None
    blocks: tuple[MenuBlockSummary, ...] = ()
    total_estimated_minutes: float = 0.0
    source_title: str = ""
    has_resumable_session: bool = False
    resumable_session_id: UUID | None = None


class SessionSummaryBlock(BaseModel, frozen=True):
    """Block result in session summary."""

    block_type: BlockType
    item_count: int = 0
    completed_count: int = 0


class SessionSummary(BaseModel, frozen=True):
    """Session completion summary for F1."""

    session_id: UUID
    pattern: SessionPattern
    blocks: tuple[SessionSummaryBlock, ...] = ()


# --- Pronunciation assessment summary DTOs (shared by overlapping & live delivery) ---


class PronunciationWordResult(BaseModel, frozen=True):
    """Per-word pronunciation result for display."""

    word: str
    error_type: str
    accuracy_score: float


class OverlappingSummary(BaseModel, frozen=True):
    """Overlapping evaluation summary for Phase C display."""

    pronunciation_score: float
    sentence_words: tuple[tuple[PronunciationWordResult, ...], ...]


class LiveDeliverySummary(BaseModel, frozen=True):
    """Live delivery evaluation summary for Phase C display."""

    passed: bool
    pronunciation_score: float
    sentence_words: tuple[tuple[PronunciationWordResult, ...], ...]
