"""Shared test helpers and fixtures."""

import io
import wave

from parla.domain.audio import AudioData

# Default audio parameters
_SAMPLE_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2


def make_wav_audio(
    *,
    n_samples: int = 160,
    sample_rate: int = _SAMPLE_RATE,
    channels: int = _CHANNELS,
    sample_width: int = _SAMPLE_WIDTH,
    duration_seconds: float | None = None,
) -> AudioData:
    """Create an AudioData with valid WAV bytes (header + PCM silence)."""
    pcm = b"\x00" * n_samples * sample_width * channels
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    if duration_seconds is None:
        duration_seconds = n_samples / sample_rate
    return AudioData(
        data=buf.getvalue(),
        format="wav",
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        duration_seconds=duration_seconds,
    )
