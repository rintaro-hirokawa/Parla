"""Tests for SourceService."""

from collections.abc import Sequence
from uuid import UUID

import pytest

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    PassageGenerationStarted,
    SourceRegistered,
)
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.services.source_service import SourceService


def _make_test_passage(source_id: UUID) -> Passage:
    return Passage(
        source_id=source_id,
        order=0,
        topic="Test Topic",
        passage_type="説明型",
        sentences=(
            Sentence(
                order=0,
                ja="テスト文",
                en="Test sentence",
                hints=Hint(hint1="Test ...", hint2="主語 + 動詞"),
            ),
        ),
    )


class FakePassageGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        source_id: UUID,
        source_text: str,
        cefr_level: str,
        english_variant: str,
    ) -> list[Passage]:
        self.calls.append(
            {
                "source_id": source_id,
                "source_text": source_text,
                "cefr_level": cefr_level,
                "english_variant": english_variant,
            }
        )
        if self._fail:
            msg = "LLM generation failed"
            raise RuntimeError(msg)
        return [_make_test_passage(source_id)]


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

    def get_passages_by_source(self, source_id: UUID) -> list[Passage]:
        return self._passages.get(source_id, [])


class EventCollector:
    """Collects emitted events via sync handlers for assertions."""

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


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def repo() -> FakeSourceRepository:
    return FakeSourceRepository()


@pytest.fixture
def collector(bus: EventBus) -> EventCollector:
    return EventCollector(bus)


class TestRegisterSource:
    def test_creates_source_with_registered_status(self, bus: EventBus, repo: FakeSourceRepository) -> None:
        service = SourceService(bus, repo, FakePassageGenerator())
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")
        assert source.status == "registered"

    def test_persists_source(self, bus: EventBus, repo: FakeSourceRepository) -> None:
        service = SourceService(bus, repo, FakePassageGenerator())
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")
        assert repo.get_source(source.id) is not None

    def test_emits_source_registered(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        service = SourceService(bus, repo, FakePassageGenerator())
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")
        assert len(collector.events) == 1
        event = collector.events[0]
        assert isinstance(event, SourceRegistered)
        assert event.source_id == source.id


class TestHandleSourceRegistered:
    async def test_successful_generation(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        generator = FakePassageGenerator()
        service = SourceService(bus, repo, generator)
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        updated = repo.get_source(source.id)
        assert updated is not None
        assert updated.status == "not_started"

    async def test_saves_passages(self, bus: EventBus, repo: FakeSourceRepository) -> None:
        generator = FakePassageGenerator()
        service = SourceService(bus, repo, generator)
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        passages = repo.get_passages_by_source(source.id)
        assert len(passages) == 1

    async def test_emits_started_and_completed(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        service = SourceService(bus, repo, FakePassageGenerator())
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        assert PassageGenerationStarted in collector.types()
        assert PassageGenerationCompleted in collector.types()

    async def test_completed_event_has_counts(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        service = SourceService(bus, repo, FakePassageGenerator())
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        completed = [e for e in collector.events if isinstance(e, PassageGenerationCompleted)]
        assert len(completed) == 1
        assert completed[0].passage_count == 1
        assert completed[0].total_sentences == 1

    async def test_failed_generation_sets_status(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        service = SourceService(bus, repo, FakePassageGenerator(fail=True))
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        updated = repo.get_source(source.id)
        assert updated is not None
        assert updated.status == "generation_failed"

    async def test_failed_generation_emits_failed_event(
        self, bus: EventBus, repo: FakeSourceRepository, collector: EventCollector
    ) -> None:
        service = SourceService(bus, repo, FakePassageGenerator(fail=True))
        source = service.register_source(text="a" * 200, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        assert PassageGenerationFailed in collector.types()
        assert PassageGenerationCompleted not in collector.types()

    async def test_passes_correct_args_to_generator(self, bus: EventBus, repo: FakeSourceRepository) -> None:
        generator = FakePassageGenerator()
        service = SourceService(bus, repo, generator)
        text = "a" * 200
        source = service.register_source(text=text, cefr_level="B1", english_variant="American")

        await service.handle_source_registered(SourceRegistered(source_id=source.id))

        assert len(generator.calls) == 1
        call = generator.calls[0]
        assert call["source_id"] == source.id
        assert call["source_text"] == text
        assert call["cefr_level"] == "B1"
        assert call["english_variant"] == "American"
