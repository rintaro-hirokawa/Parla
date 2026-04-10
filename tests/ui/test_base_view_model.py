"""Tests for BaseViewModel."""

from PySide6.QtCore import Signal

from parla.event_bus import Event, EventBus
from parla.ui.base_view_model import BaseViewModel


class SomeEvent(Event, frozen=True):
    value: int


class OtherEvent(Event, frozen=True):
    message: str


class FakeViewModel(BaseViewModel):
    """Concrete ViewModel for testing."""

    value_changed = Signal(int)

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self.last_value: int | None = None
        self._register_sync(SomeEvent, self._on_some_event)

    def _on_some_event(self, event: SomeEvent) -> None:
        self.last_value = event.value
        self.value_changed.emit(event.value)


class TestActivateDeactivate:
    def test_activate_registers_handler(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)
        vm.activate()
        bus.emit(SomeEvent(value=42))

        assert vm.last_value == 42

    def test_deactivate_unregisters_handler(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        vm.activate()
        bus.emit(SomeEvent(value=1))
        assert vm.last_value == 1

        vm.deactivate()
        bus.emit(SomeEvent(value=2))
        assert vm.last_value == 1  # unchanged

    def test_handler_not_called_before_activate(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        bus.emit(SomeEvent(value=99))
        assert vm.last_value is None

    def test_activate_is_idempotent(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        vm.activate()
        vm.activate()  # second call should be no-op

        received: list[int] = []

        @bus.on_sync(SomeEvent)
        def counter(event: SomeEvent) -> None:
            received.append(event.value)

        bus.emit(SomeEvent(value=10))

        # FakeViewModel handler should fire once, not twice
        assert vm.last_value == 10
        # Check registry: FakeViewModel's handler + counter = 2 sync handlers for SomeEvent
        registry = bus.get_registry()
        some_event_reg = next(r for r in registry if r.event_name == "SomeEvent")
        sync_count = sum(1 for h in some_event_reg.handlers if h.kind == "sync")
        assert sync_count == 2  # vm handler + counter

    def test_deactivate_is_idempotent(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        vm.activate()
        vm.deactivate()
        vm.deactivate()  # should not raise

    def test_is_active_property(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        assert vm.is_active is False
        vm.activate()
        assert vm.is_active is True
        vm.deactivate()
        assert vm.is_active is False


class TestEventReception:
    def test_event_triggers_qt_signal(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        vm.activate()

        with qtbot.waitSignal(vm.value_changed, timeout=1000) as blocker:
            bus.emit(SomeEvent(value=77))

        assert blocker.args == [77]

    def test_no_signal_when_inactive(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        # vm not activated — signal should NOT fire
        with qtbot.assertNotEmitted(vm.value_changed):
            bus.emit(SomeEvent(value=99))

    def test_unrelated_event_does_not_trigger(self, qtbot) -> None:
        bus = EventBus()
        vm = FakeViewModel(bus)

        vm.activate()

        with qtbot.assertNotEmitted(vm.value_changed):
            bus.emit(OtherEvent(message="hello"))

        assert vm.last_value is None
