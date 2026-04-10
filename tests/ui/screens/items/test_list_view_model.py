"""Tests for ListViewModel (SCREEN-C2)."""

from datetime import date
from uuid import uuid4

from parla.domain.events import LearningItemStocked, SRSUpdated
from parla.event_bus import EventBus
from parla.ui.screens.items.list_view_model import ListViewModel
from tests.ui.screens.items.conftest import FakeItemQueryService, make_row


class TestLoadItems:
    def test_load_items_emits_signal(self, qtbot) -> None:
        row = make_row()
        service = FakeItemQueryService(items=(row,))
        vm = ListViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.items_loaded, timeout=1000) as blocker:
            vm.load_items()

        assert blocker.args == [(row,)]
        assert vm.items == (row,)

    def test_load_items_empty(self, qtbot) -> None:
        service = FakeItemQueryService(items=())
        vm = ListViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.items_loaded, timeout=1000) as blocker:
            vm.load_items()

        assert blocker.args == [()]
        assert vm.items == ()


class TestFilter:
    def test_apply_filter_passes_filter_to_service(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = ListViewModel(EventBus(), service)

        vm.apply_filter(category="文法", srs_stage=2)

        assert len(service.list_calls) == 1
        f = service.list_calls[0]
        assert f is not None
        assert f.category == "文法"
        assert f.srs_stage == 2
        assert f.status is None
        assert f.source_id is None

    def test_apply_filter_all_none_clears_filter(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = ListViewModel(EventBus(), service)

        vm.apply_filter()

        assert service.list_calls == [None]
        assert vm.current_filter is None

    def test_clear_filter_via_apply(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = ListViewModel(EventBus(), service)

        vm.apply_filter(category="語彙")
        vm.apply_filter()

        assert vm.current_filter is None
        assert service.list_calls[-1] is None


class TestNavigation:
    def test_select_item_emits_navigate(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = ListViewModel(EventBus(), service)
        item_id = uuid4()

        with qtbot.waitSignal(vm.navigate_to_detail, timeout=1000) as blocker:
            vm.select_item(item_id)

        assert blocker.args == [item_id]


class TestEventHandling:
    def test_item_stocked_event_triggers_reload(self, qtbot) -> None:
        row = make_row()
        service = FakeItemQueryService(items=(row,))
        bus = EventBus()
        vm = ListViewModel(bus, service)
        vm.activate()

        service.list_calls.clear()
        bus.emit(LearningItemStocked(
            item_id=uuid4(), pattern="new", is_reappearance=False,
        ))

        assert len(service.list_calls) == 1

    def test_srs_updated_event_triggers_reload(self, qtbot) -> None:
        service = FakeItemQueryService()
        bus = EventBus()
        vm = ListViewModel(bus, service)
        vm.activate()

        service.list_calls.clear()
        bus.emit(SRSUpdated(
            learning_item_id=uuid4(),
            old_stage=0, new_stage=1,
            next_review_date=date(2026, 4, 15),
        ))

        assert len(service.list_calls) == 1

    def test_no_reload_when_inactive(self, qtbot) -> None:
        service = FakeItemQueryService()
        bus = EventBus()
        ListViewModel(bus, service)
        # not activated

        bus.emit(LearningItemStocked(
            item_id=uuid4(), pattern="new", is_reappearance=False,
        ))

        assert len(service.list_calls) == 0
