"""Tests for PhaseCViewModel."""

from uuid import UUID, uuid4

from PySide6.QtCore import QObject, Signal

from parla.domain.audio import AudioData
from tests.conftest import make_wav_audio
from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    OverlappingCompleted,
    OverlappingLagDetected,
)
from parla.event_bus import EventBus
from parla.ui.screens.session.phase_c_view_model import PhaseCViewModel
from parla.ui.screens.session.session_context import SessionContext


def _make_audio() -> AudioData:
    return make_wav_audio()


class FakePracticeRepo:
    def get_model_audio(self, passage_id: UUID):
        return None


class FakePracticeService:
    def __init__(self) -> None:
        self.overlapping_calls: list[dict] = []
        self.live_delivery_calls: list[dict] = []
        self.lag_calls: list[UUID] = []

    async def evaluate_overlapping(self, passage_id: UUID, user_audio: AudioData) -> None:
        self.overlapping_calls.append({"passage_id": passage_id})

    async def detect_lag(self, passage_id: UUID, result) -> None:
        self.lag_calls.append(passage_id)

    async def evaluate_live_delivery(self, passage_id: UUID, user_audio: AudioData, duration_seconds: float) -> None:
        self.live_delivery_calls.append({
            "passage_id": passage_id,
            "duration": duration_seconds,
        })


class FakeAudioPlayer(QObject):
    playback_started = Signal()
    playback_finished = Signal()
    playback_position_changed = Signal(float)
    playback_error = Signal(str)
    duration_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self._playing = False
        self._speed = 1.0
        self.play_calls = 0

    def play_audio_data(self, audio_data) -> None:
        self.play_calls += 1
        self._playing = True
        self.playback_started.emit()

    def stop(self) -> None:
        self._playing = False

    def set_speed(self, rate: float) -> None:
        self._speed = rate

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_playing(self) -> bool:
        return self._playing


def _make_vm(
    passage_id: UUID | None = None,
) -> tuple[PhaseCViewModel, EventBus, FakePracticeService, FakeAudioPlayer, SessionContext]:
    bus = EventBus()
    svc = FakePracticeService()
    repo = FakePracticeRepo()
    player = FakeAudioPlayer()
    ctx = SessionContext()
    vm = PhaseCViewModel(
        event_bus=bus,
        practice_service=svc,
        practice_repo=repo,
        audio_player=player,
        session_context=ctx,
    )
    pid = passage_id or uuid4()
    vm.start(pid)
    vm.activate()
    return vm, bus, svc, player, ctx


class TestModeManagement:
    def test_initial_mode_is_listening(self, qtbot) -> None:
        vm, *_ = _make_vm()
        assert vm.current_mode == "listening"

    def test_switch_mode(self, qtbot) -> None:
        vm, *_ = _make_vm()

        with qtbot.waitSignal(vm.mode_changed, timeout=1000) as blocker:
            vm.switch_mode("overlapping")

        assert blocker.args == ["overlapping"]
        assert vm.current_mode == "overlapping"

    def test_all_modes_available(self, qtbot) -> None:
        vm, *_ = _make_vm()
        assert set(vm.available_modes) == {"listening", "overlapping", "live_delivery"}


class TestModelAudio:
    def test_model_audio_ready(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.model_audio_ready, timeout=1000):
            bus.emit(ModelAudioReady(passage_id=pid))

        assert vm.is_model_audio_loaded is True

    def test_model_audio_failed(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.model_audio_failed, timeout=1000) as blocker:
            bus.emit(ModelAudioFailed(passage_id=pid, error_message="TTS error"))

        assert blocker.args == ["TTS error"]

    def test_ignores_other_passage(self, qtbot) -> None:
        vm, bus, *_ = _make_vm()

        with qtbot.assertNotEmitted(vm.model_audio_ready):
            bus.emit(ModelAudioReady(passage_id=uuid4()))


class TestOverlapping:
    def test_overlapping_completed(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.overlapping_result, timeout=1000) as blocker:
            bus.emit(OverlappingCompleted(passage_id=pid, pronunciation_score=85.0))

        assert blocker.args == [85.0]

    def test_lag_detected(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.lag_detected, timeout=1000) as blocker:
            bus.emit(OverlappingLagDetected(passage_id=pid, lag_count=3))

        assert blocker.args == [3]


class TestLiveDelivery:
    def test_live_delivery_completed(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.live_delivery_result, timeout=1000) as blocker:
            bus.emit(LiveDeliveryCompleted(passage_id=pid, passed=True, wpm=120.0))

        assert blocker.args == [True, 120.0]


class TestSpeedControl:
    def test_set_speed(self, qtbot) -> None:
        vm, _, _, player, _ = _make_vm()
        vm.set_speed(0.75)
        assert player.speed == 0.75


class TestDeactivate:
    def test_deactivate_unsubscribes(self, qtbot) -> None:
        vm, bus, *_ = _make_vm()
        vm.deactivate()

        with qtbot.assertNotEmitted(vm.model_audio_ready):
            bus.emit(ModelAudioReady(passage_id=uuid4()))
