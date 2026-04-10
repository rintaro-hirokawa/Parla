"""Tests for SQLiteSourceRepository."""

import sqlite3
from uuid import uuid4

import pytest

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = create_connection(":memory:")
    init_schema(c)
    return c


@pytest.fixture
def repo(conn: sqlite3.Connection) -> SQLiteSourceRepository:
    return SQLiteSourceRepository(conn)


def _make_source(**overrides: object) -> Source:
    defaults: dict[str, object] = {
        "text": "a" * 200,
        "cefr_level": "B1",
        "english_variant": "American",
    }
    defaults.update(overrides)
    return Source(**defaults)  # type: ignore[arg-type]


def _make_passage(source_id: object = None, order: int = 0) -> Passage:
    if source_id is None:
        source_id = uuid4()
    return Passage(
        source_id=source_id,  # type: ignore[arg-type]
        order=order,
        topic="Test Topic",
        passage_type="説明型",
        sentences=(
            Sentence(
                order=0,
                ja="テスト",
                en="Test",
                hints=Hint(hint1="Test ...", hint2="主語 + 動詞"),
            ),
            Sentence(
                order=1,
                ja="テスト2",
                en="Test 2",
                hints=Hint(hint1="Test2 ...", hint2="主語 + 動詞(過去形)"),
            ),
        ),
    )


class TestSaveAndGetSource:
    def test_save_and_get(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)
        got = repo.get_source(source.id)
        assert got is not None
        assert got.id == source.id
        assert got.text == source.text
        assert got.cefr_level == source.cefr_level
        assert got.english_variant == source.english_variant
        assert got.status == "registered"

    def test_get_nonexistent_returns_none(self, repo: SQLiteSourceRepository) -> None:
        assert repo.get_source(uuid4()) is None

    def test_save_with_title(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source(title="My Title")
        repo.save_source(source)
        got = repo.get_source(source.id)
        assert got is not None
        assert got.title == "My Title"


class TestUpdateSource:
    def test_update_status(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)

        updated = source.start_generating()
        repo.update_source(updated)

        got = repo.get_source(source.id)
        assert got is not None
        assert got.status == "generating"

    def test_update_preserves_other_fields(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source(title="Original Title")
        repo.save_source(source)

        updated = source.start_generating()
        repo.update_source(updated)

        got = repo.get_source(source.id)
        assert got is not None
        assert got.title == "Original Title"
        assert got.text == source.text


class TestPassagePersistence:
    def test_save_and_get_passages(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)

        p1 = _make_passage(source.id, order=0)
        p2 = _make_passage(source.id, order=1)
        repo.save_passages([p1, p2])

        passages = repo.get_passages_by_source(source.id)
        assert len(passages) == 2

    def test_passages_preserve_sentences_and_hints(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)

        passage = _make_passage(source.id)
        repo.save_passages([passage])

        passages = repo.get_passages_by_source(source.id)
        assert len(passages) == 1
        got = passages[0]
        assert got.id == passage.id
        assert got.topic == "Test Topic"
        assert len(got.sentences) == 2
        s = got.sentences[0]
        assert s.ja == "テスト"
        assert s.en == "Test"
        assert s.hints.hint1 == "Test ..."
        assert s.hints.hint2 == "主語 + 動詞"

    def test_get_passages_for_source_without_passages(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)
        assert repo.get_passages_by_source(source.id) == []

    def test_passages_ordered_by_order(self, repo: SQLiteSourceRepository) -> None:
        source = _make_source()
        repo.save_source(source)

        p2 = _make_passage(source.id, order=2)
        p0 = _make_passage(source.id, order=0)
        p1 = _make_passage(source.id, order=1)
        repo.save_passages([p2, p0, p1])

        passages = repo.get_passages_by_source(source.id)
        orders = [p.order for p in passages]
        assert orders == [0, 1, 2]


class TestGetActiveSources:
    def test_returns_not_started_and_in_progress(self, repo: SQLiteSourceRepository, conn: sqlite3.Connection) -> None:
        s1 = _make_source()
        repo.save_source(s1)
        s1 = s1.start_generating().complete_generation()
        repo.update_source(s1)

        s2 = _make_source()
        repo.save_source(s2)
        s2 = s2.start_generating().complete_generation()
        repo.update_source(s2)
        # Manually set to in_progress via SQL (no domain transition method yet)
        conn.execute("UPDATE sources SET status = 'in_progress' WHERE id = ?", (str(s2.id),))
        conn.commit()

        s3 = _make_source()
        repo.save_source(s3)
        # Keep s3 as registered

        active = repo.get_active_sources()
        active_ids = {s.id for s in active}
        assert s1.id in active_ids
        assert s2.id in active_ids
        assert s3.id not in active_ids

    def test_returns_empty_when_none_active(self, repo: SQLiteSourceRepository) -> None:
        s = _make_source()
        repo.save_source(s)
        assert repo.get_active_sources() == []
