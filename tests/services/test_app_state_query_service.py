"""Tests for AppStateQueryService."""

from datetime import date, datetime

from parla.domain.session import SessionMenu, SessionState
from parla.domain.user_settings import UserSettings
from parla.services.app_state_query_service import AppStateQueryService


class FakeUserSettingsRepository:
    def __init__(self, *, empty: bool = False) -> None:
        self._exists = not empty
        self._settings = UserSettings()

    def get(self) -> UserSettings:
        return self._settings

    def save(self, settings: UserSettings) -> None:
        self._settings = settings
        self._exists = True

    def exists(self) -> bool:
        return self._exists


class FakeSessionRepository:
    def __init__(self) -> None:
        self._menus: dict[str, SessionMenu] = {}
        self._states: dict[str, SessionState] = {}
        self._active_state: SessionState | None = None

    def save_menu(self, menu: SessionMenu) -> None:
        self._menus[str(menu.id)] = menu
        self._menus[f"date:{menu.target_date.isoformat()}"] = menu

    def get_menu(self, menu_id: object) -> SessionMenu | None:
        return self._menus.get(str(menu_id))

    def get_menu_for_date(self, target_date: date) -> SessionMenu | None:
        return self._menus.get(f"date:{target_date.isoformat()}")

    def save_state(self, state: SessionState) -> None:
        self._states[str(state.id)] = state
        if state.status in ("in_progress", "interrupted"):
            self._active_state = state

    def get_state(self, session_id: object) -> SessionState | None:
        return self._states.get(str(session_id))

    def get_active_state(self) -> SessionState | None:
        return self._active_state

    def update_state(self, state: SessionState) -> None:
        self._states[str(state.id)] = state
        if state.status in ("in_progress", "interrupted"):
            self._active_state = state
        elif self._active_state and str(self._active_state.id) == str(state.id):
            self._active_state = None


class TestFirstLaunch:
    def test_needs_setup_when_no_settings(self) -> None:
        settings_repo = FakeUserSettingsRepository(empty=True)
        session_repo = FakeSessionRepository()
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.needs_setup is True
        assert state.has_resumable_session is False
        assert state.has_today_menu is False

    def test_no_setup_needed_when_settings_exist(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.needs_setup is False


class TestResumableSession:
    def test_has_resumable_session(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        menu = SessionMenu(
            target_date=date(2026, 4, 10),
            pattern="a",
            blocks=(),
            confirmed=True,
        )
        session_repo.save_menu(menu)
        session_state = SessionState(
            menu_id=menu.id,
            status="interrupted",
            started_at=datetime(2026, 4, 10, 9, 0),
            interrupted_at=datetime(2026, 4, 10, 9, 30),
        )
        session_repo.save_state(session_state)
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.has_resumable_session is True
        assert state.resumable_session_id == session_state.id

    def test_no_resumable_session_when_completed(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.has_resumable_session is False
        assert state.resumable_session_id is None


class TestTodayMenu:
    def test_has_today_menu_confirmed(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        menu = SessionMenu(
            target_date=date(2026, 4, 10),
            pattern="a",
            blocks=(),
            confirmed=True,
        )
        session_repo.save_menu(menu)
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.has_today_menu is True
        assert state.today_menu_confirmed is True

    def test_has_today_menu_unconfirmed(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        menu = SessionMenu(
            target_date=date(2026, 4, 10),
            pattern="a",
            blocks=(),
            confirmed=False,
        )
        session_repo.save_menu(menu)
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.has_today_menu is True
        assert state.today_menu_confirmed is False

    def test_no_today_menu(self) -> None:
        settings_repo = FakeUserSettingsRepository()
        session_repo = FakeSessionRepository()
        service = AppStateQueryService(
            settings_repo=settings_repo,
            session_repo=session_repo,
        )
        state = service.get_bootstrap_state(today=date(2026, 4, 10))
        assert state.has_today_menu is False
        assert state.today_menu_confirmed is False
