"""Tests for TomorrowMenuViewModel."""

from datetime import date
from uuid import uuid4

from parla.domain.events import (
    BackgroundGenerationCompleted,
    BackgroundGenerationStarted,
)
from parla.domain.session import BlockType, SessionPattern
from parla.event_bus import EventBus
from parla.services.query_models import MenuBlockSummary, MenuPreview
from parla.ui.screens.session.session_context import SessionContext
from parla.ui.screens.session.tomorrow_menu_view_model import TomorrowMenuViewModel


def _make_preview() -> MenuPreview:
    return MenuPreview(
        menu_id=uuid4(),
        target_date=date(2026, 4, 11),
        pattern=SessionPattern.REVIEW_AND_NEW,
        blocks=(
            MenuBlockSummary(block_type=BlockType.REVIEW, item_count=10, estimated_minutes=20),
            MenuBlockSummary(block_type=BlockType.NEW_MATERIAL, item_count=1, estimated_minutes=10),
        ),
        total_estimated_minutes=30.0,
        source_title="Test Source",
        pending_review_count=10,
    )


class FakeSessionQueryService:
    def __init__(self, preview: MenuPreview | None = None) -> None:
        self._preview = preview

    def get_menu_preview(self, menu_id):
        return self._preview


class FakeSessionService:
    def __init__(self) -> None:
        self.confirm_calls: list = []
        self.recompose_calls: list = []

    def confirm_menu(self, menu_id) -> None:
        self.confirm_calls.append(menu_id)

    def recompose_menu(self, menu_id, new_source_id, target_date, today):
        self.recompose_calls.append({
            "menu_id": menu_id,
            "new_source_id": new_source_id,
        })


def _make_vm(
    preview: MenuPreview | None = None,
) -> tuple[TomorrowMenuViewModel, EventBus, FakeSessionService, FakeSessionQueryService]:
    bus = EventBus()
    p = preview or _make_preview()
    query = FakeSessionQueryService(p)
    svc = FakeSessionService()
    ctx = SessionContext()
    vm = TomorrowMenuViewModel(
        event_bus=bus,
        session_service=svc,
        session_query_service=query,
        session_context=ctx,
    )
    return vm, bus, svc, query


class TestLoad:
    def test_preview_loaded(self, qtbot) -> None:
        preview = _make_preview()
        vm, *_ = _make_vm(preview)

        with qtbot.waitSignal(vm.preview_loaded, timeout=1000):
            vm.load(preview.menu_id)

        assert vm.target_date == date(2026, 4, 11)
        assert vm.total_minutes == 30.0
        assert vm.source_title == "Test Source"

    def test_load_not_found(self, qtbot) -> None:
        query = FakeSessionQueryService(None)
        bus = EventBus()
        svc = FakeSessionService()
        ctx = SessionContext()
        vm = TomorrowMenuViewModel(
            event_bus=bus,
            session_service=svc,
            session_query_service=query,
            session_context=ctx,
        )

        with qtbot.waitSignal(vm.error, timeout=1000):
            vm.load(uuid4())


class TestConfirm:
    def test_confirm_calls_service(self, qtbot) -> None:
        preview = _make_preview()
        vm, _, svc, _ = _make_vm(preview)
        vm.load(preview.menu_id)

        with qtbot.waitSignal(vm.confirmed, timeout=1000):
            vm.confirm()

        assert len(svc.confirm_calls) == 1


class TestBackgroundGeneration:
    def test_generation_started(self, qtbot) -> None:
        preview = _make_preview()
        vm, bus, *_ = _make_vm(preview)
        vm.load(preview.menu_id)
        vm.activate()

        with qtbot.waitSignal(vm.generation_started, timeout=1000) as blocker:
            bus.emit(BackgroundGenerationStarted(menu_id=preview.menu_id, item_count=5))

        assert blocker.args == [5]

    def test_generation_completed(self, qtbot) -> None:
        preview = _make_preview()
        vm, bus, *_ = _make_vm(preview)
        vm.load(preview.menu_id)
        vm.activate()

        with qtbot.waitSignal(vm.generation_complete, timeout=1000) as blocker:
            bus.emit(BackgroundGenerationCompleted(menu_id=preview.menu_id, success_count=4, failure_count=1))

        assert blocker.args == [4, 1]

    def test_ignores_other_menu(self, qtbot) -> None:
        preview = _make_preview()
        vm, bus, *_ = _make_vm(preview)
        vm.load(preview.menu_id)
        vm.activate()

        with qtbot.assertNotEmitted(vm.generation_started):
            bus.emit(BackgroundGenerationStarted(menu_id=uuid4(), item_count=5))


class TestDeactivate:
    def test_deactivate_unsubscribes(self, qtbot) -> None:
        preview = _make_preview()
        vm, bus, *_ = _make_vm(preview)
        vm.load(preview.menu_id)
        vm.activate()
        vm.deactivate()

        with qtbot.assertNotEmitted(vm.generation_started):
            bus.emit(BackgroundGenerationStarted(menu_id=preview.menu_id, item_count=5))
