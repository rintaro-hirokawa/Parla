"""Tests for SetupView."""

from parla.event_bus import EventBus
from parla.ui.screens.setup.view import SetupView
from parla.ui.screens.setup.view_model import SetupViewModel


class FakeSettingsService:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []

    def update_settings(self, **kwargs):
        call = {k: v for k, v in kwargs.items() if v is not None}
        self.update_calls.append(call)


def _make_view(qtbot):
    bus = EventBus()
    service = FakeSettingsService()
    vm = SetupViewModel(bus, service)
    view = SetupView(vm)
    qtbot.addWidget(view)
    return view, vm, service


class TestCefrSelection:
    def test_default_selection_is_b1(self, qtbot) -> None:
        view, vm, _ = _make_view(qtbot)
        assert vm.selected_cefr == "B1"

    def test_clicking_cefr_updates_viewmodel(self, qtbot) -> None:
        view, vm, _ = _make_view(qtbot)
        # Select C1 radio (index 4: A1=0, A2=1, B1=2, B2=3, C1=4)
        view._cefr_radios[4].click()
        assert vm.selected_cefr == "C1"


class TestVariantSelection:
    def test_default_variant_is_american(self, qtbot) -> None:
        view, vm, _ = _make_view(qtbot)
        assert view._variant_combo.currentText() == "American"

    def test_changing_variant_updates_viewmodel(self, qtbot) -> None:
        view, vm, _ = _make_view(qtbot)
        idx = view._variant_combo.findText("Indian")
        view._variant_combo.setCurrentIndex(idx)
        assert vm.selected_variant == "Indian"


class TestConfirmButton:
    def test_confirm_calls_service_and_emits_signal(self, qtbot) -> None:
        view, vm, service = _make_view(qtbot)

        view._cefr_radios[5].click()  # C2
        idx = view._variant_combo.findText("British")
        view._variant_combo.setCurrentIndex(idx)

        with qtbot.waitSignal(vm.setup_completed, timeout=1000):
            view._confirm_button.click()

        assert service.update_calls[0] == {"cefr_level": "C2", "english_variant": "British"}
