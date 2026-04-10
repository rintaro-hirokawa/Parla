"""Local filesystem implementation of AudioStorage."""

import wave
from pathlib import Path
from uuid import UUID

import structlog

from parla.domain.audio import AudioData

logger = structlog.get_logger()


class LocalAudioStorage:
    """Stores audio files on the local filesystem.

    Files are stored as: base_dir / {sentence_id}.{format}
    Future: replace with cloud storage adapter.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, sentence_id: UUID, audio: AudioData) -> None:
        path = self._path_for(sentence_id, audio.format)
        if audio.format == "wav":
            self._write_wav(path, audio)
        else:
            path.write_bytes(audio.data)
        logger.info(
            "audio_saved",
            sentence_id=str(sentence_id),
            format=audio.format,
            duration=audio.duration_seconds,
            path=str(path),
        )

    def load(self, sentence_id: UUID) -> AudioData | None:
        for fmt in ("wav", "mp3"):
            path = self._path_for(sentence_id, fmt)
            if path.exists():
                if fmt == "wav":
                    return self._read_wav(path)
                return AudioData(
                    data=path.read_bytes(),
                    format=fmt,
                    sample_rate=0,
                    channels=0,
                    sample_width=0,
                    duration_seconds=0.0,
                )
        return None

    def delete(self, sentence_id: UUID) -> None:
        for fmt in ("wav", "mp3"):
            path = self._path_for(sentence_id, fmt)
            if path.exists():
                path.unlink()
                logger.info("audio_deleted", sentence_id=str(sentence_id), path=str(path))

    def _path_for(self, sentence_id: UUID, fmt: str) -> Path:
        return self._base_dir / f"{sentence_id}.{fmt}"

    @staticmethod
    def _write_wav(path: Path, audio: AudioData) -> None:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(audio.channels)
            wf.setsampwidth(audio.sample_width)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(audio.data)

    @staticmethod
    def _read_wav(path: Path) -> AudioData:
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)
            duration = n_frames / sample_rate if sample_rate > 0 else 0.0
        return AudioData(
            data=data,
            format="wav",
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration_seconds=duration,
        )
