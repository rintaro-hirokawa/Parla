"""Tests for LocalAudioStorage."""

import io
import wave
from uuid import uuid4

from parla.adapters.local_audio_storage import LocalAudioStorage
from parla.domain.audio import AudioData


def _make_wav_data(
    n_samples: int = 160,
    sample_width: int = 2,
    sample_rate: int = 16000,
    channels: int = 1,
) -> bytes:
    """Generate valid WAV bytes containing silence."""
    pcm = b"\x00" * n_samples * sample_width * channels
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _make_audio(**overrides) -> AudioData:
    sample_rate = overrides.pop("sample_rate", 16000)
    channels = overrides.pop("channels", 1)
    sample_width = overrides.pop("sample_width", 2)
    defaults = {
        "data": _make_wav_data(160, sample_width, sample_rate, channels),
        "format": "wav",
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width": sample_width,
        "duration_seconds": 0.01,
    }
    defaults.update(overrides)
    return AudioData(**defaults)


class TestSaveAndLoad:
    def test_save_and_load_wav(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        sid = uuid4()
        audio = _make_audio()

        storage.save(sid, audio)
        loaded = storage.load(sid)

        assert loaded is not None
        assert loaded.format == "wav"
        assert loaded.sample_rate == 16000
        assert loaded.channels == 1
        assert loaded.sample_width == 2
        assert loaded.data == audio.data

    def test_load_nonexistent_returns_none(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        assert storage.load(uuid4()) is None

    def test_save_creates_directory(self, tmp_path) -> None:
        base = tmp_path / "deep" / "nested" / "audio"
        storage = LocalAudioStorage(base)
        storage.save(uuid4(), _make_audio())
        assert base.exists()


class TestDelete:
    def test_delete_removes_file(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        sid = uuid4()
        storage.save(sid, _make_audio())

        storage.delete(sid)
        assert storage.load(sid) is None

    def test_delete_nonexistent_is_noop(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        storage.delete(uuid4())  # should not raise


class TestWavRoundTrip:
    def test_preserves_metadata(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        sid = uuid4()
        audio = _make_audio(
            sample_rate=44100,
            channels=2,
            sample_width=2,
            data=_make_wav_data(441, 2, 44100, 2),
        )

        storage.save(sid, audio)
        loaded = storage.load(sid)

        assert loaded is not None
        assert loaded.sample_rate == 44100
        assert loaded.channels == 2
        assert loaded.sample_width == 2

    def test_duration_computed_from_frames(self, tmp_path) -> None:
        storage = LocalAudioStorage(tmp_path / "audio")
        sid = uuid4()
        audio = _make_audio(
            data=_make_wav_data(16000, 2, 16000, 1),
            sample_rate=16000,
            duration_seconds=1.0,
        )

        storage.save(sid, audio)
        loaded = storage.load(sid)

        assert loaded is not None
        assert abs(loaded.duration_seconds - 1.0) < 0.001
