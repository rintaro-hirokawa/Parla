"""Tests for SQLiteLearningItemRepository."""

from uuid import uuid4

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_learning_item_repository import SQLiteLearningItemRepository
from parla.domain.learning_item import LearningItem

# We need a sentence row for FK. Helper inserts minimal parent rows.


def _setup():
    conn = create_connection(":memory:")
    init_schema(conn)
    repo = SQLiteLearningItemRepository(conn)

    # Insert parent rows for FK constraints
    source_id = uuid4()
    conn.execute(
        """INSERT INTO sources (id, title, text, cefr_level, english_variant,
                                status, created_at, updated_at)
           VALUES (?, '', ?, 'B1', 'American', 'not_started', '', '')""",
        (str(source_id), "a" * 200),
    )
    passage_id = uuid4()
    conn.execute(
        """INSERT INTO passages (id, source_id, "order", topic, passage_type, created_at)
           VALUES (?, ?, 0, 'test', '説明型', '')""",
        (str(passage_id), str(source_id)),
    )
    sentence_id = uuid4()
    conn.execute(
        """INSERT INTO sentences (id, passage_id, "order", ja, en, hint1, hint2)
           VALUES (?, ?, 0, 'テスト', 'test', 'h1', 'h2')""",
        (str(sentence_id), str(passage_id)),
    )
    conn.commit()
    return repo, sentence_id


def _make_item(sentence_id, **overrides) -> LearningItem:
    defaults = {
        "pattern": "by ~ing",
        "explanation": "〜することによって",
        "category": "文法",
        "sub_tag": "動名詞",
        "priority": 5,
        "source_sentence_id": sentence_id,
        "status": "auto_stocked",
    }
    defaults.update(overrides)
    return LearningItem(**defaults)


class TestSaveAndRetrieve:
    def test_save_and_get_by_sentence(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])

        items = repo.get_items_by_sentence(sid)
        assert len(items) == 1
        assert items[0].pattern == "by ~ing"
        assert items[0].id == item.id

    def test_save_multiple_items(self) -> None:
        repo, sid = _setup()
        items = [
            _make_item(sid, pattern="by ~ing", priority=5),
            _make_item(sid, pattern="unless ~", priority=4),
        ]
        repo.save_items(items)

        result = repo.get_items_by_sentence(sid)
        assert len(result) == 2

    def test_get_stocked_items(self) -> None:
        repo, sid = _setup()
        repo.save_items([
            _make_item(sid, pattern="by ~ing", status="auto_stocked"),
            _make_item(sid, pattern="unless ~", status="review_later"),
        ])

        stocked = repo.get_stocked_items()
        assert len(stocked) == 1
        assert stocked[0].pattern == "by ~ing"


class TestUpdateStatus:
    def test_update_status(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid, status="auto_stocked")
        repo.save_items([item])

        repo.update_item_status(item.id, "dismissed")

        items = repo.get_items_by_sentence(sid)
        assert items[0].status == "dismissed"


class TestReappearance:
    def test_reappearance_with_matched_id(self) -> None:
        repo, sid = _setup()
        original = _make_item(sid, pattern="keep ~ing")
        repo.save_items([original])

        reappeared = _make_item(
            sid,
            pattern="keep ~ing",
            is_reappearance=True,
            matched_item_id=original.id,
        )
        repo.save_items([reappeared])

        items = repo.get_items_by_sentence(sid)
        reapp = [i for i in items if i.is_reappearance]
        assert len(reapp) == 1
        assert reapp[0].matched_item_id == original.id
