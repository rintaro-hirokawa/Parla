"""User settings management service."""

from parla.domain.events import SettingsChanged
from parla.domain.source import CEFRLevel, EnglishVariant
from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ports.user_settings_repository import UserSettingsRepository


class SettingsService:
    """Manages application-level user settings."""

    def __init__(
        self,
        event_bus: EventBus,
        settings_repo: UserSettingsRepository,
    ) -> None:
        self._bus = event_bus
        self._repo = settings_repo

    def get_settings(self) -> UserSettings:
        """Get current user settings (creates defaults if none exist)."""
        return self._repo.get()

    def update_settings(
        self,
        *,
        cefr_level: CEFRLevel | None = None,
        english_variant: EnglishVariant | None = None,
    ) -> UserSettings:
        """Update user settings. Only provided fields are changed."""
        current = self._repo.get()
        updates: dict[str, CEFRLevel | EnglishVariant] = {}
        if cefr_level is not None:
            updates["cefr_level"] = cefr_level
        if english_variant is not None:
            updates["english_variant"] = english_variant

        if not updates:
            return current

        updated = current.model_copy(update=updates)
        self._repo.save(updated)

        self._bus.emit(
            SettingsChanged(
                cefr_level=updated.cefr_level,
                english_variant=updated.english_variant,
            )
        )

        return updated
