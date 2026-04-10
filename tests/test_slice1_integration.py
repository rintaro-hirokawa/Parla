"""Slice 1 integration tests: source registration → passage generation.

Verifies the full flow with real SQLite (:memory:), real EventBus wiring,
and a Fake LLM adapter. Ensures all parts connect correctly.

register_source() is tested in unit tests. Here we test the pipeline:
emit(SourceRegistered) → async handler → Fake LLM → SQLite persist.
"""

import json
from pathlib import Path
from uuid import UUID

from parla.adapters.gemini_passage_generation import LLMPassageResult, convert_to_domain
from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    PassageGenerationStarted,
    SourceRegistered,
)
from parla.domain.passage import Passage
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.services.source_service import SourceService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture_passages(source_id: UUID) -> list[Passage]:
    """Load V1 verification result and convert to domain Passages."""
    with (FIXTURES_DIR / "passage_generation_response.json").open(encoding="utf-8") as f:
        raw = json.load(f)
    result = LLMPassageResult.model_validate(raw)
    return convert_to_domain(result, source_id)


class FakeLLMPassageGenerator:
    """Returns real V1 verification data as fixture."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def generate(
        self,
        source_id: UUID,
        source_text: str,
        cefr_level: str,
        english_variant: str,
    ) -> list[Passage]:
        if self._fail:
            msg = "Simulated LLM API error"
            raise RuntimeError(msg)
        return _load_fixture_passages(source_id)


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.on_sync(SourceRegistered)(self._collect)
        bus.on_sync(PassageGenerationStarted)(self._collect)
        bus.on_sync(PassageGenerationCompleted)(self._collect)
        bus.on_sync(PassageGenerationFailed)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[type[Event]]:
        return [type(e) for e in self.events]


def _make_source() -> Source:
    return Source(text="a" * 200, cefr_level="B1", english_variant="American")


def _setup(
    *,
    fail: bool = False,
) -> tuple[SourceService, SQLiteSourceRepository, EventBus, EventCollector]:
    """Wire the full system: real SQLite + real EventBus + Fake LLM."""
    bus = EventBus()
    conn = create_connection(":memory:")
    init_schema(conn)
    repo = SQLiteSourceRepository(conn)
    generator = FakeLLMPassageGenerator(fail=fail)
    service = SourceService(bus, repo, generator)

    # Production wiring
    bus.on_async(SourceRegistered)(service.handle_source_registered)

    collector = EventCollector(bus)
    return service, repo, bus, collector


class TestSlice1HappyPath:
    """Full flow: emit(SourceRegistered) → handler → Fake LLM → SQLite."""

    async def test_source_reaches_not_started_status(self) -> None:
        _, repo, bus, _ = _setup()
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        updated = repo.get_source(source.id)
        assert updated is not None
        assert updated.status == "not_started"

    async def test_passages_persisted_to_sqlite(self) -> None:
        _, repo, bus, _ = _setup()
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        passages = repo.get_passages_by_source(source.id)
        assert len(passages) == 6  # V1 fixture has 6 passages

    async def test_sentences_and_hints_round_trip_through_sqlite(self) -> None:
        _, repo, bus, _ = _setup()
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        passages = repo.get_passages_by_source(source.id)
        first = passages[0]

        assert first.source_id == source.id
        assert first.order == 0
        assert first.topic != ""
        assert first.passage_type == "説明型"

        assert len(first.sentences) >= 7
        s = first.sentences[0]
        assert s.order == 0
        assert s.ja != ""
        assert s.en != ""
        assert s.hints.hint1 != ""
        assert s.hints.hint2 != ""

    async def test_event_sequence(self) -> None:
        _, repo, bus, collector = _setup()
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        assert collector.types() == [
            SourceRegistered,
            PassageGenerationStarted,
            PassageGenerationCompleted,
        ]

    async def test_completed_event_has_correct_counts(self) -> None:
        _, repo, bus, collector = _setup()
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        completed = [e for e in collector.events if isinstance(e, PassageGenerationCompleted)]
        assert len(completed) == 1
        assert completed[0].passage_count == 6
        assert completed[0].total_sentences == 47


class TestSlice1ErrorPath:
    """LLM failure: emit → handler → fail → status update."""

    async def test_source_reaches_generation_failed_status(self) -> None:
        _, repo, bus, _ = _setup(fail=True)
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        updated = repo.get_source(source.id)
        assert updated is not None
        assert updated.status == "generation_failed"

    async def test_no_passages_persisted_on_failure(self) -> None:
        _, repo, bus, _ = _setup(fail=True)
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        passages = repo.get_passages_by_source(source.id)
        assert passages == []

    async def test_error_event_sequence(self) -> None:
        _, repo, bus, collector = _setup(fail=True)
        source = _make_source()
        repo.save_source(source)

        tasks = bus.emit(SourceRegistered(source_id=source.id))
        await tasks[0]

        assert collector.types() == [
            SourceRegistered,
            PassageGenerationStarted,
            PassageGenerationFailed,
        ]
