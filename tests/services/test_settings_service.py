"""Tests for SettingsService."""

from parla.domain.events import SettingsChanged
from parla.domain.user_settings import UserSettings
from parla.event_bus import Event, EventBus
from parla.services.settings_service import SettingsService


class InMemorySettingsRepository:
    def __init__(self) -> None:
        self._settings = UserSettings()
        self._saved = False

    def get(self) -> UserSettings:
        return self._settings

    def save(self, settings: UserSettings) -> None:
        self._settings = settings
        self._saved = True

    def exists(self) -> bool:
        return self._saved


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.on_sync(SettingsChanged)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)


class TestGetSettings:
    def test_returns_defaults(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        settings = service.get_settings()
        assert settings.cefr_level == "B1"
        assert settings.english_variant == "American"
        assert settings.phonetic_display is False


class TestUpdateSettings:
    def test_update_cefr_level(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        updated = service.update_settings(cefr_level="C1")
        assert updated.cefr_level == "C1"
        assert updated.english_variant == "American"  # unchanged

    def test_update_english_variant(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        updated = service.update_settings(english_variant="British")
        assert updated.english_variant == "British"

    def test_update_phonetic_display(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        updated = service.update_settings(phonetic_display=True)
        assert updated.phonetic_display is True

    def test_update_multiple_fields(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        updated = service.update_settings(cefr_level="A2", english_variant="Australian")
        assert updated.cefr_level == "A2"
        assert updated.english_variant == "Australian"

    def test_update_persists(self) -> None:
        bus = EventBus()
        repo = InMemorySettingsRepository()
        service = SettingsService(bus, repo)
        service.update_settings(cefr_level="C2")
        assert service.get_settings().cefr_level == "C2"

    def test_no_changes_returns_current(self) -> None:
        bus = EventBus()
        collector = EventCollector(bus)
        service = SettingsService(bus, InMemorySettingsRepository())
        result = service.update_settings()
        assert result.cefr_level == "B1"
        assert len(collector.events) == 0  # no event emitted

    def test_emits_settings_changed(self) -> None:
        bus = EventBus()
        collector = EventCollector(bus)
        service = SettingsService(bus, InMemorySettingsRepository())
        service.update_settings(cefr_level="B2")

        assert len(collector.events) == 1
        event = collector.events[0]
        assert isinstance(event, SettingsChanged)
        assert event.cefr_level == "B2"
        assert event.english_variant == "American"
        assert event.phonetic_display is False

    def test_sequential_updates(self) -> None:
        bus = EventBus()
        service = SettingsService(bus, InMemorySettingsRepository())
        service.update_settings(cefr_level="A1")
        service.update_settings(english_variant="Indian")
        settings = service.get_settings()
        assert settings.cefr_level == "A1"
        assert settings.english_variant == "Indian"
