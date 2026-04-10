"""Application startup state query service."""

from datetime import date

from parla.ports.session_repository import SessionRepository
from parla.ports.user_settings_repository import UserSettingsRepository
from parla.services.query_models import BootstrapState


class AppStateQueryService:
    """Read-only service for determining application startup routing."""

    def __init__(
        self,
        *,
        settings_repo: UserSettingsRepository,
        session_repo: SessionRepository,
    ) -> None:
        self._settings_repo = settings_repo
        self._session_repo = session_repo

    def get_bootstrap_state(self, *, today: date) -> BootstrapState:
        """Determine what the app should show on startup."""
        needs_setup = self._check_needs_setup()

        active_state = self._session_repo.get_active_state()
        has_resumable = active_state is not None
        resumable_id = active_state.id if active_state else None

        menu = self._session_repo.get_menu_for_date(today)
        has_today_menu = menu is not None
        today_confirmed = menu.confirmed if menu else False

        return BootstrapState(
            needs_setup=needs_setup,
            has_resumable_session=has_resumable,
            resumable_session_id=resumable_id,
            has_today_menu=has_today_menu,
            today_menu_confirmed=today_confirmed,
        )

    def _check_needs_setup(self) -> bool:
        return not self._settings_repo.exists()
