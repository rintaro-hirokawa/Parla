"""Tests for WPM calculation."""

import pytest

from parla.domain.practice import PronunciationWord
from parla.domain.wpm import (
    CEFR_WPM_TARGETS,
    calculate_speech_duration,
    calculate_time_limit,
    calculate_wpm,
)


def _pw(word: str, offset: float = 0.0, duration: float = 0.3, error_type: str = "None") -> PronunciationWord:
    return PronunciationWord(
        word=word, accuracy_score=90.0, error_type=error_type,
        offset_seconds=offset, duration_seconds=duration,
    )


class TestCalculateSpeechDuration:
    def test_basic(self) -> None:
        words = [_pw("hello", 0.5, 0.3), _pw("world", 1.0, 0.4)]
        # 0.5 to 1.4
        assert calculate_speech_duration(words) == pytest.approx(0.9)

    def test_omissions_excluded(self) -> None:
        words = [
            _pw("hello", 0.5, 0.3),
            _pw("missed", offset=-1.0, duration=0.0, error_type="Omission"),
            _pw("world", 1.0, 0.4),
        ]
        assert calculate_speech_duration(words) == pytest.approx(0.9)

    def test_single_word(self) -> None:
        words = [_pw("hello", 0.5, 0.3)]
        assert calculate_speech_duration(words) == pytest.approx(0.3)

    def test_no_recognized_words(self) -> None:
        words = [_pw("missed", offset=-1.0, duration=0.0, error_type="Omission")]
        assert calculate_speech_duration(words) == pytest.approx(0.0)

    def test_empty(self) -> None:
        assert calculate_speech_duration([]) == pytest.approx(0.0)


class TestCalculateWpm:
    def test_normal(self) -> None:
        assert calculate_wpm(100, 60.0) == pytest.approx(100.0)

    def test_fast_speaker(self) -> None:
        assert calculate_wpm(200, 60.0) == pytest.approx(200.0)

    def test_slow_speaker(self) -> None:
        assert calculate_wpm(50, 60.0) == pytest.approx(50.0)

    def test_fractional(self) -> None:
        assert calculate_wpm(75, 45.0) == pytest.approx(100.0)

    def test_zero_duration_returns_zero(self) -> None:
        assert calculate_wpm(100, 0.0) == 0.0

    def test_zero_words(self) -> None:
        assert calculate_wpm(0, 30.0) == pytest.approx(0.0)


class TestCalculateTimeLimit:
    def test_b1_100_words(self) -> None:
        # B1 target = 110 WPM, 100 words → 100/110 * 60 = 54.5s, * 1.2 buffer = 65.5s
        result = calculate_time_limit(100, "B1")
        assert result == pytest.approx(100 / 110 * 60 * 1.2)

    def test_custom_buffer(self) -> None:
        result = calculate_time_limit(100, "B1", buffer_ratio=1.0)
        assert result == pytest.approx(100 / 110 * 60)

    def test_a2_level(self) -> None:
        result = calculate_time_limit(90, "A2")
        # A2 target = 90 WPM → 90/90 * 60 = 60s * 1.2 = 72s
        assert result == pytest.approx(72.0)

    def test_unknown_cefr_raises(self) -> None:
        with pytest.raises(KeyError):
            calculate_time_limit(100, "X9")


class TestCefrTargets:
    def test_all_levels_defined(self) -> None:
        assert set(CEFR_WPM_TARGETS.keys()) == {"A2", "B1", "B2", "C1"}

    def test_values_ascending(self) -> None:
        levels = ["A2", "B1", "B2", "C1"]
        for i in range(len(levels) - 1):
            assert CEFR_WPM_TARGETS[levels[i]] < CEFR_WPM_TARGETS[levels[i + 1]]
