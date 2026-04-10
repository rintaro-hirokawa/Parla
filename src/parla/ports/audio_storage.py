"""Port for audio file storage."""

from typing import Protocol
from uuid import UUID

from parla.domain.audio import AudioData


class AudioStorage(Protocol):
    """Stores and retrieves audio recordings.

    Domain uses logical IDs (sentence_id). File path resolution
    is the adapter's responsibility.
    """

    def save(self, sentence_id: UUID, audio: AudioData) -> None: ...

    def load(self, sentence_id: UUID) -> AudioData | None: ...

    def delete(self, sentence_id: UUID) -> None: ...
