"""Tests for ElevenLabs TTS adapter — character-to-word timestamp aggregation."""

from parla.adapters.elevenlabs_tts import _chars_to_word_timestamps


class TestCharsToWordTimestamps:
    def test_simple_two_words(self) -> None:
        chars = ["H", "i", " ", "t", "o"]
        starts = [0.0, 0.05, 0.1, 0.15, 0.2]
        ends = [0.05, 0.1, 0.15, 0.2, 0.25]
        result = _chars_to_word_timestamps(chars, starts, ends, "Hi to")

        assert len(result) == 2
        assert result[0].word == "Hi"
        assert result[0].start_seconds == 0.0
        assert result[0].end_seconds == 0.1
        assert result[1].word == "to"
        assert result[1].start_seconds == 0.15
        assert result[1].end_seconds == 0.25

    def test_single_word(self) -> None:
        chars = ["H", "e", "y"]
        starts = [0.0, 0.1, 0.2]
        ends = [0.1, 0.2, 0.3]
        result = _chars_to_word_timestamps(chars, starts, ends, "Hey")

        assert len(result) == 1
        assert result[0].word == "Hey"
        assert result[0].start_seconds == 0.0
        assert result[0].end_seconds == 0.3

    def test_empty_text(self) -> None:
        result = _chars_to_word_timestamps([], [], [], "")
        assert result == []

    def test_multiple_spaces(self) -> None:
        chars = ["a", " ", " ", "b"]
        starts = [0.0, 0.1, 0.15, 0.2]
        ends = [0.1, 0.15, 0.2, 0.3]
        result = _chars_to_word_timestamps(chars, starts, ends, "a  b")

        assert len(result) == 2
        assert result[0].word == "a"
        assert result[1].word == "b"
