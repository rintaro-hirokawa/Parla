"""Tests for SourceQueryService."""

from collections.abc import Sequence
from uuid import UUID

import pytest

from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.services.source_query_service import SourceQueryService


def _make_source(
    *,
    title: str = "Test Source",
    status: str = "not_started",
    cefr_level: str = "B1",
) -> Source:
    return Source(
        title=title,
        text="x" * 100,
        cefr_level=cefr_level,
        english_variant="American",
        status=status,
    )


def _make_passage(source_id: UUID, *, order: int = 0) -> Passage:
    return Passage(
        source_id=source_id,
        order=order,
        topic="Topic",
        passage_type="dialogue",
        sentences=(
            Sentence(order=0, ja="日本語", en="English", hints=Hint(hint1="h1", hint2="h2")),
        ),
    )


class FakeSourceRepository:
    def __init__(self) -> None:
        self._sources: dict[UUID, Source] = {}
        self._passages: dict[UUID, list[Passage]] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def update_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for p in passages:
            self._passages.setdefault(p.source_id, []).append(p)

    def get_passages_by_source(self, source_id: UUID) -> Sequence[Passage]:
        return self._passages.get(source_id, [])

    def get_passage(self, passage_id: UUID) -> Passage | None:
        for passages in self._passages.values():
            for p in passages:
                if p.id == passage_id:
                    return p
        return None

    def get_active_sources(self) -> Sequence[Source]:
        return [s for s in self._sources.values() if s.status in ("not_started", "in_progress")]

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        return None

    def get_all_sources(self) -> Sequence[Source]:
        return list(self._sources.values())


class FakePracticeRepository:
    def __init__(self) -> None:
        self._achievements: set[UUID] = set()

    def has_achievement(self, passage_id: UUID) -> bool:
        return passage_id in self._achievements

    def add_achievement(self, passage_id: UUID) -> None:
        self._achievements.add(passage_id)


class TestListSources:
    def test_empty(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources()
        assert result == ()

    def test_single_source_no_passages(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        source = _make_source()
        source_repo.save_source(source)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources()
        assert len(result) == 1
        assert result[0].id == source.id
        assert result[0].title == "Test Source"
        assert result[0].passage_count == 0
        assert result[0].learned_passage_count == 0
        assert result[0].progress_ratio == 0.0

    def test_source_with_progress(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        source = _make_source()
        source_repo.save_source(source)
        p1 = _make_passage(source.id, order=0)
        p2 = _make_passage(source.id, order=1)
        p3 = _make_passage(source.id, order=2)
        source_repo.save_passages([p1, p2, p3])
        practice_repo.add_achievement(p1.id)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources()
        assert result[0].passage_count == 3
        assert result[0].learned_passage_count == 1
        assert result[0].progress_ratio == pytest.approx(1 / 3)
        assert result[0].is_completed is False

    def test_completed_source(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        source = _make_source()
        source_repo.save_source(source)
        p1 = _make_passage(source.id, order=0)
        source_repo.save_passages([p1])
        practice_repo.add_achievement(p1.id)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources()
        assert result[0].is_completed is True
        assert result[0].progress_ratio == 1.0


class TestListActiveSources:
    def test_filters_active_only(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        active = _make_source(title="Active", status="not_started")
        completed = _make_source(title="Completed", status="completed")
        source_repo.save_source(active)
        source_repo.save_source(completed)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_active_sources()
        assert len(result) == 1
        assert result[0].id == active.id


class TestFilterSources:
    def test_filter_by_status(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        s1 = _make_source(title="A", status="not_started")
        s2 = _make_source(title="B", status="completed")
        source_repo.save_source(s1)
        source_repo.save_source(s2)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources(status="not_started")
        assert len(result) == 1
        assert result[0].title == "A"

    def test_filter_by_cefr(self) -> None:
        source_repo = FakeSourceRepository()
        practice_repo = FakePracticeRepository()
        s1 = _make_source(title="A", cefr_level="B1")
        s2 = _make_source(title="B", cefr_level="C1")
        source_repo.save_source(s1)
        source_repo.save_source(s2)
        service = SourceQueryService(
            source_repo=source_repo,
            practice_repo=practice_repo,
        )
        result = service.list_sources(cefr_level="C1")
        assert len(result) == 1
        assert result[0].title == "B"
