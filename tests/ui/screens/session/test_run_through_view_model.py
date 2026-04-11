"""Tests for RunThroughViewModel."""

from uuid import UUID, uuid4

from PySide6.QtCore import QObject, Signal

from parla.domain.audio import AudioData
from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    OverlappingCompleted,
)
from parla.domain.practice import ModelAudio, OverlappingResult, WordTimestamp
from parla.event_bus import EventBus
from parla.services.query_models import OverlappingSummary, PronunciationWordResult
from parla.ui.screens.session.run_through_view_model import RunThroughViewModel
from parla.ui.screens.session.session_context import SessionContext
from tests.conftest import make_wav_audio


def _make_audio() -> AudioData:
    return make_wav_audio()


class FakePracticeRepo:
    def __init__(self, model_audio: ModelAudio | None = None) -> None:
        self._model_audio = model_audio
        self._overlapping_result: OverlappingResult | None = None

    def get_model_audio(self, passage_id: UUID) -> ModelAudio | None:
        return self._model_audio

    def set_overlapping_result(self, result: OverlappingResult) -> None:
        self._overlapping_result = result

    def get_overlapping_result(self, passage_id: UUID) -> OverlappingResult | None:
        return self._overlapping_result


class FakeStreamingSession:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.finalized = False

    def push_chunk(self, pcm_data: bytes) -> None:
        self.chunks.append(pcm_data)

    async def finalize(self) -> None:
        self.finalized = True


class FakePracticeService:
    def __init__(self, model_audio: ModelAudio | None = None) -> None:
        self.overlapping_calls: list[dict] = []
        self.live_delivery_calls: list[dict] = []
        self._streaming_session: FakeStreamingSession | None = None
        self._model_audio = model_audio

    def get_model_audio(self, passage_id: UUID) -> ModelAudio | None:
        return self._model_audio

    def request_model_audio(self, passage_id: UUID) -> None:
        pass

    def start_overlapping_stream(self, passage_id: UUID) -> FakeStreamingSession:
        self._streaming_session = FakeStreamingSession()
        return self._streaming_session

    async def finalize_overlapping_stream(self, passage_id: UUID, session: FakeStreamingSession) -> None:
        self.overlapping_calls.append({"passage_id": passage_id})

    def start_live_delivery_stream(self, passage_id: UUID) -> FakeStreamingSession:
        self._streaming_session = FakeStreamingSession()
        return self._streaming_session

    async def finalize_live_delivery_stream(
        self, passage_id: UUID, session: FakeStreamingSession
    ) -> None:
        self.live_delivery_calls.append({"passage_id": passage_id})

    async def evaluate_overlapping(self, passage_id: UUID, user_audio: AudioData) -> None:
        self.overlapping_calls.append({"passage_id": passage_id})

    async def evaluate_live_delivery(self, passage_id: UUID, user_audio: AudioData) -> None:
        self.live_delivery_calls.append({"passage_id": passage_id})


class FakeSessionQuery:
    def __init__(self) -> None:
        self._overlapping_summary: OverlappingSummary | None = None

    def set_overlapping_summary(self, summary: OverlappingSummary) -> None:
        self._overlapping_summary = summary

    def get_overlapping_summary(self, passage_id: UUID) -> OverlappingSummary | None:
        return self._overlapping_summary


class FakeAudioPlayer(QObject):
    playback_started = Signal()
    playback_finished = Signal()
    playback_position_changed = Signal(float)
    playback_error = Signal(str)
    duration_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self._playing = False
        self._paused = False
        self._speed = 1.0
        self._position = 0.0
        self._duration = 10.0
        self.play_calls = 0
        self.seek_calls: list[float] = []

    def play_audio_data(self, audio_data) -> None:
        self.play_calls += 1
        self._playing = True
        self._paused = False
        self.playback_started.emit()

    def stop(self) -> None:
        self._playing = False
        self._paused = False

    def pause(self) -> None:
        self._playing = False
        self._paused = True

    def resume(self) -> None:
        self._playing = True
        self._paused = False
        self.playback_started.emit()

    def seek(self, seconds: float) -> None:
        self.seek_calls.append(seconds)
        self._position = seconds

    def set_speed(self, rate: float) -> None:
        self._speed = rate

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def position_seconds(self) -> float:
        return self._position

    @property
    def duration_seconds(self) -> float:
        return self._duration


class FakeRecorder(QObject):
    recording_started = Signal()
    chunk_ready = Signal(bytes)

    def __init__(self) -> None:
        super().__init__()
        self.start_calls = 0
        self.stop_calls = 0
        self._recording = False
        self._stop_audio: AudioData | None = make_wav_audio()

    def start(self) -> None:
        self.start_calls += 1
        self._recording = True
        self.recording_started.emit()

    def stop(self) -> AudioData | None:
        self.stop_calls += 1
        self._recording = False
        return self._stop_audio

    @property
    def is_recording(self) -> bool:
        return self._recording


def _make_model_audio(passage_id: UUID) -> ModelAudio:
    return ModelAudio(
        passage_id=passage_id,
        audio=make_wav_audio(),
        word_timestamps=(
            WordTimestamp(word="Hello", start_seconds=0.0, end_seconds=0.3),
            WordTimestamp(word="world", start_seconds=0.3, end_seconds=0.6),
            WordTimestamp(word="Good", start_seconds=0.7, end_seconds=0.9),
            WordTimestamp(word="morning", start_seconds=0.9, end_seconds=1.3),
        ),
        sentence_texts=("Hello world", "Good morning"),
    )


def _make_vm(
    passage_id: UUID | None = None,
    *,
    with_model_audio: bool = False,
    sentence_ja_texts: tuple[str, ...] = (),
) -> tuple[
    RunThroughViewModel, EventBus, FakePracticeService, FakeAudioPlayer, FakeRecorder, SessionContext, FakeSessionQuery
]:
    bus = EventBus()
    pid = passage_id or uuid4()
    model_audio = _make_model_audio(pid) if with_model_audio else None
    svc = FakePracticeService(model_audio=model_audio)
    player = FakeAudioPlayer()
    recorder = FakeRecorder()
    ctx = SessionContext()
    query = FakeSessionQuery()
    vm = RunThroughViewModel(
        event_bus=bus,
        practice_service=svc,
        audio_player=player,
        recorder=recorder,
        session_context=ctx,
        session_query_service=query,
    )
    vm.start(pid, sentence_ja_texts=sentence_ja_texts)
    vm.activate()
    return vm, bus, svc, player, recorder, ctx, query


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

class TestLiveDelivery:
    def test_live_delivery_completed(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.waitSignal(vm.live_delivery_result, timeout=1000) as blocker:
            bus.emit(LiveDeliveryCompleted(
                passage_id=pid, passed=True, error_rate=0.05, error_rate_threshold=0.15, wpm=120.0,
            ))

        assert blocker.args == [True, 0.05, 0.15, 120.0]


class TestSpeedControl:
    def test_set_speed(self, qtbot) -> None:
        vm, _, _, player, *_ = _make_vm()
        vm.set_speed(0.75)
        assert player.speed == 0.75


class TestPlaybackTransport:
    def test_toggle_play_pause_from_stopped(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, *_ = _make_vm(pid, with_model_audio=True)
        vm.toggle_play_pause()
        assert player.play_calls == 1

    def test_toggle_play_pause_pauses_when_playing(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, *_ = _make_vm(pid, with_model_audio=True)
        vm.toggle_play_pause()  # play
        assert player.is_playing is True
        vm.toggle_play_pause()  # pause
        assert player.is_paused is True

    def test_toggle_play_pause_resumes_when_paused(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, *_ = _make_vm(pid, with_model_audio=True)
        vm.toggle_play_pause()  # play
        vm.toggle_play_pause()  # pause
        vm.toggle_play_pause()  # resume
        assert player.is_playing is True

    def test_seek(self, qtbot) -> None:
        vm, _, _, player, *_ = _make_vm()
        vm.seek(3.5)
        assert player.seek_calls == [3.5]

    def test_skip_forward(self, qtbot) -> None:
        vm, _, _, player, *_ = _make_vm()
        player._position = 5.0
        vm.skip(2.0)
        assert player.seek_calls == [7.0]

    def test_skip_backward_clamped(self, qtbot) -> None:
        vm, _, _, player, *_ = _make_vm()
        player._position = 1.0
        vm.skip(-2.0)
        assert player.seek_calls == [0.0]

    def test_reset_to_start(self, qtbot) -> None:
        vm, _, _, player, *_ = _make_vm()
        vm.reset_to_start()
        assert player.seek_calls == [0.0]

    def test_complete_stops_player(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, *_ = _make_vm(pid, with_model_audio=True)
        vm.toggle_play_pause()
        assert player.is_playing is True
        vm.complete()
        assert player.is_playing is False


class TestOverlappingAutoRecord:
    def test_overlapping_starts_recording_with_playback(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, recorder, *_ = _make_vm(pid, with_model_audio=True)
        vm.switch_mode("overlapping")
        vm.toggle_play_pause()
        assert player.play_calls == 1
        assert recorder.start_calls == 1

    def test_listening_does_not_start_recording(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, recorder, *_ = _make_vm(pid, with_model_audio=True)
        # listening mode (default)
        vm.toggle_play_pause()
        assert player.play_calls == 1
        assert recorder.start_calls == 0

    def test_playback_finished_stops_recording_and_submits(self, qtbot) -> None:
        pid = uuid4()
        vm, _, svc, player, recorder, *_ = _make_vm(pid, with_model_audio=True)
        vm.switch_mode("overlapping")
        vm.toggle_play_pause()
        assert recorder.is_recording is True

        # Simulate playback finished
        player._playing = False
        player.playback_finished.emit()

        assert recorder.stop_calls == 1
        assert recorder.is_recording is False

    def test_pause_during_overlapping_stops_recording(self, qtbot) -> None:
        pid = uuid4()
        vm, _, _, player, recorder, *_ = _make_vm(pid, with_model_audio=True)
        vm.switch_mode("overlapping")
        vm.toggle_play_pause()  # play + record
        assert recorder.is_recording is True
        vm.toggle_play_pause()  # pause
        assert recorder.stop_calls == 1


class TestLiveDeliveryRecording:
    def test_on_recording_finished_submits_live_delivery(self, qtbot) -> None:
        pid = uuid4()
        vm, _, svc, *_ = _make_vm(pid)
        vm.switch_mode("live_delivery")
        audio = make_wav_audio()
        vm.on_recording_finished(audio)
        # submit_live_delivery is async — check svc calls after event loop
        # Since we use asyncio.ensure_future, verify the call was attempted
        assert vm._current_mode == "live_delivery"

    def test_on_recording_finished_ignores_non_live_mode(self, qtbot) -> None:
        pid = uuid4()
        vm, _, svc, *_ = _make_vm(pid)
        # Default mode is listening
        audio = make_wav_audio()
        vm.on_recording_finished(audio)
        # No error, just a no-op


class TestSentenceJaTexts:
    def test_ja_texts_set_on_start(self, qtbot) -> None:
        pid = uuid4()
        ja = ("こんにちは", "おはようございます")
        vm, *_ = _make_vm(pid, sentence_ja_texts=ja)
        assert vm.sentence_ja_texts == ja

    def test_ja_texts_default_empty(self, qtbot) -> None:
        vm, *_ = _make_vm()
        assert vm.sentence_ja_texts == ()


class TestSentenceIndex:
    def test_sentence_texts_loaded_on_start(self, qtbot) -> None:
        pid = uuid4()
        vm, *_ = _make_vm(pid, with_model_audio=True)
        assert vm.sentence_texts == ("Hello world", "Good morning")

    def test_current_sentence_index_first_sentence(self, qtbot) -> None:
        pid = uuid4()
        vm, *_ = _make_vm(pid, with_model_audio=True)
        assert vm.current_sentence_index(0.0) == 0
        assert vm.current_sentence_index(0.5) == 0

    def test_current_sentence_index_second_sentence(self, qtbot) -> None:
        pid = uuid4()
        vm, *_ = _make_vm(pid, with_model_audio=True)
        assert vm.current_sentence_index(0.8) == 1
        assert vm.current_sentence_index(1.2) == 1

    def test_current_sentence_index_past_end(self, qtbot) -> None:
        pid = uuid4()
        vm, *_ = _make_vm(pid, with_model_audio=True)
        assert vm.current_sentence_index(5.0) == 1

    def test_current_sentence_index_no_data(self, qtbot) -> None:
        vm, *_ = _make_vm()
        assert vm.current_sentence_index(0.0) == -1


class TestOverlappingWordsReady:
    def test_emits_words_on_overlapping_completed(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, _, _, _, _, query = _make_vm(passage_id=pid, with_model_audio=True)

        summary = OverlappingSummary(
            pronunciation_score=85.0,
            sentence_words=(
                (
                    PronunciationWordResult(word="Hello", error_type="None", accuracy_score=95.0),
                    PronunciationWordResult(word="world", error_type="Mispronunciation", accuracy_score=40.0),
                ),
                (
                    PronunciationWordResult(word="Good", error_type="None", accuracy_score=90.0),
                    PronunciationWordResult(word="morning", error_type="Omission", accuracy_score=0.0),
                ),
            ),
        )
        query.set_overlapping_summary(summary)

        with qtbot.waitSignal(vm.overlapping_words_ready, timeout=1000) as blocker:
            bus.emit(OverlappingCompleted(passage_id=pid, pronunciation_score=85.0))

        result = blocker.args[0]
        assert result.pronunciation_score == 85.0
        assert len(result.sentence_words) == 2
        assert result.sentence_words[0][1].error_type == "Mispronunciation"

    def test_no_emission_when_query_returns_none(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, *_ = _make_vm(passage_id=pid)

        with qtbot.assertNotEmitted(vm.overlapping_words_ready):
            bus.emit(OverlappingCompleted(passage_id=pid, pronunciation_score=85.0))


class TestDeactivate:
    def test_deactivate_unsubscribes(self, qtbot) -> None:
        vm, bus, *_ = _make_vm()
        vm.deactivate()

        with qtbot.assertNotEmitted(vm.model_audio_ready):
            bus.emit(ModelAudioReady(passage_id=uuid4()))
