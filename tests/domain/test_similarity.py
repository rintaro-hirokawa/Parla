"""Tests for error-rate-based pass/fail judgment logic."""

import pytest

from parla.domain.similarity import (
    ERROR_RATE_THRESHOLD,
    calculate_error_rate,
    judge_passed,
)


class TestCalculateErrorRate:
    def test_all_correct(self) -> None:
        assert calculate_error_rate(["None", "None", "None"]) == pytest.approx(0.0)

    def test_all_mispronunciation(self) -> None:
        assert calculate_error_rate(["Mispronunciation", "Mispronunciation"]) == pytest.approx(1.0)

    def test_all_omission(self) -> None:
        assert calculate_error_rate(["Omission", "Omission"]) == pytest.approx(1.0)

    def test_mixed_errors(self) -> None:
        # 2 errors out of 5 ref-aligned words
        types = ["None", "Mispronunciation", "None", "Omission", "None"]
        assert calculate_error_rate(types) == pytest.approx(0.4)

    def test_insertions_excluded(self) -> None:
        # Insertions don't count toward ref-aligned total
        types = ["None", "None", "Insertion", "Mispronunciation"]
        # ref-aligned: None, None, Mispronunciation → 1/3
        assert calculate_error_rate(types) == pytest.approx(1 / 3)

    def test_empty(self) -> None:
        assert calculate_error_rate([]) == pytest.approx(0.0)

    def test_only_insertions(self) -> None:
        assert calculate_error_rate(["Insertion", "Insertion"]) == pytest.approx(0.0)


class TestJudgePassed:
    def test_all_correct_passes(self) -> None:
        assert judge_passed(["None", "None", "None"]) is True

    def test_below_threshold_passes(self) -> None:
        # 1 error out of 10 = 10% < 15%
        types = ["Mispronunciation"] + ["None"] * 9
        assert judge_passed(types) is True

    def test_at_threshold_fails(self) -> None:
        # 15% is NOT < 15%, so it fails
        # 3 errors out of 20 = 15%
        types = ["Mispronunciation"] * 3 + ["None"] * 17
        assert judge_passed(types) is False

    def test_above_threshold_fails(self) -> None:
        # 2 errors out of 5 = 40%
        types = ["Mispronunciation", "Omission", "None", "None", "None"]
        assert judge_passed(types) is False

    def test_empty_passes(self) -> None:
        assert judge_passed([]) is True

    def test_threshold_value(self) -> None:
        assert ERROR_RATE_THRESHOLD == 0.15
