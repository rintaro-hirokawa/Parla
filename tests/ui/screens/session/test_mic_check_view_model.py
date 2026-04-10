"""Tests for MicCheckViewModel."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioDevice

from parla.domain.audio import AudioData
from parla.ui.screens.session.mic_check_view_model import MicCheckViewModel

# Threshold used by the ViewModel
_LEVEL_THRESHOLD = 0.05


class FakeAudioRecorder(QObject):
    """Fake matching AudioRecorder's public API."""

    recording_started = Signal()
    recording_stopped = Signal(AudioData)
    level_changed = Signal(float)
    waveform_updated = Signal(list)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._recording = False
        self._devices: list[QAudioDevice] = []
        self._selected: QAudioDevice | None = None

    def available_devices(self) -> list[QAudioDevice]:
        return self._devices

    def select_device(self, device: QAudioDevice) -> None:
        self._selected = device

    def selected_device(self) -> QAudioDevice | None:
        return self._selected

    def start(self) -> None:
        self._recording = True
        self.recording_started.emit()

    def stop(self) -> AudioData | None:
        self._recording = False
        return None

    def cancel(self) -> None:
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording


class TestDeviceListing:
    def test_device_names_returned(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        names = vm.device_names()
        # Real devices from QMediaDevices; just assert no crash
        assert isinstance(names, list)


class TestLevelDetection:
    def test_start_enabled_after_sufficient_level(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        assert vm.is_start_enabled is False

        vm.start_test()

        # Emit level above threshold
        with qtbot.waitSignal(vm.start_enabled_changed, timeout=1000):
            recorder.level_changed.emit(0.1)

        assert vm.is_start_enabled is True

    def test_low_level_does_not_enable(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        vm.start_test()
        recorder.level_changed.emit(0.01)

        assert vm.is_start_enabled is False

    def test_warning_emitted_on_low_level(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        vm.start_test()

        with qtbot.waitSignal(vm.level_warning, timeout=1000):
            recorder.level_changed.emit(0.01)


class TestProceed:
    def test_confirm_emits_proceed(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        vm.start_test()
        recorder.level_changed.emit(0.1)  # enable start

        with qtbot.waitSignal(vm.proceed, timeout=1000):
            vm.confirm_start()

    def test_confirm_stops_test(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        vm.start_test()
        recorder.level_changed.emit(0.1)
        vm.confirm_start()

        assert recorder.is_recording is False

    def test_confirm_not_possible_before_level_ok(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        with qtbot.assertNotEmitted(vm.proceed):
            vm.confirm_start()


class TestError:
    def test_recorder_error_forwarded(self, qtbot) -> None:
        recorder = FakeAudioRecorder()
        vm = MicCheckViewModel(recorder=recorder)

        with qtbot.waitSignal(vm.error, timeout=1000) as blocker:
            recorder.error_occurred.emit("mic failed")
        assert blocker.args == ["mic failed"]
