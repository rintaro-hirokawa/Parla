"""Tests for SettingsViewModel."""

from parla.domain.events import SettingsChanged
from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ui.screens.settings.view_model import SettingsViewModel


class FakeSettingsService:
    def __init__(self, settings: UserSettings | None = None) -> None:
        self._settings = settings or UserSettings()
        self.update_calls: list[dict] = []

    def get_settings(self) -> UserSettings:
        return self._settings

    def update_settings(
        self,
        *,
        cefr_level: str | None = None,
        english_variant: str | None = None,
    ) -> UserSettings:
        call: dict = {}
        if cefr_level is not None:
            call["cefr_level"] = cefr_level
        if english_variant is not None:
            call["english_variant"] = english_variant
        self.update_calls.append(call)

        updates = {k: v for k, v in call.items()}
        self._settings = self._settings.model_copy(update=updates)
        return self._settings


class TestLoadSettings:
    def test_emits_settings_loaded(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService(UserSettings(cefr_level="B2", english_variant="British"))
        vm = SettingsViewModel(bus, service)
        vm.activate()

        with qtbot.waitSignal(vm.settings_changed, timeout=1000) as blocker:
            vm.load_settings()

        assert blocker.args == ["B2", "British"]

    def test_state_properties_after_load(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService(UserSettings(cefr_level="A1", english_variant="Australian"))
        vm = SettingsViewModel(bus, service)
        vm.activate()
        vm.load_settings()

        assert vm.cefr_level == "A1"
        assert vm.english_variant == "Australian"


class TestUpdateSettings:
    def test_update_cefr_level(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SettingsViewModel(bus, service)
        vm.activate()
        vm.load_settings()

        vm.update_cefr_level("C1")

        assert len(service.update_calls) == 1
        assert service.update_calls[0] == {"cefr_level": "C1"}

    def test_update_english_variant(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SettingsViewModel(bus, service)
        vm.activate()
        vm.load_settings()

        vm.update_english_variant("Indian")

        assert service.update_calls[0] == {"english_variant": "Indian"}



class TestSettingsChangedEvent:
    def test_event_updates_state_and_emits_signal(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SettingsViewModel(bus, service)
        vm.activate()
        vm.load_settings()

        with qtbot.waitSignal(vm.settings_changed, timeout=1000) as blocker:
            bus.emit(SettingsChanged(cefr_level="C2", english_variant="Canadian"))

        assert blocker.args == ["C2", "Canadian"]
        assert vm.cefr_level == "C2"
        assert vm.english_variant == "Canadian"

    def test_no_signal_when_inactive(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SettingsViewModel(bus, service)
        # not activated

        with qtbot.assertNotEmitted(vm.settings_changed):
            bus.emit(SettingsChanged(cefr_level="C2", english_variant="Canadian"))


class TestNavigateToSources:
    def test_open_sources_emits_signal(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SettingsViewModel(bus, service)

        with qtbot.waitSignal(vm.navigate_to_sources, timeout=1000):
            vm.open_sources()
