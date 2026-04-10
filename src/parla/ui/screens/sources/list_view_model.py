"""ViewModel for Source List screen (SCREEN-D2)."""

from PySide6.QtCore import Signal

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    SourceRegistered,
)
from parla.domain.source import CEFRLevel, SourceStatus
from parla.event_bus import EventBus
from parla.services.query_models import SourceSummary
from parla.services.source_query_service import SourceQueryService
from parla.ui.base_view_model import BaseViewModel


class SourceListViewModel(BaseViewModel):
    """Manages source list state with filtering and event-driven updates."""

    sources_loaded = Signal(object)  # tuple[SourceSummary, ...]
    navigate_to_registration = Signal()

    def __init__(self, event_bus: EventBus, source_query_service: SourceQueryService) -> None:
        super().__init__(event_bus)
        self._source_query = source_query_service
        self._sources: tuple[SourceSummary, ...] = ()
        self._current_status: SourceStatus | None = None
        self._current_cefr: CEFRLevel | None = None
        self._register_sync(SourceRegistered, self._on_source_registered)
        self._register_sync(PassageGenerationCompleted, self._on_generation_completed)
        self._register_sync(PassageGenerationFailed, self._on_generation_failed)

    @property
    def sources(self) -> tuple[SourceSummary, ...]:
        return self._sources

    def load_sources(
        self,
        *,
        status: SourceStatus | None = None,
        cefr_level: CEFRLevel | None = None,
    ) -> None:
        """Load sources with optional filters."""
        self._current_status = status
        self._current_cefr = cefr_level
        self._sources = self._source_query.list_sources(status=status, cefr_level=cefr_level)
        self.sources_loaded.emit(self._sources)

    def open_registration(self) -> None:
        """Request navigation to source registration screen."""
        self.navigate_to_registration.emit()

    def _reload(self) -> None:
        self._sources = self._source_query.list_sources(
            status=self._current_status, cefr_level=self._current_cefr
        )
        self.sources_loaded.emit(self._sources)

    def _on_source_registered(self, _event: SourceRegistered) -> None:
        self._reload()

    def _on_generation_completed(self, _event: PassageGenerationCompleted) -> None:
        self._reload()

    def _on_generation_failed(self, _event: PassageGenerationFailed) -> None:
        self._reload()
