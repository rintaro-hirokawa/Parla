"""Tests for LocalAudioStorage."""

from uuid import uuid4

from parla.adapters.local_audio_storage import LocalAudioStorage
from parla.domain.audio import AudioData


def _make_pcm_data(n_samples: int = 160, sample_width: int = 2) -> bytes:
    """Generate simple PCM audio data (silence)."""
    return b"\x00" * n_samples * sample_width


def _make_audio(**overrides) -> AudioData:
    defaults = {
        "data": _make_pcm_data(160),
        "format": "wav",
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
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
            sample_rate=44100, channels=2, sample_width=2,
            data=_make_pcm_data(441, 2),
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
        # 16000 samples at 16000 Hz = 1.0 second
        audio = _make_audio(
            data=_make_pcm_data(16000, 2),
            sample_rate=16000,
            duration_seconds=1.0,
        )

        storage.save(sid, audio)
        loaded = storage.load(sid)

        assert loaded is not None
        assert abs(loaded.duration_seconds - 1.0) < 0.001
