"""Shared test fixtures for items screen tests."""

from datetime import datetime
from uuid import uuid4

from parla.services.query_models import (
    LearningItemDetail,
    LearningItemFilter,
    LearningItemRow,
)


def make_row(**overrides) -> LearningItemRow:
    defaults = {
        "id": uuid4(),
        "pattern": "test pattern",
        "explanation": "test explanation",
        "category": "文法",
        "status": "auto_stocked",
        "srs_stage": 0,
        "source_title": "Test Source",
        "source_sentence_ja": "テスト文",
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return LearningItemRow(**defaults)


def make_detail(**overrides) -> LearningItemDetail:
    defaults = {
        "id": uuid4(),
        "pattern": "present perfect",
        "explanation": "現在完了形",
        "category": "文法",
        "sub_tag": "tense",
        "status": "auto_stocked",
        "srs_stage": 2,
        "ease_factor": 1.3,
        "correct_context_count": 3,
        "source_title": "Test Source",
        "source_sentence_ja": "テスト文",
        "source_sentence_en": "Test sentence",
        "first_utterance": "I have been there",
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return LearningItemDetail(**defaults)


class FakeItemQueryService:
    """Fake for both list and detail query methods."""

    def __init__(self, items=(), detail=None):
        self._items = items
        self._detail = detail
        self.list_calls: list[LearningItemFilter | None] = []
        self.detail_calls: list = []

    def list_items(self, *, filter=None):
        self.list_calls.append(filter)
        return self._items

    def get_item_detail(self, item_id):
        self.detail_calls.append(item_id)
        return self._detail
