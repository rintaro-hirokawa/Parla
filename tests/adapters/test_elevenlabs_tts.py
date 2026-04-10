"""Tests for ElevenLabs TTS adapter — character-to-word timestamp aggregation."""

from parla.adapters.elevenlabs_tts import _chars_to_word_timestamps


class TestCharsToWordTimestamps:
    def test_simple_two_words(self) -> None:
        characters = [
            {"character": "H", "character_start_times_seconds": 0.0, "character_end_times_seconds": 0.05},
            {"character": "i", "character_start_times_seconds": 0.05, "character_end_times_seconds": 0.1},
            {"character": " ", "character_start_times_seconds": 0.1, "character_end_times_seconds": 0.15},
            {"character": "t", "character_start_times_seconds": 0.15, "character_end_times_seconds": 0.2},
            {"character": "o", "character_start_times_seconds": 0.2, "character_end_times_seconds": 0.25},
        ]
        result = _chars_to_word_timestamps(characters, "Hi to")

        assert len(result) == 2
        assert result[0].word == "Hi"
        assert result[0].start_seconds == 0.0
        assert result[0].end_seconds == 0.1
        assert result[1].word == "to"
        assert result[1].start_seconds == 0.15
        assert result[1].end_seconds == 0.25

    def test_single_word(self) -> None:
        characters = [
            {"character": "H", "character_start_times_seconds": 0.0, "character_end_times_seconds": 0.1},
            {"character": "e", "character_start_times_seconds": 0.1, "character_end_times_seconds": 0.2},
            {"character": "y", "character_start_times_seconds": 0.2, "character_end_times_seconds": 0.3},
        ]
        result = _chars_to_word_timestamps(characters, "Hey")

        assert len(result) == 1
        assert result[0].word == "Hey"
        assert result[0].start_seconds == 0.0
        assert result[0].end_seconds == 0.3

    def test_empty_text(self) -> None:
        result = _chars_to_word_timestamps([], "")
        assert result == []

    def test_multiple_spaces(self) -> None:
        characters = [
            {"character": "a", "character_start_times_seconds": 0.0, "character_end_times_seconds": 0.1},
            {"character": " ", "character_start_times_seconds": 0.1, "character_end_times_seconds": 0.15},
            {"character": " ", "character_start_times_seconds": 0.15, "character_end_times_seconds": 0.2},
            {"character": "b", "character_start_times_seconds": 0.2, "character_end_times_seconds": 0.3},
        ]
        # text.split() handles multiple spaces
        result = _chars_to_word_timestamps(characters, "a  b")

        assert len(result) == 2
        assert result[0].word == "a"
        assert result[1].word == "b"
