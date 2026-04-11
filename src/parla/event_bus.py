"""Simple in-memory event bus with sync/async handler support."""

import asyncio
import contextlib
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from parla.domain.base_event import Event

logger = structlog.get_logger()

# Re-export Event for backward compatibility
__all__ = ["Event", "EventBus", "HandlerEntry", "EventRegistration"]

type _SyncHandler = Callable[..., object]
type _AsyncHandler = Callable[..., Coroutine[Any, Any, None]]


class HandlerEntry(BaseModel, frozen=True):
    """A registered handler with its metadata."""

    name: str
    kind: Literal["sync", "async"]


class EventRegistration(BaseModel, frozen=True):
    """All handlers registered for a single event type."""

    event_name: str
    handlers: tuple[HandlerEntry, ...]


class EventBus:
    """In-memory pub/sub event bus.

    Sync handlers execute immediately and block until done.
    Async handlers are scheduled as asyncio tasks on the running loop.
    """

    def __init__(self) -> None:
        self._sync_handlers: dict[type[Event], list[_SyncHandler]] = defaultdict(list)
        self._async_handlers: dict[type[Event], list[_AsyncHandler]] = defaultdict(list)

    def on_sync[E: Event](self, event_type: type[E]) -> Callable[[Callable[[E], None]], Callable[[E], None]]:
        """Register a synchronous handler. Runs immediately on emit."""

        def decorator(fn: Callable[[E], None]) -> Callable[[E], None]:
            self._sync_handlers[event_type].append(fn)
            return fn

        return decorator

    def on_async[E: Event](
        self, event_type: type[E]
    ) -> Callable[
        [Callable[[E], Coroutine[Any, Any, None]]],
        Callable[[E], Coroutine[Any, Any, None]],
    ]:
        """Register an async handler. Scheduled as asyncio.Task on emit."""

        def decorator(
            fn: Callable[[E], Coroutine[Any, Any, None]],
        ) -> Callable[[E], Coroutine[Any, Any, None]]:
            self._async_handlers[event_type].append(fn)
            return fn

        return decorator

    def off_sync[E: Event](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        """Unregister a synchronous handler."""
        handlers = self._sync_handlers.get(event_type, [])
        with contextlib.suppress(ValueError):
            handlers.remove(handler)
        if not handlers and event_type in self._sync_handlers:
            del self._sync_handlers[event_type]

    def off_async[E: Event](self, event_type: type[E], handler: Callable[[E], Coroutine[Any, Any, None]]) -> None:
        """Unregister an async handler."""
        handlers = self._async_handlers.get(event_type, [])
        with contextlib.suppress(ValueError):
            handlers.remove(handler)
        if not handlers and event_type in self._async_handlers:
            del self._async_handlers[event_type]

    def emit(self, event: Event) -> list[asyncio.Task[None]]:
        """Emit an event. Sync handlers run first, then async tasks are created."""
        event_type = type(event)
        logger.info("event_emitted", event_type=event_type.__name__, payload=str(event))

        for handler in self._sync_handlers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "sync_handler_failed",
                    handler=handler.__qualname__,
                    event_type=event_type.__name__,
                )

        tasks: list[asyncio.Task[None]] = []
        for handler in self._async_handlers.get(event_type, []):
            tasks.append(asyncio.create_task(handler(event)))

        return tasks

    def get_registry(self) -> list[EventRegistration]:
        """Return all registered handlers for startup logging."""
        all_types = set(self._sync_handlers) | set(self._async_handlers)
        registrations: list[EventRegistration] = []
        for et in sorted(all_types, key=lambda t: t.__name__):
            entries = tuple(
                [HandlerEntry(name=h.__qualname__, kind="sync") for h in self._sync_handlers.get(et, [])]
                + [HandlerEntry(name=h.__qualname__, kind="async") for h in self._async_handlers.get(et, [])]
            )
            registrations.append(EventRegistration(event_name=et.__name__, handlers=entries))
        return registrations
