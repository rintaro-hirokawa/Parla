"""Port for user settings persistence."""

from typing import Protocol

from parla.domain.user_settings import UserSettings


class UserSettingsRepository(Protocol):
    """Single-user settings persistence (single-row table)."""

    def get(self) -> UserSettings: ...

    def save(self, settings: UserSettings) -> None: ...
