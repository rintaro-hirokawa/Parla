"""Tests for LearningItem domain model."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from parla.domain.learning_item import (
    LearningItem,
    RawItemData,
    create_learning_items_from_raw,
    status_from_priority,
)


class TestStatusFromPriority:
    """priority → status mapping (V2 verification recommendations)."""

    def test_priority_5_maps_to_auto_stocked(self) -> None:
        assert status_from_priority(5) == "auto_stocked"

    def test_priority_4_maps_to_auto_stocked(self) -> None:
        assert status_from_priority(4) == "auto_stocked"

    def test_priority_3_maps_to_review_later(self) -> None:
        assert status_from_priority(3) == "review_later"

    def test_priority_2_maps_to_review_later(self) -> None:
        assert status_from_priority(2) == "review_later"


class TestLearningItemCreation:
    """LearningItem entity creation and validation."""

    def _make_item(self, **overrides) -> LearningItem:
        defaults = {
            "id": uuid4(),
            "pattern": "by ~ing",
            "explanation": "「〜することによって」を表すパターン。例: by studying hard",
            "category": "文法",
            "sub_tag": "動名詞",
            "priority": 5,
            "source_sentence_id": uuid4(),
            "is_reappearance": False,
            "matched_item_id": None,
            "status": "auto_stocked",
        }
        defaults.update(overrides)
        return LearningItem(**defaults)

    def test_create_valid_item(self) -> None:
        item = self._make_item()
        assert item.pattern == "by ~ing"
        assert item.category == "文法"
        assert item.sub_tag == "動名詞"
        assert item.priority == 5
        assert item.status == "auto_stocked"

    def test_all_valid_categories(self) -> None:
        for cat in ("文法", "語彙", "コロケーション", "構文", "表現"):
            item = self._make_item(category=cat)
            assert item.category == cat

    def test_invalid_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_item(category="無効なカテゴリ")

    def test_priority_range_2_to_5(self) -> None:
        for p in (2, 3, 4, 5):
            item = self._make_item(priority=p)
            assert item.priority == p

    def test_priority_below_2_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_item(priority=1)

    def test_priority_above_5_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_item(priority=6)

    def test_all_valid_statuses(self) -> None:
        for s in ("auto_stocked", "review_later", "dismissed"):
            item = self._make_item(status=s)
            assert item.status == s

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_item(status="invalid")

    def test_reappearance_with_matched_id(self) -> None:
        matched_id = uuid4()
        item = self._make_item(
            is_reappearance=True,
            matched_item_id=matched_id,
        )
        assert item.is_reappearance is True
        assert item.matched_item_id == matched_id

    def test_empty_sub_tag_allowed(self) -> None:
        item = self._make_item(category="コロケーション", sub_tag="")
        assert item.sub_tag == ""


class TestCreateLearningItemsFromRaw:
    """create_learning_items_from_raw: domain factory for LLM-extracted items."""

    def _make_raw(self, **overrides: object) -> RawItemData:
        defaults: dict[str, object] = {
            "pattern": "by ~ing",
            "explanation": "〜することによって",
            "category": "文法",
            "sub_tag": "動名詞",
            "priority": 5,
            "is_reappearance": False,
            "matched_stock_item_id": None,
        }
        defaults.update(overrides)
        return RawItemData(**defaults)

    def test_single_item_high_priority(self) -> None:
        sid = uuid4()
        items = create_learning_items_from_raw([self._make_raw(priority=5)], sid)
        assert len(items) == 1
        assert items[0].status == "auto_stocked"
        assert items[0].source_sentence_id == sid

    def test_low_priority_maps_to_review_later(self) -> None:
        items = create_learning_items_from_raw([self._make_raw(priority=2)], uuid4())
        assert items[0].status == "review_later"

    def test_valid_matched_id_parsed(self) -> None:
        matched = uuid4()
        raw = self._make_raw(matched_stock_item_id=str(matched), is_reappearance=True)
        items = create_learning_items_from_raw([raw], uuid4())
        assert items[0].matched_item_id == matched
        assert items[0].is_reappearance is True

    def test_invalid_matched_id_suppressed(self) -> None:
        raw = self._make_raw(matched_stock_item_id="not-a-uuid")
        items = create_learning_items_from_raw([raw], uuid4())
        assert items[0].matched_item_id is None

    def test_empty_matched_id_is_none(self) -> None:
        raw = self._make_raw(matched_stock_item_id="")
        items = create_learning_items_from_raw([raw], uuid4())
        assert items[0].matched_item_id is None

    def test_empty_input(self) -> None:
        items = create_learning_items_from_raw([], uuid4())
        assert items == []

    def test_multiple_items(self) -> None:
        raws = [self._make_raw(priority=5), self._make_raw(priority=3)]
        items = create_learning_items_from_raw(raws, uuid4())
        assert len(items) == 2
        assert items[0].status == "auto_stocked"
        assert items[1].status == "review_later"
