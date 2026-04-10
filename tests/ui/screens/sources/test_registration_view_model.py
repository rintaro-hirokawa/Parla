"""Tests for SourceRegistrationViewModel."""

from uuid import UUID, uuid4

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    PassageGenerationStarted,
)
from parla.domain.source import Source
from parla.domain.user_settings import UserSettings
from parla.event_bus import EventBus
from parla.ui.screens.sources.registration_view_model import SourceRegistrationViewModel


class FakeSettingsService:
    def __init__(self, settings: UserSettings | None = None) -> None:
        self._settings = settings or UserSettings()

    def get_settings(self) -> UserSettings:
        return self._settings


class FakeSourceService:
    def __init__(self) -> None:
        self.register_calls: list[dict] = []
        self._last_source_id: UUID | None = None

    def register_source(self, text: str, cefr_level: str, english_variant: str, title: str = "") -> Source:
        self._last_source_id = uuid4()
        self.register_calls.append({
            "text": text,
            "title": title,
            "cefr_level": cefr_level,
            "english_variant": english_variant,
        })
        return Source(
            id=self._last_source_id,
            text=text,
            title=title,
            cefr_level=cefr_level,
            english_variant=english_variant,
        )


class TestLoadCefrLevel:
    def test_emits_cefr_from_settings(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(
            bus,
            FakeSourceService(),
            FakeSettingsService(UserSettings(cefr_level="C1", english_variant="British")),
        )
        vm.activate()

        with qtbot.waitSignal(vm.cefr_level_loaded, timeout=1000) as blocker:
            vm.load_settings()

        assert blocker.args == ["C1"]
        assert vm.cefr_level == "C1"
        assert vm.english_variant == "British"


class TestValidation:
    def test_valid_text_and_title(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(bus, FakeSourceService(), FakeSettingsService())
        vm.activate()

        with qtbot.waitSignal(vm.validation_changed, timeout=1000) as blocker:
            vm.validate("x" * 100, "My Title")

        assert blocker.args[0] is True  # is_valid
        assert blocker.args[1] == ""  # no error

    def test_text_too_short(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(bus, FakeSourceService(), FakeSettingsService())
        vm.activate()

        with qtbot.waitSignal(vm.validation_changed, timeout=1000) as blocker:
            vm.validate("x" * 99, "Title")

        assert blocker.args[0] is False

    def test_text_too_long(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(bus, FakeSourceService(), FakeSettingsService())
        vm.activate()

        with qtbot.waitSignal(vm.validation_changed, timeout=1000) as blocker:
            vm.validate("x" * 50001, "Title")

        assert blocker.args[0] is False

    def test_empty_title(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(bus, FakeSourceService(), FakeSettingsService())
        vm.activate()

        with qtbot.waitSignal(vm.validation_changed, timeout=1000) as blocker:
            vm.validate("x" * 200, "")

        assert blocker.args[0] is False


class TestRegister:
    def test_calls_service(self, qtbot) -> None:
        bus = EventBus()
        source_service = FakeSourceService()
        vm = SourceRegistrationViewModel(
            bus,
            source_service,
            FakeSettingsService(UserSettings(cefr_level="B2", english_variant="Australian")),
        )
        vm.activate()
        vm.load_settings()

        vm.register("x" * 200, "My Source")

        assert len(source_service.register_calls) == 1
        call = source_service.register_calls[0]
        assert call["title"] == "My Source"
        assert call["cefr_level"] == "B2"
        assert call["english_variant"] == "Australian"

    def test_emits_registration_started(self, qtbot) -> None:
        bus = EventBus()
        vm = SourceRegistrationViewModel(bus, FakeSourceService(), FakeSettingsService())
        vm.activate()
        vm.load_settings()

        with qtbot.waitSignal(vm.registration_started, timeout=1000):
            vm.register("x" * 200, "Title")


class TestGenerationEvents:
    def _make_vm_with_source(self, qtbot):
        bus = EventBus()
        source_service = FakeSourceService()
        vm = SourceRegistrationViewModel(bus, source_service, FakeSettingsService())
        vm.activate()
        vm.load_settings()
        vm.register("x" * 200, "Title")
        source_id = source_service._last_source_id
        return vm, bus, source_id

    def test_generation_started_emits_progress(self, qtbot) -> None:
        vm, bus, source_id = self._make_vm_with_source(qtbot)

        with qtbot.waitSignal(vm.generation_progress, timeout=1000):
            bus.emit(PassageGenerationStarted(source_id=source_id))

    def test_generation_completed_emits_signal(self, qtbot) -> None:
        vm, bus, source_id = self._make_vm_with_source(qtbot)

        with qtbot.waitSignal(vm.generation_completed, timeout=1000) as blocker:
            bus.emit(PassageGenerationCompleted(source_id=source_id, passage_count=3, total_sentences=24))

        assert blocker.args == [3, 24]

    def test_generation_failed_emits_signal(self, qtbot) -> None:
        vm, bus, source_id = self._make_vm_with_source(qtbot)

        with qtbot.waitSignal(vm.generation_failed, timeout=1000) as blocker:
            bus.emit(PassageGenerationFailed(source_id=source_id, error_message="LLM timeout"))

        assert blocker.args == ["LLM timeout"]

    def test_ignores_events_for_other_sources(self, qtbot) -> None:
        vm, bus, _ = self._make_vm_with_source(qtbot)
        other_id = uuid4()

        with qtbot.assertNotEmitted(vm.generation_progress):
            bus.emit(PassageGenerationStarted(source_id=other_id))
