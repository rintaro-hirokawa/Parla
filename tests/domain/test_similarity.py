"""Tests for error-rate-based pass/fail judgment logic."""

import pytest

from parla.domain.practice import (
    ERROR_RATE_THRESHOLD,
    PronunciationWord,
    calculate_error_rate,
    judge_passed,
)


def _word(error_type: str) -> PronunciationWord:
    """Helper to create a PronunciationWord with only error_type set."""
    return PronunciationWord(word="w", accuracy_score=100.0, error_type=error_type)


def _words(*error_types: str) -> list[PronunciationWord]:
    return [_word(et) for et in error_types]


class TestCalculateErrorRate:
    def test_all_correct(self) -> None:
        assert calculate_error_rate(_words("None", "None", "None")) == pytest.approx(0.0)

    def test_all_mispronunciation(self) -> None:
        assert calculate_error_rate(_words("Mispronunciation", "Mispronunciation")) == pytest.approx(1.0)

    def test_all_omission(self) -> None:
        assert calculate_error_rate(_words("Omission", "Omission")) == pytest.approx(1.0)

    def test_mixed_errors(self) -> None:
        # 2 errors out of 5 ref-aligned words
        words = _words("None", "Mispronunciation", "None", "Omission", "None")
        assert calculate_error_rate(words) == pytest.approx(0.4)

    def test_insertions_excluded(self) -> None:
        # Insertions don't count toward ref-aligned total
        words = _words("None", "None", "Insertion", "Mispronunciation")
        # ref-aligned: None, None, Mispronunciation → 1/3
        assert calculate_error_rate(words) == pytest.approx(1 / 3)

    def test_empty(self) -> None:
        assert calculate_error_rate([]) == pytest.approx(0.0)

    def test_only_insertions(self) -> None:
        assert calculate_error_rate(_words("Insertion", "Insertion")) == pytest.approx(0.0)


class TestJudgePassed:
    def test_all_correct_passes(self) -> None:
        assert judge_passed(_words("None", "None", "None")) is True

    def test_below_threshold_passes(self) -> None:
        # 1 error out of 10 = 10% < 15%
        words = _words("Mispronunciation", *["None"] * 9)
        assert judge_passed(words) is True

    def test_at_threshold_fails(self) -> None:
        # 15% is NOT < 15%, so it fails
        # 3 errors out of 20 = 15%
        words = _words(*["Mispronunciation"] * 3, *["None"] * 17)
        assert judge_passed(words) is False

    def test_above_threshold_fails(self) -> None:
        # 2 errors out of 5 = 40%
        words = _words("Mispronunciation", "Omission", "None", "None", "None")
        assert judge_passed(words) is False

    def test_empty_passes(self) -> None:
        assert judge_passed([]) is True

    def test_threshold_value(self) -> None:
        assert ERROR_RATE_THRESHOLD == 0.15
