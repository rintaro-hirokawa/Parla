"""Tests for SourceListViewModel."""

from datetime import datetime
from uuid import uuid4

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    SourceRegistered,
)
from parla.event_bus import EventBus
from parla.services.query_models import SourceSummary
from parla.ui.screens.sources.list_view_model import SourceListViewModel


def _make_summary(title: str = "Test", status: str = "not_started", cefr: str = "B1") -> SourceSummary:
    return SourceSummary(
        id=uuid4(),
        title=title,
        cefr_level=cefr,
        english_variant="American",
        status=status,
        passage_count=10,
        learned_passage_count=3,
        created_at=datetime(2026, 1, 1),
    )


class FakeSourceQueryService:
    def __init__(self, sources: tuple[SourceSummary, ...] = ()) -> None:
        self._sources = sources
        self.call_count = 0
        self.last_filters: dict = {}

    def list_sources(self, *, status=None, cefr_level=None) -> tuple[SourceSummary, ...]:
        self.call_count += 1
        self.last_filters = {"status": status, "cefr_level": cefr_level}
        return self._sources


class TestLoadSources:
    def test_emits_sources_loaded(self, qtbot) -> None:
        bus = EventBus()
        sources = (_make_summary("Source A"), _make_summary("Source B"))
        query = FakeSourceQueryService(sources)
        vm = SourceListViewModel(bus, query)
        vm.activate()

        with qtbot.waitSignal(vm.sources_loaded, timeout=1000) as blocker:
            vm.load_sources()

        assert blocker.args[0] == sources

    def test_passes_filters(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSourceQueryService()
        vm = SourceListViewModel(bus, query)
        vm.activate()

        vm.load_sources(status="in_progress", cefr_level="C1")

        assert query.last_filters == {"status": "in_progress", "cefr_level": "C1"}


class TestEventDrivenReload:
    def test_source_registered_reloads(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSourceQueryService()
        vm = SourceListViewModel(bus, query)
        vm.activate()
        vm.load_sources()
        assert query.call_count == 1

        bus.emit(SourceRegistered(source_id=uuid4()))
        assert query.call_count == 2

    def test_generation_completed_reloads(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSourceQueryService()
        vm = SourceListViewModel(bus, query)
        vm.activate()
        vm.load_sources()

        bus.emit(PassageGenerationCompleted(source_id=uuid4(), passage_count=3, total_sentences=24))
        assert query.call_count == 2

    def test_generation_failed_reloads(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSourceQueryService()
        vm = SourceListViewModel(bus, query)
        vm.activate()
        vm.load_sources()

        bus.emit(PassageGenerationFailed(source_id=uuid4(), error_message="fail"))
        assert query.call_count == 2

    def test_no_reload_when_inactive(self, qtbot) -> None:
        bus = EventBus()
        query = FakeSourceQueryService()
        SourceListViewModel(bus, query)
        # not activated

        bus.emit(SourceRegistered(source_id=uuid4()))
        assert query.call_count == 0


class TestNavigateToRegistration:
    def test_emits_signal(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceListViewModel(bus, FakeSourceQueryService())

        with qtbot.waitSignal(vm.navigate_to_registration, timeout=1000):
            vm.open_registration()
