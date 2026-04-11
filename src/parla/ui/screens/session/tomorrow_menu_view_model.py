"""ViewModel for tomorrow's menu confirmation (SCREEN-F2)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal

from parla.domain.events import (
    BackgroundGenerationCompleted,
    BackgroundGenerationStarted,
    PassageGenerationCompleted,
)
from parla.ui.base_view_model import BaseViewModel

if TYPE_CHECKING:
    from uuid import UUID

    from parla.event_bus import EventBus
    from parla.services.query_models import MenuPreview
    from parla.services.session_query_service import SessionQueryService
    from parla.services.session_service import SessionService
    from parla.ui.screens.session.session_context import SessionContext


class TomorrowMenuViewModel(BaseViewModel):
    """Manages tomorrow's menu preview, source change, and confirmation."""

    preview_loaded = Signal()
    generation_started = Signal(int)  # item_count
    generation_complete = Signal(int, int)  # success_count, failure_count
    confirmed = Signal()
    material_exhausted = Signal()
    navigate_to_source_registration = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        event_bus: EventBus,
        session_service: SessionService,
        session_query_service: SessionQueryService,
        session_context: SessionContext,
    ) -> None:
        super().__init__(event_bus)
        self._session_service = session_service
        self._query = session_query_service
        self._ctx = session_context

        self._menu_id: UUID | None = None
        self._preview: MenuPreview | None = None
        self._has_menu = False

        self._register_sync(BackgroundGenerationStarted, self._on_gen_started)
        self._register_sync(BackgroundGenerationCompleted, self._on_gen_completed)
        self._register_sync(PassageGenerationCompleted, self._on_new_source_ready)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def target_date(self) -> date | None:
        return self._preview.target_date if self._preview else None

    @property
    def total_minutes(self) -> float:
        return self._preview.total_estimated_minutes if self._preview else 0.0

    @property
    def source_title(self) -> str:
        return self._preview.source_title if self._preview else ""

    @property
    def preview(self) -> MenuPreview | None:
        return self._preview

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load(self, menu_id: UUID) -> None:
        self._menu_id = menu_id
        self._has_menu = True
        self._preview = self._query.get_menu_preview(menu_id)
        if self._preview is None:
            self.error.emit("Menu preview not found")
            return
        self.preview_loaded.emit()
        if all(s.remaining_passages == 0 for s in self._preview.active_sources):
            self.material_exhausted.emit()

    def show_no_material(self) -> None:
        """Signal that no menu could be composed due to exhausted material."""
        self._has_menu = False
        self.material_exhausted.emit()

    def change_source(self, new_source_id: UUID) -> None:
        if self._menu_id is None or self._preview is None:
            return
        result = self._session_service.recompose_menu(
            self._menu_id,
            new_source_id,
            self._preview.target_date,
            date.today(),
        )
        if result is None:
            self.material_exhausted.emit()
        else:
            self.load(result.id)

    def go_to_source_registration(self) -> None:
        """Request navigation to source registration screen."""
        self.navigate_to_source_registration.emit()

    def confirm(self) -> None:
        if self._menu_id is None:
            return
        self._session_service.confirm_menu(self._menu_id)
        self.confirmed.emit()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_gen_started(self, event: BackgroundGenerationStarted) -> None:
        if event.menu_id != self._menu_id:
            return
        self.generation_started.emit(event.item_count)

    def _on_gen_completed(self, event: BackgroundGenerationCompleted) -> None:
        if event.menu_id != self._menu_id:
            return
        self.generation_complete.emit(event.success_count, event.failure_count)

    def _on_new_source_ready(self, event: PassageGenerationCompleted) -> None:
        """A new source finished generating — recompose the menu."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        new_menu = self._session_service.compose_menu(tomorrow, event.source_id, today)
        if new_menu is not None:
            self.load(new_menu.id)
