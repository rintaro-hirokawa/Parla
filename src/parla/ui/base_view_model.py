"""Base class for all ViewModels in the UI layer."""

from collections.abc import Callable

from PySide6.QtCore import QObject

from parla.event_bus import Event, EventBus


class BaseViewModel(QObject):
    """ViewModel base with EventBus lifecycle management.

    Subclasses call ``_register_sync(EventType, handler)`` in ``__init__``
    to declare which events they handle.  Handlers are only active between
    ``activate()`` and ``deactivate()`` calls.
    """

    def __init__(self, event_bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._active = False
        self._sync_registrations: list[tuple[type[Event], Callable[..., None]]] = []

    def _register_sync(self, event_type: type[Event], handler: Callable[..., None]) -> None:
        """Declare a sync event handler. Must be called in ``__init__``."""
        self._sync_registrations.append((event_type, handler))

    def activate(self) -> None:
        """Register all declared handlers with the EventBus. Idempotent."""
        if self._active:
            return
        self._active = True
        for event_type, handler in self._sync_registrations:
            self._event_bus.on_sync(event_type)(handler)

    def deactivate(self) -> None:
        """Unregister all handlers from the EventBus. Idempotent."""
        if not self._active:
            return
        self._active = False
        for event_type, handler in self._sync_registrations:
            self._event_bus.off_sync(event_type, handler)

    @property
    def is_active(self) -> bool:
        """Whether this ViewModel is currently receiving events."""
        return self._active
