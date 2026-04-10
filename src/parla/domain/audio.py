"""AudioData value object — raw audio with metadata."""

from pydantic import BaseModel, Field


class AudioData(BaseModel, frozen=True):
    """Audio recording with format metadata.

    Domain receives this from the client (UI/recording layer).
    File path resolution is handled by infrastructure (AudioStorage port).
    """

    data: bytes
    format: str = Field(description="File format: wav, mp3, etc.")
    sample_rate: int = Field(description="Sample rate in Hz (e.g. 16000, 44100)")
    channels: int = Field(ge=1, description="Number of channels (1=mono, 2=stereo)")
    sample_width: int = Field(ge=1, description="Bytes per sample (e.g. 2 for 16-bit)")
    duration_seconds: float = Field(ge=0.0, description="Recording duration in seconds")
