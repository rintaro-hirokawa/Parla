"""Tests for EventBus."""

import asyncio

import pytest

from parla.event_bus import Event, EventBus


class SampleEvent(Event, frozen=True):
    value: int


class OtherEvent(Event, frozen=True):
    message: str


class TestSyncHandlers:
    def test_sync_handler_receives_event(self) -> None:
        bus = EventBus()
        received: list[SampleEvent] = []

        @bus.on_sync(SampleEvent)
        def handler(event: SampleEvent) -> None:
            received.append(event)

        bus.emit(SampleEvent(value=42))

        assert len(received) == 1
        assert received[0].value == 42

    def test_multiple_sync_handlers_execute_in_order(self) -> None:
        bus = EventBus()
        order: list[str] = []

        @bus.on_sync(SampleEvent)
        def first(event: SampleEvent) -> None:
            order.append("first")

        @bus.on_sync(SampleEvent)
        def second(event: SampleEvent) -> None:
            order.append("second")

        bus.emit(SampleEvent(value=1))

        assert order == ["first", "second"]

    def test_sync_handler_failure_does_not_block_others(self) -> None:
        bus = EventBus()
        received: list[str] = []

        @bus.on_sync(SampleEvent)
        def failing(event: SampleEvent) -> None:
            raise RuntimeError("boom")

        @bus.on_sync(SampleEvent)
        def surviving(event: SampleEvent) -> None:
            received.append("ok")

        bus.emit(SampleEvent(value=1))

        assert received == ["ok"]

    def test_different_event_types_are_independent(self) -> None:
        bus = EventBus()
        sample_received: list[SampleEvent] = []
        other_received: list[OtherEvent] = []

        @bus.on_sync(SampleEvent)
        def on_sample(event: SampleEvent) -> None:
            sample_received.append(event)

        @bus.on_sync(OtherEvent)
        def on_other(event: OtherEvent) -> None:
            other_received.append(event)

        bus.emit(SampleEvent(value=1))

        assert len(sample_received) == 1
        assert len(other_received) == 0


class TestAsyncHandlers:
    @pytest.mark.asyncio
    async def test_async_handler_receives_event(self) -> None:
        bus = EventBus()
        received: list[SampleEvent] = []

        @bus.on_async(SampleEvent)
        async def handler(event: SampleEvent) -> None:
            received.append(event)

        tasks = bus.emit(SampleEvent(value=99))
        await asyncio.gather(*tasks)

        assert len(received) == 1
        assert received[0].value == 99

    @pytest.mark.asyncio
    async def test_emit_returns_tasks(self) -> None:
        bus = EventBus()

        @bus.on_async(SampleEvent)
        async def handler(event: SampleEvent) -> None:
            pass

        tasks = bus.emit(SampleEvent(value=1))

        assert len(tasks) == 1
        assert isinstance(tasks[0], asyncio.Task)
        await asyncio.gather(*tasks)


class TestMixedHandlers:
    @pytest.mark.asyncio
    async def test_sync_runs_before_async(self) -> None:
        bus = EventBus()
        order: list[str] = []

        @bus.on_sync(SampleEvent)
        def sync_handler(event: SampleEvent) -> None:
            order.append("sync")

        @bus.on_async(SampleEvent)
        async def async_handler(event: SampleEvent) -> None:
            order.append("async")

        tasks = bus.emit(SampleEvent(value=1))

        # sync already executed at this point
        assert order == ["sync"]

        await asyncio.gather(*tasks)
        assert order == ["sync", "async"]


class TestEventImmutability:
    def test_event_is_frozen(self) -> None:
        event = SampleEvent(value=42)
        with pytest.raises(Exception):  # noqa: B017
            event.value = 100  # type: ignore[misc]


class TestUnsubscribe:
    def test_off_sync_removes_handler(self) -> None:
        bus = EventBus()
        received: list[SampleEvent] = []

        @bus.on_sync(SampleEvent)
        def handler(event: SampleEvent) -> None:
            received.append(event)

        bus.emit(SampleEvent(value=1))
        assert len(received) == 1

        bus.off_sync(SampleEvent, handler)
        bus.emit(SampleEvent(value=2))
        assert len(received) == 1  # handler was removed, no new event

    def test_off_sync_only_removes_specified_handler(self) -> None:
        bus = EventBus()
        received_a: list[int] = []
        received_b: list[int] = []

        @bus.on_sync(SampleEvent)
        def handler_a(event: SampleEvent) -> None:
            received_a.append(event.value)

        @bus.on_sync(SampleEvent)
        def handler_b(event: SampleEvent) -> None:
            received_b.append(event.value)

        bus.off_sync(SampleEvent, handler_a)
        bus.emit(SampleEvent(value=42))

        assert received_a == []
        assert received_b == [42]

    def test_off_sync_unregistered_handler_is_noop(self) -> None:
        bus = EventBus()

        def not_registered(event: SampleEvent) -> None:
            pass

        # Should not raise
        bus.off_sync(SampleEvent, not_registered)

    @pytest.mark.asyncio
    async def test_off_async_removes_handler(self) -> None:
        bus = EventBus()
        received: list[SampleEvent] = []

        @bus.on_async(SampleEvent)
        async def handler(event: SampleEvent) -> None:
            received.append(event)

        tasks = bus.emit(SampleEvent(value=1))
        await asyncio.gather(*tasks)
        assert len(received) == 1

        bus.off_async(SampleEvent, handler)
        tasks = bus.emit(SampleEvent(value=2))
        await asyncio.gather(*tasks)
        assert len(received) == 1  # handler was removed

    def test_off_async_unregistered_handler_is_noop(self) -> None:
        bus = EventBus()

        async def not_registered(event: SampleEvent) -> None:
            pass

        # Should not raise
        bus.off_async(SampleEvent, not_registered)

    def test_unsubscribed_handler_not_in_registry(self) -> None:
        bus = EventBus()

        @bus.on_sync(SampleEvent)
        def handler(event: SampleEvent) -> None:
            pass

        assert len(bus.get_registry()) == 1

        bus.off_sync(SampleEvent, handler)
        assert bus.get_registry() == []


class TestRegistry:
    def test_get_registry_returns_registered_handlers(self) -> None:
        bus = EventBus()

        @bus.on_sync(SampleEvent)
        def sync_handler(event: SampleEvent) -> None:
            pass

        @bus.on_async(SampleEvent)
        async def async_handler(event: SampleEvent) -> None:
            pass

        registry = bus.get_registry()

        assert len(registry) == 1
        reg = registry[0]
        assert reg.event_name == "SampleEvent"
        assert len(reg.handlers) == 2
        assert reg.handlers[0].kind == "sync"
        assert reg.handlers[1].kind == "async"

    def test_empty_registry(self) -> None:
        bus = EventBus()
        assert bus.get_registry() == []
