"""Tests for SourceRegistrationView."""

from uuid import uuid4

from parla.domain.source import Source
from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ui.screens.sources.registration_view import SourceRegistrationView
from parla.ui.screens.sources.registration_view_model import SourceRegistrationViewModel


class FakeSettingsService:
    def __init__(self, settings: UserSettings | None = None) -> None:
        self._settings = settings or UserSettings()

    def get_settings(self) -> UserSettings:
        return self._settings


class FakeSourceService:
    def __init__(self) -> None:
        self.register_calls: list[dict] = []

    def register_source(self, text: str, cefr_level: str, english_variant: str, title: str = "") -> Source:
        self.register_calls.append({
            "text": text, "title": title, "cefr_level": cefr_level, "english_variant": english_variant,
        })
        return Source(id=uuid4(), text=text, title=title, cefr_level=cefr_level, english_variant=english_variant)


def _make_view(qtbot, settings: UserSettings | None = None):
    bus = EventBus()
    source_service = FakeSourceService()
    settings_service = FakeSettingsService(settings or UserSettings(cefr_level="B1"))
    vm = SourceRegistrationViewModel(bus, source_service, settings_service)
    view = SourceRegistrationView(vm)
    qtbot.addWidget(view)
    vm.activate()
    vm.load_settings()
    return view, vm, bus, source_service


class TestCefrDisplay:
    def test_shows_current_cefr(self, qtbot) -> None:
        view, *_ = _make_view(qtbot, UserSettings(cefr_level="C1"))
        assert "C1" in view._cefr_label.text()


class TestValidation:
    def test_register_button_disabled_initially(self, qtbot) -> None:
        view, *_ = _make_view(qtbot)
        assert not view._register_button.isEnabled()

    def test_valid_input_enables_button(self, qtbot) -> None:
        view, *_ = _make_view(qtbot)
        view._title_edit.setText("My Title")
        view._text_edit.setPlainText("x" * 100)
        assert view._register_button.isEnabled()

    def test_short_text_disables_button(self, qtbot) -> None:
        view, *_ = _make_view(qtbot)
        view._title_edit.setText("My Title")
        view._text_edit.setPlainText("x" * 50)
        assert not view._register_button.isEnabled()

    def test_char_count_displayed(self, qtbot) -> None:
        view, *_ = _make_view(qtbot)
        view._text_edit.setPlainText("hello")
        assert "5" in view._char_count_label.text()


class TestRegistration:
    def test_register_button_calls_service(self, qtbot) -> None:
        view, vm, bus, source_service = _make_view(qtbot)
        view._title_edit.setText("Test Source")
        view._text_edit.setPlainText("x" * 200)

        view._register_button.click()

        assert len(source_service.register_calls) == 1
        assert source_service.register_calls[0]["title"] == "Test Source"


class TestProgressDisplay:
    def test_progress_message_shown(self, qtbot) -> None:
        view, vm, *_ = _make_view(qtbot)

        vm.generation_progress.emit("パッセージ生成中...")

        assert "生成中" in view._progress_label.text()

    def test_completed_message_shown(self, qtbot) -> None:
        view, vm, *_ = _make_view(qtbot)

        vm.generation_completed.emit(3, 24)

        assert "3" in view._progress_label.text()
        assert "24" in view._progress_label.text()

    def test_error_message_shown(self, qtbot) -> None:
        view, vm, *_ = _make_view(qtbot)

        vm.generation_failed.emit("LLM timeout")

        assert "LLM timeout" in view._progress_label.text()
