"""Tests for SQLiteLearningItemRepository."""

from datetime import date
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
        repo.save_items(
            [
                _make_item(sid, pattern="by ~ing", status="auto_stocked"),
                _make_item(sid, pattern="unless ~", status="review_later"),
            ]
        )

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


class TestSRSState:
    """Slice 3: SRS state persistence and due item queries."""

    def test_srs_defaults_on_save(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])

        loaded = repo.get_item(item.id)
        assert loaded is not None
        assert loaded.srs_stage == 0
        assert loaded.ease_factor == 1.0
        assert loaded.next_review_date is None
        assert loaded.correct_context_count == 0

    def test_get_item_by_id(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])

        loaded = repo.get_item(item.id)
        assert loaded is not None
        assert loaded.pattern == item.pattern

    def test_get_item_nonexistent(self) -> None:
        repo, _ = _setup()
        assert repo.get_item(uuid4()) is None

    def test_update_srs_state(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])

        repo.update_srs_state(
            item_id=item.id,
            srs_stage=2,
            ease_factor=1.3,
            next_review_date=date(2026, 4, 15),
            correct_context_count=1,
        )

        loaded = repo.get_item(item.id)
        assert loaded is not None
        assert loaded.srs_stage == 2
        assert loaded.ease_factor == 1.3
        assert loaded.next_review_date == date(2026, 4, 15)
        assert loaded.correct_context_count == 1

    def test_get_due_items_with_null_date(self) -> None:
        """Items with next_review_date=None are immediately due."""
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])

        due = repo.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 1
        assert due[0].id == item.id

    def test_get_due_items_overdue(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])
        repo.update_srs_state(
            item.id,
            srs_stage=1,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 8),
            correct_context_count=0,
        )

        due = repo.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 1

    def test_get_due_items_not_yet_due(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid)
        repo.save_items([item])
        repo.update_srs_state(
            item.id,
            srs_stage=3,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 20),
            correct_context_count=0,
        )

        due = repo.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 0

    def test_get_due_items_excludes_review_later(self) -> None:
        repo, sid = _setup()
        item = _make_item(sid, status="review_later")
        repo.save_items([item])

        due = repo.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 0

    def test_get_due_items_respects_limit(self) -> None:
        repo, sid = _setup()
        for _ in range(5):
            repo.save_items([_make_item(sid)])

        due = repo.get_due_items(as_of=date(2026, 4, 10), limit=3)
        assert len(due) == 3

    def test_get_due_items_ordered_by_most_overdue(self) -> None:
        repo, sid = _setup()
        item1 = _make_item(sid, pattern="old")
        item2 = _make_item(sid, pattern="newer")
        repo.save_items([item1, item2])
        repo.update_srs_state(
            item1.id,
            srs_stage=1,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 5),
            correct_context_count=0,
        )
        repo.update_srs_state(
            item2.id,
            srs_stage=1,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 8),
            correct_context_count=0,
        )

        due = repo.get_due_items(as_of=date(2026, 4, 10))
        assert due[0].pattern == "old"
        assert due[1].pattern == "newer"

    def test_save_item_with_srs_fields(self) -> None:
        repo, sid = _setup()
        item = _make_item(
            sid,
            srs_stage=3,
            ease_factor=1.2,
            next_review_date=date(2026, 5, 1),
            correct_context_count=2,
        )
        repo.save_items([item])

        loaded = repo.get_item(item.id)
        assert loaded is not None
        assert loaded.srs_stage == 3
        assert loaded.ease_factor == 1.2
        assert loaded.next_review_date == date(2026, 5, 1)
        assert loaded.correct_context_count == 2


class TestCountDueItems:
    def test_counts_due_items(self) -> None:
        repo, sid = _setup()
        i1 = _make_item(sid, next_review_date=date(2026, 4, 10))
        i2 = _make_item(sid, next_review_date=date(2026, 4, 9))
        i3 = _make_item(sid, next_review_date=date(2026, 4, 15))
        repo.save_items([i1, i2, i3])

        assert repo.count_due_items(date(2026, 4, 10)) == 2

    def test_counts_zero_when_none_due(self) -> None:
        repo, sid = _setup()
        i = _make_item(sid, next_review_date=date(2026, 4, 15))
        repo.save_items([i])

        assert repo.count_due_items(date(2026, 4, 10)) == 0

    def test_counts_items_with_null_review_date(self) -> None:
        repo, sid = _setup()
        i = _make_item(sid, next_review_date=None)
        repo.save_items([i])

        assert repo.count_due_items(date(2026, 4, 10)) == 1
