"""Session composition domain types and pure functions.

Session composition is fully deterministic — no LLM involved.
Pattern selection and block assembly are pure functions driven by config.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

type BlockType = Literal["review", "new_material", "consolidation"]
type SessionPattern = Literal["a", "b", "c"]
type SessionStatus = Literal["not_started", "in_progress", "completed", "interrupted"]


class SessionConfig(BaseModel, frozen=True):
    """Session composition parameters — loaded from config, immutable at runtime."""

    review_overflow_threshold: int = 30
    estimated_minutes_per_review: float = 2.0
    estimated_minutes_per_passage: float = 10.0
    estimated_minutes_per_consolidation: float = 2.0


class SessionBlock(BaseModel, frozen=True):
    """A single block within a session menu."""

    block_type: BlockType
    items: tuple[UUID, ...] = ()
    estimated_minutes: float = 0.0


class SessionMenu(BaseModel, frozen=True):
    """A composed session menu — immutable value object."""

    id: UUID = Field(default_factory=uuid4)
    target_date: date
    pattern: SessionPattern
    blocks: tuple[SessionBlock, ...]
    source_id: UUID | None = None
    confirmed: bool = False
    pending_review_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    """Mutable session execution state — tracks progress through blocks."""

    id: UUID = Field(default_factory=uuid4)
    menu_id: UUID
    status: SessionStatus = "not_started"
    current_block_index: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    interrupted_at: datetime | None = None


# --- Pure functions ---


def select_pattern(pending_review_count: int, config: SessionConfig) -> SessionPattern:
    """Deterministic pattern selection based on pending review count.

    - 0 pending → pattern c (new material only)
    - Above overflow threshold → pattern b (review only)
    - Otherwise → pattern a (review + new + consolidation)
    """
    if pending_review_count == 0:
        return "c"
    if pending_review_count > config.review_overflow_threshold:
        return "b"
    return "a"


def compose_blocks(
    *,
    pattern: SessionPattern,
    review_item_ids: Sequence[UUID],
    passage_ids: Sequence[UUID],
    config: SessionConfig,
) -> tuple[SessionBlock, ...]:
    """Build the block sequence for a given pattern.

    Block 3 (consolidation) items are unknown at composition time
    (they come from Block 2 during the session), so items=() and
    estimated_minutes=0.0.
    """
    blocks: list[SessionBlock] = []

    if pattern in ("a", "b"):
        blocks.append(
            SessionBlock(
                block_type="review",
                items=tuple(review_item_ids),
                estimated_minutes=len(review_item_ids) * config.estimated_minutes_per_review,
            )
        )

    if pattern in ("a", "c"):
        blocks.append(
            SessionBlock(
                block_type="new_material",
                items=tuple(passage_ids),
                estimated_minutes=len(passage_ids) * config.estimated_minutes_per_passage,
            )
        )
        blocks.append(
            SessionBlock(
                block_type="consolidation",
                items=(),
                estimated_minutes=0.0,
            )
        )

    return tuple(blocks)
