"""ElevenLabs TTS adapter using convert_with_timestamps API."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.ports.tts_generation import RawTTSResult, RawWordTimestamp

logger = structlog.get_logger()

_DEFAULT_VOICES: dict[str, str] = {
    "American": "21m00Tcm4TlvDq8ikWAM",  # Rachel
    "British": "pNInz6obpgDQGcFmaJgB",  # Adam
    "Australian": "ErXwobaYiN019PkySvjV",  # Antoni
    "Canadian": "21m00Tcm4TlvDq8ikWAM",  # Rachel (fallback)
    "Indian": "pNInz6obpgDQGcFmaJgB",  # Adam (fallback)
}


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        msg = "ELEVENLABS_API_KEY not set"
        raise RuntimeError(msg)
    return key


def _chars_to_word_timestamps(
    characters: list[dict[str, Any]],
    text: str,
) -> list[RawWordTimestamp]:
    """Aggregate character-level timestamps into word-level timestamps.

    ElevenLabs returns character-level data with fields:
      character, character_start_times_seconds, character_end_times_seconds
    We merge consecutive characters into words based on whitespace in the text.
    """
    words = text.split()
    result: list[RawWordTimestamp] = []
    char_idx = 0

    for word in words:
        while char_idx < len(characters) and characters[char_idx].get("character", "") in (" ", ""):
            char_idx += 1

        word_start = None
        word_end = 0.0
        chars_consumed = 0

        while chars_consumed < len(word) and char_idx < len(characters):
            char_data = characters[char_idx]
            start = char_data.get("character_start_times_seconds", 0.0)
            end = char_data.get("character_end_times_seconds", 0.0)

            if word_start is None:
                word_start = start
            word_end = end

            char_idx += 1
            chars_consumed += 1

        result.append(
            RawWordTimestamp(
                word=word,
                start_seconds=word_start or 0.0,
                end_seconds=word_end,
            )
        )

    return result


class ElevenLabsTTSAdapter:
    """TTS generation via ElevenLabs convert_with_timestamps API."""

    def __init__(self, voice_map: dict[str, str] | None = None) -> None:
        self._voice_map = voice_map or _DEFAULT_VOICES
        from elevenlabs import ElevenLabs

        self._client = ElevenLabs(api_key=_get_api_key())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
    async def generate_with_timestamps(
        self,
        text: str,
        english_variant: str,
    ) -> RawTTSResult:
        """Generate TTS audio with word-level timestamps."""
        voice_id = self._voice_map.get(english_variant, list(self._voice_map.values())[0])

        logger.info(
            "elevenlabs_tts_start",
            text_length=len(text),
            english_variant=english_variant,
            voice_id=voice_id,
        )

        response = await asyncio.to_thread(
            self._client.text_to_speech.convert_with_timestamps,
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        audio_chunks: list[bytes] = []
        all_characters: list[dict[str, Any]] = []

        for item in response:
            if item.get("audio_base64"):
                audio_chunks.append(base64.b64decode(item["audio_base64"]))
            if item.get("alignment"):
                alignment = item["alignment"]
                chars = alignment.get("characters", [])
                starts = alignment.get("character_start_times_seconds", [])
                ends = alignment.get("character_end_times_seconds", [])
                for i, char in enumerate(chars):
                    all_characters.append(
                        {
                            "character": char,
                            "character_start_times_seconds": starts[i] if i < len(starts) else 0.0,
                            "character_end_times_seconds": ends[i] if i < len(ends) else 0.0,
                        }
                    )

        audio_data = b"".join(audio_chunks)
        word_timestamps = _chars_to_word_timestamps(all_characters, text)
        duration = word_timestamps[-1].end_seconds if word_timestamps else 0.0

        logger.info(
            "elevenlabs_tts_done",
            audio_bytes=len(audio_data),
            word_count=len(word_timestamps),
            duration=duration,
        )

        return RawTTSResult(
            audio_data=audio_data,
            audio_format="mp3",
            sample_rate=44100,
            channels=1,
            sample_width=2,
            duration_seconds=duration,
            word_timestamps=tuple(word_timestamps),
        )
