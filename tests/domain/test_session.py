"""Domain tests for session composition: select_pattern and compose_blocks.

TDD — these tests define the specification for deterministic session composition.
"""

from uuid import uuid4

from parla.domain.session import (
    SessionConfig,
    compose_blocks,
    select_next_unlearned_passage,
    select_pattern,
)


class TestSelectPattern:
    """Pattern selection based on pending review count."""

    def test_zero_reviews_returns_c(self) -> None:
        config = SessionConfig()
        assert select_pattern(0, config) == "c"

    def test_above_threshold_returns_b(self) -> None:
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(31, config) == "b"

    def test_at_threshold_returns_a(self) -> None:
        """At the threshold (not above) → pattern a."""
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(30, config) == "a"

    def test_below_threshold_returns_a(self) -> None:
        config = SessionConfig(review_overflow_threshold=30)
        assert select_pattern(15, config) == "a"

    def test_one_review_returns_a(self) -> None:
        config = SessionConfig()
        assert select_pattern(1, config) == "a"

    def test_custom_threshold(self) -> None:
        config = SessionConfig(review_overflow_threshold=10)
        assert select_pattern(11, config) == "b"
        assert select_pattern(10, config) == "a"


class TestComposeBlocks:
    """Block composition for each pattern."""

    def _item_ids(self, n: int) -> tuple[str, ...]:
        return tuple(uuid4() for _ in range(n))

    def test_pattern_a_has_three_blocks(self) -> None:
        config = SessionConfig()
        review_ids = self._item_ids(5)
        passage_ids = self._item_ids(2)
        blocks = compose_blocks(
            pattern="a",
            review_item_ids=review_ids,
            passage_ids=passage_ids,
            config=config,
        )
        assert len(blocks) == 3
        assert blocks[0].block_type == "review"
        assert blocks[0].items == review_ids
        assert blocks[1].block_type == "new_material"
        assert blocks[1].items == passage_ids
        assert blocks[2].block_type == "consolidation"
        assert blocks[2].items == ()

    def test_pattern_b_has_one_block(self) -> None:
        config = SessionConfig()
        review_ids = self._item_ids(20)
        blocks = compose_blocks(
            pattern="b",
            review_item_ids=review_ids,
            passage_ids=(),
            config=config,
        )
        assert len(blocks) == 1
        assert blocks[0].block_type == "review"
        assert blocks[0].items == review_ids

    def test_pattern_c_has_two_blocks(self) -> None:
        config = SessionConfig()
        passage_ids = self._item_ids(3)
        blocks = compose_blocks(
            pattern="c",
            review_item_ids=(),
            passage_ids=passage_ids,
            config=config,
        )
        assert len(blocks) == 2
        assert blocks[0].block_type == "new_material"
        assert blocks[0].items == passage_ids
        assert blocks[1].block_type == "consolidation"
        assert blocks[1].items == ()

    def test_estimated_time_review(self) -> None:
        config = SessionConfig(estimated_minutes_per_review=2.0)
        review_ids = self._item_ids(10)
        blocks = compose_blocks(
            pattern="b",
            review_item_ids=review_ids,
            passage_ids=(),
            config=config,
        )
        assert blocks[0].estimated_minutes == 20.0

    def test_estimated_time_new_material(self) -> None:
        config = SessionConfig(estimated_minutes_per_passage=10.0)
        passage_ids = self._item_ids(2)
        blocks = compose_blocks(
            pattern="c",
            review_item_ids=(),
            passage_ids=passage_ids,
            config=config,
        )
        assert blocks[0].estimated_minutes == 20.0

    def test_consolidation_block_is_empty_at_composition(self) -> None:
        """Block 3 (consolidation) items are unknown at composition time."""
        config = SessionConfig()
        blocks = compose_blocks(
            pattern="a",
            review_item_ids=self._item_ids(5),
            passage_ids=self._item_ids(1),
            config=config,
        )
        consolidation = blocks[2]
        assert consolidation.block_type == "consolidation"
        assert consolidation.items == ()
        assert consolidation.estimated_minutes == 0.0

    def test_empty_review_items_pattern_a(self) -> None:
        """Pattern a with empty review — review block has 0 items, 0 time."""
        config = SessionConfig()
        blocks = compose_blocks(
            pattern="a",
            review_item_ids=(),
            passage_ids=self._item_ids(1),
            config=config,
        )
        assert blocks[0].block_type == "review"
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
