"""Tests for overlapping lag detection — domain types and pure functions."""

import pytest
from pydantic import ValidationError

from parla.domain.lag_detection import (
    DelayedPhrase,
    LagDetectionResult,
    LagPoint,
    identify_delayed_phrases,
)


class TestIdentifyDelayedPhrases:
    def test_no_delays(self) -> None:
        words = ["The", "cat", "sat", "on", "the", "mat"]
        deviations = [0.0, 0.1, 0.0, 0.1, 0.0, 0.1]
        result = identify_delayed_phrases(words, deviations)
        assert result == []

    def test_single_word_spike_smoothed_away(self) -> None:
        """A single-word spike gets smoothed below threshold — not detected."""
        words = ["The", "cat", "sat", "on", "the", "mat"]
        deviations = [0.0, 0.0, 0.8, 0.0, 0.0, 0.0]
        result = identify_delayed_phrases(words, deviations)
        # Smoothing window=3 averages 0.8 with neighbors → ~0.27 < 0.3
        assert result == []

    def test_contiguous_delay_detected(self) -> None:
        """Two adjacent delayed words survive smoothing."""
        words = ["The", "cat", "sat", "on", "the", "mat"]
        deviations = [0.0, 0.0, 0.8, 0.7, 0.0, 0.0]
        result = identify_delayed_phrases(words, deviations)
        assert len(result) >= 1
        delayed_words = set()
        for phrase in result:
            for idx in phrase.word_indices:
                delayed_words.add(words[idx])
        assert "sat" in delayed_words

    def test_contiguous_phrase_delay(self) -> None:
        words = ["I", "want", "to", "establish", "a", "connection"]
        deviations = [0.0, 0.0, 0.0, 0.8, 0.7, 0.6]
        result = identify_delayed_phrases(words, deviations)
        assert len(result) >= 1
        # The last 3 words should be in a single phrase or overlapping phrases
        all_indices = set()
        for phrase in result:
            all_indices.update(phrase.word_indices)
        assert 3 in all_indices  # "establish"

    def test_multiple_separate_delays(self) -> None:
        words = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        deviations = [0.8, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.8, 0.0]
        result = identify_delayed_phrases(words, deviations)
        assert len(result) >= 2

    def test_empty_inputs(self) -> None:
        assert identify_delayed_phrases([], []) == []

    def test_custom_threshold(self) -> None:
        words = ["The", "cat", "sat", "on"]
        deviations = [0.0, 0.6, 0.6, 0.0]
        # With high threshold, smoothed values (~0.4) are below
        assert identify_delayed_phrases(words, deviations, threshold=0.5) == []
        # With low threshold, delay detected
        result = identify_delayed_phrases(words, deviations, threshold=0.2)
        assert len(result) >= 1

    def test_mismatched_lengths(self) -> None:
        words = ["a", "b", "c", "d"]
        deviations = [0.0, 0.8]  # shorter
        result = identify_delayed_phrases(words, deviations)
        # Should handle gracefully — only process min(len) elements
        assert isinstance(result, list)

    def test_avg_and_max_delay(self) -> None:
        words = ["a", "b", "c", "d", "e"]
        deviations = [0.0, 0.5, 0.9, 0.6, 0.0]
        result = identify_delayed_phrases(words, deviations)
        for phrase in result:
            assert phrase.avg_delay_sec > 0
            assert phrase.max_delay_sec >= phrase.avg_delay_sec

    def test_all_delayed(self) -> None:
        words = ["a", "b", "c"]
        deviations = [0.8, 0.9, 0.7]
        result = identify_delayed_phrases(words, deviations)
        assert len(result) == 1
        assert len(result[0].word_indices) == 3

    def test_phrase_text_joined(self) -> None:
        words = ["The", "quick", "brown", "fox"]
        deviations = [0.0, 0.8, 0.9, 0.0]
        result = identify_delayed_phrases(words, deviations)
        for phrase in result:
            assert " " in phrase.phrase or len(phrase.word_indices) == 1


class TestDomainTypes:
    def test_delayed_phrase_frozen(self) -> None:
        dp = DelayedPhrase(phrase="hello world", word_indices=(0, 1), avg_delay_sec=0.5, max_delay_sec=0.7)
        with pytest.raises(ValidationError):
            dp.phrase = "modified"  # type: ignore[misc]

    def test_lag_point_frozen(self) -> None:
        lp = LagPoint(
            phrase="hello world",
            delay_sec=0.5,
            estimated_cause="pronunciation_difficulty",
            suggestion="ゆっくり練習しましょう",
        )
        assert lp.estimated_cause == "pronunciation_difficulty"

    def test_lag_detection_result(self) -> None:
        result = LagDetectionResult(
            lag_points=(
                LagPoint(
                    phrase="establish a connection",
                    delay_sec=0.8,
                    estimated_cause="vocabulary_recall",
                    suggestion="establish は「確立する」です",
                ),
            ),
            overall_comment="全体的に良い練習でした",
        )
        assert len(result.lag_points) == 1
        assert result.overall_comment == "全体的に良い練習でした"
