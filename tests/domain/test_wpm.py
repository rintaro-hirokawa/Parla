"""Tests for WPM calculation and Phase C skip logic."""

import pytest

from parla.domain.wpm import (
    CEFR_WPM_TARGETS,
    calculate_time_limit,
    calculate_wpm,
    is_wpm_in_target,
    should_skip_phase_c,
)


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
        # B1 lower target = 110 WPM, 100 words → 100/110 * 60 = 54.5s, * 1.2 buffer = 65.5s
        result = calculate_time_limit(100, "B1")
        assert result == pytest.approx(100 / 110 * 60 * 1.2)

    def test_custom_buffer(self) -> None:
        result = calculate_time_limit(100, "B1", buffer_ratio=1.0)
        assert result == pytest.approx(100 / 110 * 60)

    def test_a2_level(self) -> None:
        result = calculate_time_limit(90, "A2")
        # A2 lower = 90 WPM → 90/90 * 60 = 60s * 1.2 = 72s
        assert result == pytest.approx(72.0)

    def test_unknown_cefr_raises(self) -> None:
        with pytest.raises(KeyError):
            calculate_time_limit(100, "X9")


class TestIsWpmInTarget:
    def test_in_range(self) -> None:
        assert is_wpm_in_target(120.0, "B1") is True

    def test_at_lower_bound(self) -> None:
        assert is_wpm_in_target(110.0, "B1") is True

    def test_at_upper_bound(self) -> None:
        assert is_wpm_in_target(130.0, "B1") is True

    def test_below_range(self) -> None:
        assert is_wpm_in_target(109.0, "B1") is False

    def test_above_range(self) -> None:
        assert is_wpm_in_target(131.0, "B1") is False

    def test_a2_range(self) -> None:
        assert is_wpm_in_target(95.0, "A2") is True

    def test_c1_range(self) -> None:
        assert is_wpm_in_target(190.0, "C1") is True


class TestShouldSkipPhaseC:
    def test_skip_when_no_items_and_wpm_ok(self) -> None:
        assert should_skip_phase_c(0, 120.0, "B1") is True

    def test_no_skip_when_items_exist(self) -> None:
        assert should_skip_phase_c(1, 120.0, "B1") is False

    def test_no_skip_when_wpm_below_target(self) -> None:
        assert should_skip_phase_c(0, 80.0, "B1") is False

    def test_no_skip_when_wpm_above_target(self) -> None:
        assert should_skip_phase_c(0, 200.0, "B1") is False

    def test_no_skip_when_both_conditions_fail(self) -> None:
        assert should_skip_phase_c(3, 80.0, "B1") is False


class TestCefrTargets:
    def test_all_levels_defined(self) -> None:
        assert set(CEFR_WPM_TARGETS.keys()) == {"A2", "B1", "B2", "C1"}

    def test_ranges_ascending(self) -> None:
        levels = ["A2", "B1", "B2", "C1"]
        for i in range(len(levels) - 1):
            low_cur, _ = CEFR_WPM_TARGETS[levels[i]]
            low_next, _ = CEFR_WPM_TARGETS[levels[i + 1]]
            assert low_cur < low_next
