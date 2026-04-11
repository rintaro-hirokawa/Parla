"""Domain tests for session composition: select_pattern and compose_blocks.

TDD — these tests define the specification for deterministic session composition.
"""

from uuid import uuid4

import pytest

from parla.domain.errors import InvalidStatusTransition
from parla.domain.session import (
    BlockType,
    SessionConfig,
    SessionMenu,
    SessionPattern,
    SessionState,
    SessionStatus,
    compose_blocks,
    select_next_unlearned_passage,
    select_pattern,
)


class TestSelectPattern:
    """Pattern selection based on pending review count."""

    def test_zero_reviews_returns_new_only(self) -> None:
        config = SessionConfig()
        assert select_pattern(0, config) == SessionPattern.NEW_ONLY

    def test_above_threshold_returns_review_only(self) -> None:
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(31, config) == SessionPattern.REVIEW_ONLY

    def test_at_threshold_returns_review_and_new(self) -> None:
        """At the threshold (not above) → REVIEW_AND_NEW."""
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(30, config) == SessionPattern.REVIEW_AND_NEW

    def test_below_threshold_returns_review_and_new(self) -> None:
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(15, config) == SessionPattern.REVIEW_AND_NEW

    def test_one_review_returns_review_and_new(self) -> None:
        config = SessionConfig()
        assert select_pattern(1, config) == SessionPattern.REVIEW_AND_NEW

    def test_custom_threshold(self) -> None:
        config = SessionConfig(review_overflow_threshold=10)
        assert select_pattern(11, config) == SessionPattern.REVIEW_ONLY
        assert select_pattern(10, config) == SessionPattern.REVIEW_AND_NEW


class TestComposeBlocks:
    """Block composition for each pattern."""

    def _item_ids(self, n: int) -> tuple[str, ...]:
        return tuple(uuid4() for _ in range(n))

    def test_review_and_new_has_three_blocks(self) -> None:
        config = SessionConfig()
        review_ids = self._item_ids(5)
        passage_ids = self._item_ids(2)
        blocks = compose_blocks(
            pattern=SessionPattern.REVIEW_AND_NEW,
            review_item_ids=review_ids,
            passage_ids=passage_ids,
            config=config,
        )
        assert len(blocks) == 3
        assert blocks[0].block_type == BlockType.REVIEW
        assert blocks[0].items == review_ids
        assert blocks[1].block_type == BlockType.NEW_MATERIAL
        assert blocks[1].items == passage_ids
        assert blocks[2].block_type == BlockType.CONSOLIDATION
        assert blocks[2].items == ()

    def test_review_only_has_one_block(self) -> None:
        config = SessionConfig()
        review_ids = self._item_ids(20)
        blocks = compose_blocks(
            pattern=SessionPattern.REVIEW_ONLY,
            review_item_ids=review_ids,
            passage_ids=(),
            config=config,
        )
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.REVIEW
        assert blocks[0].items == review_ids

    def test_new_only_has_two_blocks(self) -> None:
        config = SessionConfig()
        passage_ids = self._item_ids(3)
        blocks = compose_blocks(
            pattern=SessionPattern.NEW_ONLY,
            review_item_ids=(),
            passage_ids=passage_ids,
            config=config,
        )
        assert len(blocks) == 2
        assert blocks[0].block_type == BlockType.NEW_MATERIAL
        assert blocks[0].items == passage_ids
        assert blocks[1].block_type == BlockType.CONSOLIDATION
        assert blocks[1].items == ()

    def test_estimated_time_review(self) -> None:
        config = SessionConfig(estimated_minutes_per_review=2.0)
        review_ids = self._item_ids(10)
        blocks = compose_blocks(
            pattern=SessionPattern.REVIEW_ONLY,
            review_item_ids=review_ids,
            passage_ids=(),
            config=config,
        )
        assert blocks[0].estimated_minutes == 20.0

    def test_estimated_time_new_material(self) -> None:
        config = SessionConfig(estimated_minutes_per_passage=10.0)
        passage_ids = self._item_ids(2)
        blocks = compose_blocks(
            pattern=SessionPattern.NEW_ONLY,
            review_item_ids=(),
            passage_ids=passage_ids,
            config=config,
        )
        assert blocks[0].estimated_minutes == 20.0

    def test_consolidation_block_is_empty_at_composition(self) -> None:
        """Block 3 (consolidation) items are unknown at composition time."""
        config = SessionConfig()
        blocks = compose_blocks(
            pattern=SessionPattern.REVIEW_AND_NEW,
            review_item_ids=self._item_ids(5),
            passage_ids=self._item_ids(1),
            config=config,
        )
        consolidation = blocks[2]
        assert consolidation.block_type == BlockType.CONSOLIDATION
        assert consolidation.items == ()
        assert consolidation.estimated_minutes == 0.0

    def test_empty_review_items_review_and_new(self) -> None:
        """REVIEW_AND_NEW with empty review — review block has 0 items, 0 time."""
        config = SessionConfig()
        blocks = compose_blocks(
            pattern=SessionPattern.REVIEW_AND_NEW,
            review_item_ids=(),
            passage_ids=self._item_ids(1),
            config=config,
        )
        assert blocks[0].block_type == BlockType.REVIEW
        assert blocks[0].items == ()
        assert blocks[0].estimated_minutes == 0.0


class TestSelectNextUnlearnedPassage:
    """select_next_unlearned_passage: first passage not in learned set."""

    def test_returns_first_unlearned(self) -> None:
        ids = [uuid4(), uuid4(), uuid4()]
        result = select_next_unlearned_passage(ids, {ids[0]})
        assert result == ids[1]

    def test_all_learned_returns_none(self) -> None:
        ids = [uuid4(), uuid4()]
        result = select_next_unlearned_passage(ids, set(ids))
        assert result is None

    def test_none_learned_returns_first(self) -> None:
        ids = [uuid4(), uuid4()]
        result = select_next_unlearned_passage(ids, set())
        assert result == ids[0]

    def test_empty_passages_returns_none(self) -> None:
        result = select_next_unlearned_passage([], set())
        assert result is None

    def test_preserves_order(self) -> None:
        ids = [uuid4(), uuid4(), uuid4()]
        result = select_next_unlearned_passage(ids, {ids[0], ids[1]})
        assert result == ids[2]


class TestSessionStateTransitions:
    """SessionState rich entity: state machine transitions following Source pattern."""

    def test_start_creates_in_progress(self) -> None:
        menu_id = uuid4()
        state = SessionState.start(menu_id)
        assert state.menu_id == menu_id
        assert state.status == SessionStatus.IN_PROGRESS
        assert state.started_at is not None

    def test_interrupt_from_in_progress(self) -> None:
        state = SessionState.start(uuid4())
        interrupted = state.interrupt()
        assert interrupted.status == SessionStatus.INTERRUPTED
        assert interrupted.interrupted_at is not None

    def test_interrupt_from_completed_raises(self) -> None:
        state = SessionState.start(uuid4()).complete()
        with pytest.raises(InvalidStatusTransition):
            state.interrupt()

    def test_interrupt_from_interrupted_raises(self) -> None:
        state = SessionState.start(uuid4()).interrupt()
        with pytest.raises(InvalidStatusTransition):
            state.interrupt()

    def test_resume_from_interrupted(self) -> None:
        state = SessionState.start(uuid4()).interrupt()
        resumed = state.resume()
        assert resumed.status == SessionStatus.IN_PROGRESS
        assert resumed.interrupted_at is None

    def test_resume_from_in_progress_raises(self) -> None:
        state = SessionState.start(uuid4())
        with pytest.raises(InvalidStatusTransition):
            state.resume()

    def test_complete_from_in_progress(self) -> None:
        state = SessionState.start(uuid4())
        completed = state.complete()
        assert completed.status == SessionStatus.COMPLETED
        assert completed.completed_at is not None

    def test_complete_from_interrupted_raises(self) -> None:
        state = SessionState.start(uuid4()).interrupt()
        with pytest.raises(InvalidStatusTransition):
            state.complete()

    def test_advance_block_increments(self) -> None:
        state = SessionState.start(uuid4())
        advanced = state.advance_block(total_blocks=3)
        assert advanced.current_block_index == 1
        assert advanced.status == SessionStatus.IN_PROGRESS

    def test_advance_block_completes_at_last(self) -> None:
        state = SessionState.start(uuid4())
        # 1ブロックのセッション → advance で完了
        completed = state.advance_block(total_blocks=1)
        assert completed.status == SessionStatus.COMPLETED
        assert completed.completed_at is not None

    def test_advance_block_from_interrupted_raises(self) -> None:
        state = SessionState.start(uuid4()).interrupt()
        with pytest.raises(InvalidStatusTransition):
            state.advance_block(total_blocks=3)

    def test_transition_returns_new_instance(self) -> None:
        original = SessionState.start(uuid4())
        interrupted = original.interrupt()
        assert original is not interrupted
        assert original.status == SessionStatus.IN_PROGRESS

    def test_frozen_model(self) -> None:
        state = SessionState.start(uuid4())
        with pytest.raises(Exception):  # noqa: B017
            state.status = SessionStatus.COMPLETED  # type: ignore[misc]


class TestSessionMenuConfirm:
    """SessionMenu.confirm() — returns confirmed copy, idempotent."""

    def _make_menu(self) -> SessionMenu:
        from datetime import date

        return SessionMenu(
            target_date=date(2026, 4, 11),
            pattern=SessionPattern.NEW_ONLY,
            blocks=(),
        )

    def test_confirm_returns_confirmed(self) -> None:
        menu = self._make_menu()
        assert menu.confirmed is False
        confirmed = menu.confirm()
        assert confirmed.confirmed is True

    def test_confirm_is_idempotent(self) -> None:
        menu = self._make_menu().confirm()
        again = menu.confirm()
        assert again.confirmed is True
