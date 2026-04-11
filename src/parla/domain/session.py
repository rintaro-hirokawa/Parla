"""Session composition domain types and pure functions.

Session composition is fully deterministic — no LLM involved.
Pattern selection and block assembly are pure functions driven by config.
"""

from collections.abc import Sequence
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from parla.domain.errors import InvalidStatusTransition


class BlockType(StrEnum):
    REVIEW = "review"
    NEW_MATERIAL = "new_material"
    CONSOLIDATION = "consolidation"


class SessionPattern(StrEnum):
    REVIEW_AND_NEW = "review_and_new"
    REVIEW_ONLY = "review_only"
    NEW_ONLY = "new_only"


class SessionStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


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

    def confirm(self) -> "SessionMenu":
        """Return a confirmed copy. Idempotent."""
        return self.model_copy(update={"confirmed": True})


_VALID_SESSION_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.NOT_STARTED: {SessionStatus.IN_PROGRESS},
    SessionStatus.IN_PROGRESS: {SessionStatus.INTERRUPTED, SessionStatus.COMPLETED},
    SessionStatus.INTERRUPTED: {SessionStatus.IN_PROGRESS},
    SessionStatus.COMPLETED: set(),
}


class SessionState(BaseModel, frozen=True):
    """Immutable session execution state — tracks progress through blocks."""

    id: UUID = Field(default_factory=uuid4)
    menu_id: UUID
    status: SessionStatus = SessionStatus.NOT_STARTED
    current_block_index: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    interrupted_at: datetime | None = None

    @classmethod
    def start(cls, menu_id: UUID) -> "SessionState":
        """Factory: create a new session in IN_PROGRESS state."""
        return cls(
            menu_id=menu_id,
            status=SessionStatus.IN_PROGRESS,
            started_at=datetime.now(),
        )

    def _transition(self, new_status: SessionStatus, **updates: object) -> "SessionState":
        if new_status not in _VALID_SESSION_TRANSITIONS[self.status]:
            msg = f"Cannot transition session from '{self.status}' to '{new_status}'"
            raise InvalidStatusTransition(msg)
        return self.model_copy(update={"status": new_status, **updates})

    def interrupt(self) -> "SessionState":
        """IN_PROGRESS → INTERRUPTED."""
        return self._transition(SessionStatus.INTERRUPTED, interrupted_at=datetime.now())

    def resume(self) -> "SessionState":
        """INTERRUPTED → IN_PROGRESS."""
        return self._transition(SessionStatus.IN_PROGRESS, interrupted_at=None)

    def complete(self) -> "SessionState":
        """IN_PROGRESS → COMPLETED."""
        return self._transition(SessionStatus.COMPLETED, completed_at=datetime.now())

    def advance_block(self, total_blocks: int) -> "SessionState":
        """Advance to next block, or complete if at last block."""
        if self.status != SessionStatus.IN_PROGRESS:
            msg = f"Cannot advance block when session status is '{self.status}'"
            raise InvalidStatusTransition(msg)
        next_index = self.current_block_index + 1
        if next_index >= total_blocks:
            return self.complete()
        return self.model_copy(update={"current_block_index": next_index})


# --- Pure functions ---


def select_next_unlearned_passage(
    passage_ids: Sequence[UUID],
    learned_passage_ids: set[UUID],
) -> UUID | None:
    """Return the first passage ID not in the learned set, or None if all learned."""
    for pid in passage_ids:
        if pid not in learned_passage_ids:
            return pid
    return None


def select_pattern(pending_review_count: int, config: SessionConfig) -> SessionPattern:
    """Deterministic pattern selection based on pending review count.

    - 0 pending → NEW_ONLY (new material only)
    - Above overflow threshold → REVIEW_ONLY (review only)
    - Otherwise → REVIEW_AND_NEW (review + new + consolidation)
    """
    if pending_review_count == 0:
        return SessionPattern.NEW_ONLY
    if pending_review_count > config.review_overflow_threshold:
        return SessionPattern.REVIEW_ONLY
    return SessionPattern.REVIEW_AND_NEW


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

    if pattern in (SessionPattern.REVIEW_AND_NEW, SessionPattern.REVIEW_ONLY):
        blocks.append(
            SessionBlock(
                block_type=BlockType.REVIEW,
                items=tuple(review_item_ids),
                estimated_minutes=len(review_item_ids) * config.estimated_minutes_per_review,
            )
        )

    if pattern in (SessionPattern.REVIEW_AND_NEW, SessionPattern.NEW_ONLY):
        blocks.append(
            SessionBlock(
                block_type=BlockType.NEW_MATERIAL,
                items=tuple(passage_ids),
                estimated_minutes=len(passage_ids) * config.estimated_minutes_per_passage,
            )
        )
        blocks.append(
            SessionBlock(
                block_type=BlockType.CONSOLIDATION,
                items=(),
                estimated_minutes=0.0,
            )
        )

    return tuple(blocks)
