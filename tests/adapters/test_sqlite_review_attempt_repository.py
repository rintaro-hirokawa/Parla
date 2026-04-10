"""Tests for SQLiteReviewAttemptRepository."""

from uuid import uuid4

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_review_attempt_repository import SQLiteReviewAttemptRepository
from parla.domain.review import ReviewAttempt


def _setup():
    conn = create_connection(":memory:")
    init_schema(conn)
    # Insert required parent rows
    source_id = uuid4()
    conn.execute(
        "INSERT INTO sources (id, title, text, cefr_level, english_variant, status, created_at, updated_at) "
        "VALUES (?, '', ?, 'B1', 'American', 'not_started', '2026-04-10', '2026-04-10')",
        (str(source_id), "a" * 200),
    )
    sentence_id = uuid4()
    passage_id = uuid4()
    conn.execute(
        "INSERT INTO passages (id, source_id, \"order\", topic, passage_type, created_at) "
        "VALUES (?, ?, 0, 'test', '説明型', '2026-04-10')",
        (str(passage_id), str(source_id)),
    )
    conn.execute(
        "INSERT INTO sentences (id, passage_id, \"order\", ja, en, hint1, hint2) "
        "VALUES (?, ?, 0, 'テスト', 'Test', 'hint1', 'hint2')",
        (str(sentence_id), str(passage_id)),
    )
    item_id = uuid4()
    conn.execute(
        "INSERT INTO learning_items (id, pattern, explanation, category, priority, "
        "source_sentence_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(item_id), "test pattern", "test explanation", "文法", 4,
         str(sentence_id), "auto_stocked", "2026-04-10"),
    )
    variation_id = uuid4()
    conn.execute(
        "INSERT INTO variations (id, learning_item_id, source_id, ja, en, hint1, hint2, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(variation_id), str(item_id), str(source_id),
         "テスト", "Test", "h1", "h2", "2026-04-10"),
    )
    conn.commit()
    repo = SQLiteReviewAttemptRepository(conn)
    return repo, variation_id, item_id


class TestSaveAndGet:
    def test_save_and_get_attempt(self) -> None:
        repo, variation_id, item_id = _setup()
        attempt = ReviewAttempt(
            variation_id=variation_id,
            learning_item_id=item_id,
            attempt_number=1,
            correct=True,
            item_used=True,
            hint_level=0,
            timer_ratio=0.5,
        )
        repo.save_attempt(attempt)

        attempts = repo.get_attempts_by_variation(variation_id)
        assert len(attempts) == 1
        assert attempts[0].correct is True
        assert attempts[0].item_used is True
        assert attempts[0].hint_level == 0
        assert attempts[0].timer_ratio == 0.5

    def test_multiple_attempts_ordered(self) -> None:
        repo, variation_id, item_id = _setup()
        for i in range(1, 4):
            repo.save_attempt(ReviewAttempt(
                variation_id=variation_id,
                learning_item_id=item_id,
                attempt_number=i,
                correct=i == 3,
                item_used=i >= 2,
                hint_level=max(0, 2 - i),
                timer_ratio=0.5,
            ))

        attempts = repo.get_attempts_by_variation(variation_id)
        assert len(attempts) == 3
        assert [a.attempt_number for a in attempts] == [1, 2, 3]
        assert attempts[2].correct is True

    def test_empty_variation_returns_empty(self) -> None:
        repo, _, _ = _setup()
        assert repo.get_attempts_by_variation(uuid4()) == []
