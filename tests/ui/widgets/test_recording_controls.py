"""Tests for RecordingControlsWidget."""

from PySide6.QtCore import QObject, Qt, Signal

from parla.domain.audio import AudioData
from parla.ui.widgets.recording_controls import RecordingControlsWidget


class MockRecorder(QObject):
    """Mock audio recorder for testing."""

    samples_ready = Signal(list)
    level_updated = Signal(float)
    recording_done = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._recording = False
        self.start_called = False
        self.stop_called = False

    def start_recording(self) -> None:
        self._recording = True
        self.start_called = True

    def stop_recording(self) -> None:
        self._recording = False
        self.stop_called = True

    def is_recording(self) -> bool:
        return self._recording


def _make_audio_data() -> AudioData:
    return AudioData(
        data=b"\x00" * 100,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=1.0,
    )


class TestRecordingControlsWidget:
    def test_click_starts_recording(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        assert recorder.start_called is True

    def test_click_again_stops_recording(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        # Start
        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        # Stop
        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        assert recorder.stop_called is True

    def test_button_text_toggles(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        assert widget._record_button.text() == "Record"
        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        assert widget._record_button.text() == "Stop"
        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        assert widget._record_button.text() == "Record"

    def test_recording_done_emits_signal(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        audio = _make_audio_data()
        with qtbot.waitSignal(widget.recording_finished, timeout=1000) as blocker:
            recorder.recording_done.emit(audio)
        assert blocker.args[0] is audio

    def test_samples_forwarded_to_waveform(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        recorder.samples_ready.emit([0.5, -0.3, 0.1])
        # Verify waveform received the samples
        buf = list(widget.waveform._buffer)
        assert buf[-3:] == [0.5, -0.3, 0.1]

    def test_level_forwarded_to_meter(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        recorder.level_updated.emit(0.7)
        assert widget.level_meter.level == 0.7

    def test_recording_done_resets_button(self, qtbot):
        recorder = MockRecorder()
        widget = RecordingControlsWidget(recorder)
        qtbot.addWidget(widget)

        # Start recording
        qtbot.mouseClick(widget._record_button, Qt.MouseButton.LeftButton)
        assert widget._record_button.text() == "Stop"

        # Simulate recording done
        recorder.recording_done.emit(_make_audio_data())
        assert widget._record_button.text() == "Record"
