"""Tests for DetailViewModel (SCREEN-C3)."""

from datetime import date
from uuid import uuid4

from parla.domain.events import SRSUpdated
from parla.event_bus import EventBus
from parla.ui.screens.items.detail_view_model import DetailViewModel
from tests.ui.screens.items.conftest import FakeItemQueryService, make_detail


class TestLoadDetail:
    def test_load_detail_emits_detail_loaded(self, qtbot) -> None:
        detail = make_detail()
        service = FakeItemQueryService(detail=detail)
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.detail_loaded, timeout=1000) as blocker:
            vm.load_detail(detail.id)

        assert blocker.args == [detail]
        assert vm.detail is detail

    def test_load_detail_emits_not_found(self, qtbot) -> None:
        service = FakeItemQueryService(detail=None)
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.detail_not_found, timeout=1000):
            vm.load_detail(uuid4())

        assert vm.detail is None


class TestNavigation:
    def test_go_back_emits_navigate_back(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.navigate_back, timeout=1000):
            vm.go_back()


class TestEventHandling:
    def test_srs_updated_reloads_matching_item(self, qtbot) -> None:
        item_id = uuid4()
        detail = make_detail(id=item_id)
        service = FakeItemQueryService(detail=detail)
        bus = EventBus()
        vm = DetailViewModel(bus, service)
        vm.activate()
        vm.load_detail(item_id)

        service.detail_calls.clear()
        bus.emit(SRSUpdated(
            learning_item_id=item_id,
            old_stage=2, new_stage=3,
            next_review_date=date(2026, 5, 1),
        ))

        assert len(service.detail_calls) == 1
        assert service.detail_calls[0] == item_id

    def test_srs_updated_ignores_different_item(self, qtbot) -> None:
        item_id = uuid4()
        detail = make_detail(id=item_id)
        service = FakeItemQueryService(detail=detail)
        bus = EventBus()
        vm = DetailViewModel(bus, service)
        vm.activate()
        vm.load_detail(item_id)

        service.detail_calls.clear()
        bus.emit(SRSUpdated(
            learning_item_id=uuid4(),
            old_stage=0, new_stage=1,
            next_review_date=date(2026, 5, 1),
        ))

        assert len(service.detail_calls) == 0
