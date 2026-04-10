"""Tests for SourceListView."""

from datetime import datetime
from uuid import uuid4

from parla.event_bus import EventBus
from parla.services.query_models import SourceSummary
from parla.ui.screens.sources.list_view import SourceListView
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
        self.last_filters: dict = {}

    def list_sources(self, *, status=None, cefr_level=None) -> tuple[SourceSummary, ...]:
        self.last_filters = {"status": status, "cefr_level": cefr_level}
        return self._sources


def _make_view(qtbot, sources: tuple[SourceSummary, ...] = ()):
    bus = EventBus()
    query = FakeSourceQueryService(sources)
    vm = SourceListViewModel(bus, query)
    view = SourceListView(vm)
    qtbot.addWidget(view)
    vm.activate()
    vm.load_sources()
    return view, vm, bus, query


class TestSourceListDisplay:
    def test_shows_sources(self, qtbot) -> None:
        sources = (_make_summary("Alpha"), _make_summary("Beta"))
        view, *_ = _make_view(qtbot, sources)
        assert view._source_list.count() == 2

    def test_empty_list(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, ())
        assert view._source_list.count() == 0


class TestFilterInteraction:
    def test_status_filter_reloads(self, qtbot) -> None:
        view, vm, bus, query = _make_view(qtbot)

        # Change status filter (index 0 = "すべて" = None, index 1+ = actual statuses)
        view._status_filter.setCurrentIndex(1)

        assert query.last_filters["status"] is not None

    def test_cefr_filter_reloads(self, qtbot) -> None:
        view, vm, bus, query = _make_view(qtbot)

        view._cefr_filter.setCurrentIndex(1)  # First actual CEFR level

        assert query.last_filters["cefr_level"] is not None


class TestAddSourceButton:
    def test_emits_navigate(self, qtbot) -> None:
        view, vm, *_ = _make_view(qtbot)

        with qtbot.waitSignal(vm.navigate_to_registration, timeout=1000):
            view._add_button.click()
