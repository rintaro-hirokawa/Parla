"""Tests for SQLiteVariationRepository."""

from uuid import uuid4

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_variation_repository import SQLiteVariationRepository
from parla.domain.variation import Variation


def _setup():
    conn = create_connection(":memory:")
    init_schema(conn)
    # Insert required parent rows for foreign keys
    source_id = uuid4()
    conn.execute(
        "INSERT INTO sources (id, title, text, cefr_level, english_variant, status, created_at, updated_at) "
        "VALUES (?, '', ?, 'B1', 'American', 'not_started', '2026-04-10', '2026-04-10')",
        (str(source_id), "a" * 200),
    )
    sentence_id = uuid4()
    passage_id = uuid4()
    conn.execute(
        'INSERT INTO passages (id, source_id, "order", topic, passage_type, created_at) '
        "VALUES (?, ?, 0, 'test', '説明型', '2026-04-10')",
        (str(passage_id), str(source_id)),
    )
    conn.execute(
        'INSERT INTO sentences (id, passage_id, "order", ja, en, hint1, hint2) '
        "VALUES (?, ?, 0, 'テスト', 'Test', 'hint1', 'hint2')",
        (str(sentence_id), str(passage_id)),
    )
    item_id = uuid4()
    conn.execute(
        "INSERT INTO learning_items (id, pattern, explanation, category, priority, "
        "source_sentence_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(item_id), "test pattern", "test explanation", "文法", 4, str(sentence_id), "auto_stocked", "2026-04-10"),
    )
    conn.commit()
    repo = SQLiteVariationRepository(conn)
    return repo, item_id, source_id


class TestSaveAndGet:
    def test_save_and_get_variation(self) -> None:
        repo, item_id, source_id = _setup()
        variation = Variation(
            learning_item_id=item_id,
            source_id=source_id,
            ja="テスト日本語",
            en="Test English",
            hint1="Test ... hint",
            hint2="主語 + 動詞",
        )
        repo.save_variation(variation)

        loaded = repo.get_variation(variation.id)
        assert loaded is not None
        assert loaded.ja == "テスト日本語"
        assert loaded.en == "Test English"
        assert loaded.hint1 == "Test ... hint"
        assert loaded.hint2 == "主語 + 動詞"
        assert loaded.learning_item_id == item_id
        assert loaded.source_id == source_id

    def test_get_nonexistent_returns_none(self) -> None:
        repo, _, _ = _setup()
        assert repo.get_variation(uuid4()) is None

    def test_get_variations_by_item(self) -> None:
        repo, item_id, source_id = _setup()
        v1 = Variation(
            learning_item_id=item_id,
            source_id=source_id,
            ja="問題1",
            en="Question 1",
            hint1="h1",
            hint2="h2",
        )
        v2 = Variation(
            learning_item_id=item_id,
            source_id=source_id,
            ja="問題2",
            en="Question 2",
            hint1="h1",
            hint2="h2",
        )
        repo.save_variation(v1)
        repo.save_variation(v2)

        variations = repo.get_variations_by_item(item_id)
        assert len(variations) == 2

    def test_get_variations_by_item_empty(self) -> None:
        repo, _, _ = _setup()
        assert repo.get_variations_by_item(uuid4()) == []
