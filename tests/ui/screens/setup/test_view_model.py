"""Tests for SetupViewModel."""

from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ui.screens.setup.view_model import SetupViewModel


class FakeSettingsService:
    def __init__(self) -> None:
        self._settings = UserSettings()
        self.update_calls: list[dict] = []

    def get_settings(self) -> UserSettings:
        return self._settings

    def update_settings(self, **kwargs) -> UserSettings:
        call = {k: v for k, v in kwargs.items() if v is not None}
        self.update_calls.append(call)
        self._settings = self._settings.model_copy(update=call)
        return self._settings


class TestSelectCefr:
    def test_select_stores_level(self, qtbot) -> None:
        bus = EventBus()
        vm = SetupViewModel(bus, FakeSettingsService())
        vm.select_cefr("A2")
        assert vm.selected_cefr == "A2"


class TestSelectVariant:
    def test_select_stores_variant(self, qtbot) -> None:
        bus = EventBus()
        vm = SetupViewModel(bus, FakeSettingsService())
        vm.select_variant("British")
        assert vm.selected_variant == "British"


class TestConfirm:
    def test_calls_update_settings(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SetupViewModel(bus, service)
        vm.select_cefr("C1")
        vm.select_variant("Australian")

        vm.confirm()

        assert len(service.update_calls) == 1
        assert service.update_calls[0] == {"cefr_level": "C1", "english_variant": "Australian"}

    def test_emits_setup_completed(self, qtbot) -> None:
        bus = EventBus()
        vm = SetupViewModel(bus, FakeSettingsService())
        vm.select_cefr("B2")
        vm.select_variant("American")

        with qtbot.waitSignal(vm.setup_completed, timeout=1000):
            vm.confirm()

    def test_defaults_used_when_not_selected(self, qtbot) -> None:
        bus = EventBus()
        service = FakeSettingsService()
        vm = SetupViewModel(bus, service)

        vm.confirm()

        assert service.update_calls[0] == {"cefr_level": "B1", "english_variant": "American"}
