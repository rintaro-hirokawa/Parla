"""Port for session menu and state persistence."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from parla.domain.session import SessionMenu, SessionState


class SessionRepository(Protocol):
    """Persists session menus and execution state."""

    def save_menu(self, menu: SessionMenu) -> None: ...

    def get_menu(self, menu_id: UUID) -> SessionMenu | None: ...

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        """Get the most recent menu for a given date."""
        ...

    def save_state(self, state: SessionState) -> None: ...

    def get_state(self, session_id: UUID) -> SessionState | None: ...

    def get_active_state(self) -> SessionState | None:
        """Get the current in_progress or interrupted session state."""
        ...

    def get_completed_states(self) -> Sequence[SessionState]:
        """Get all completed session states, ordered by completed_at."""
        ...

    def update_state(self, state: SessionState) -> None: ...
