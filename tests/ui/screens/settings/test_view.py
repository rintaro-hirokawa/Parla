"""Tests for SettingsView."""

from parla.domain.events import SettingsChanged
from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ui.screens.settings.view import SettingsView
from parla.ui.screens.settings.view_model import SettingsViewModel


class FakeSettingsService:
    def __init__(self, settings: UserSettings | None = None) -> None:
        self._settings = settings or UserSettings()
        self.update_calls: list[dict] = []

    def get_settings(self) -> UserSettings:
        return self._settings

    def update_settings(self, **kwargs) -> UserSettings:
        call = {k: v for k, v in kwargs.items() if v is not None}
        self.update_calls.append(call)
        self._settings = self._settings.model_copy(update=call)
        return self._settings


def _make_view(qtbot, settings: UserSettings | None = None):
    bus = EventBus()
    service = FakeSettingsService(settings)
    vm = SettingsViewModel(bus, service)
    view = SettingsView(vm)
    qtbot.addWidget(view)
    vm.activate()
    vm.load_settings()
    return view, vm, bus, service


class TestInitialDisplay:
    def test_cefr_combo_shows_current_level(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, UserSettings(cefr_level="B2"))
        assert view._cefr_combo.currentText() == "B2"

    def test_variant_combo_shows_current_variant(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, UserSettings(english_variant="British"))
        assert view._variant_combo.currentText() == "British"



class TestUserInteraction:
    def test_cefr_change_calls_service(self, qtbot) -> None:
        view, vm, bus, service = _make_view(qtbot)

        # Change combo to "C1"
        idx = view._cefr_combo.findText("C1")
        view._cefr_combo.setCurrentIndex(idx)

        assert len(service.update_calls) == 1
        assert service.update_calls[0] == {"cefr_level": "C1"}

    def test_variant_change_calls_service(self, qtbot) -> None:
        view, vm, bus, service = _make_view(qtbot)

        idx = view._variant_combo.findText("Australian")
        view._variant_combo.setCurrentIndex(idx)

        assert service.update_calls[0] == {"english_variant": "Australian"}

    def test_sources_button_emits_navigate(self, qtbot) -> None:
        view, vm, bus, service = _make_view(qtbot)

        with qtbot.waitSignal(vm.navigate_to_sources, timeout=1000):
            view._sources_button.click()


class TestExternalSettingsChange:
    def test_event_updates_combos(self, qtbot) -> None:
        view, vm, bus, service = _make_view(qtbot)

        bus.emit(SettingsChanged(cefr_level="A2", english_variant="Indian"))

        assert view._cefr_combo.currentText() == "A2"
        assert view._variant_combo.currentText() == "Indian"

    def test_external_update_does_not_trigger_service_call(self, qtbot) -> None:
        view, vm, bus, service = _make_view(qtbot)

        bus.emit(SettingsChanged(cefr_level="A2", english_variant="Indian"))

        # No update_settings calls should be made from the event-driven UI update
        assert len(service.update_calls) == 0
