"""Tests for overlapping timing deviation calculation."""

import pytest

from parla.domain.timing import calculate_timing_deviations


class TestCalculateTimingDeviations:
    def test_perfect_sync(self) -> None:
        user = [0.0, 0.5, 1.0, 1.5]
        ref = [0.0, 0.5, 1.0, 1.5]
        result = calculate_timing_deviations(user, ref)
        assert all(d == pytest.approx(0.0) for d in result)

    def test_uniform_delay_no_correction(self) -> None:
        """Without baseline correction, uniform delay is reported as-is."""
        user = [0.3, 0.8, 1.3, 1.8]
        ref = [0.0, 0.5, 1.0, 1.5]
        result = calculate_timing_deviations(user, ref, baseline_correction=False)
        assert all(d == pytest.approx(0.3) for d in result)

    def test_uniform_delay_with_correction(self) -> None:
        """With baseline correction, uniform delay is absorbed (median subtracted)."""
        user = [0.3, 0.8, 1.3, 1.8]
        ref = [0.0, 0.5, 1.0, 1.5]
        result = calculate_timing_deviations(user, ref, baseline_correction=True)
        assert all(d == pytest.approx(0.0) for d in result)

    def test_stumble_pattern(self) -> None:
        """One word has a spike — detectable with or without correction."""
        ref = [0.0, 0.5, 1.0, 1.5, 2.0]
        user = [0.0, 0.5, 1.8, 2.3, 2.5]  # stumble at word 2
        result = calculate_timing_deviations(user, ref, baseline_correction=False)
        # Word 2 has largest deviation
        assert result[2] > result[0]
        assert result[2] > result[1]

    def test_gradual_delay(self) -> None:
        """Gradually increasing delay — deviations should increase."""
        ref = [0.0, 0.5, 1.0, 1.5, 2.0]
        user = [0.0, 0.6, 1.3, 2.1, 3.0]
        result = calculate_timing_deviations(user, ref, baseline_correction=False)
        # Each deviation should be >= previous
        for i in range(1, len(result)):
            assert result[i] >= result[i - 1]

    def test_negative_deviation_ahead_of_reference(self) -> None:
        """User speaking faster than reference results in negative deviation."""
        user = [0.0, 0.3, 0.6]
        ref = [0.0, 0.5, 1.0]
        result = calculate_timing_deviations(user, ref, baseline_correction=False)
        assert result[1] < 0
        assert result[2] < 0

    def test_empty_sequences(self) -> None:
        result = calculate_timing_deviations([], [])
        assert result == []

    def test_single_element(self) -> None:
        result = calculate_timing_deviations([0.3], [0.0])
        assert result == [pytest.approx(0.3)]

    def test_mismatched_lengths_uses_minimum(self) -> None:
        user = [0.0, 0.5, 1.0]
        ref = [0.0, 0.5]
        result = calculate_timing_deviations(user, ref)
        assert len(result) == 2

    def test_baseline_correction_with_spike(self) -> None:
        """Baseline correction removes uniform offset but preserves spike."""
        ref = [0.0, 0.5, 1.0, 1.5, 2.0]
        # Uniform 0.3s delay + 0.5s spike at word 2
        user = [0.3, 0.8, 1.8, 1.8, 2.3]
        result_no_corr = calculate_timing_deviations(user, ref, baseline_correction=False)
        result_with_corr = calculate_timing_deviations(user, ref, baseline_correction=True)
        # With correction, most words should be near 0, but the spike word should stand out
        assert abs(result_with_corr[0]) < abs(result_no_corr[0])
        assert result_with_corr[2] > result_with_corr[0]
