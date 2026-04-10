"""Tests for difflib similarity judgment logic."""

import pytest

from parla.domain.similarity import (
    calculate_similarity,
    judge_passage,
    judge_sentence_status,
)


class TestCalculateSimilarity:
    def test_identical(self) -> None:
        assert calculate_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_identical_case_insensitive(self) -> None:
        assert calculate_similarity("Hello World", "hello world") == pytest.approx(1.0)

    def test_completely_different(self) -> None:
        assert calculate_similarity("hello world", "goodbye moon") == pytest.approx(0.0)

    def test_partial_match(self) -> None:
        result = calculate_similarity(
            "the cat sat on the mat",
            "the cat on the mat",
        )
        assert 0.5 < result < 1.0

    def test_empty_reference(self) -> None:
        assert calculate_similarity("", "hello") == pytest.approx(0.0)

    def test_empty_recognized(self) -> None:
        assert calculate_similarity("hello world", "") == pytest.approx(0.0)

    def test_both_empty(self) -> None:
        assert calculate_similarity("", "") == pytest.approx(1.0)

    def test_paraphrase_level(self) -> None:
        result = calculate_similarity(
            "He is responsible for ensuring safety",
            "He is responsible for making sure it is safe",
        )
        assert 0.3 < result < 0.9

    def test_minor_difference(self) -> None:
        result = calculate_similarity(
            "The company makes better cars every year",
            "The company makes better car every year",
        )
        assert result >= 0.80


class TestJudgeSentenceStatus:
    def test_correct(self) -> None:
        assert judge_sentence_status(0.95, 0.0) == "correct"

    def test_correct_at_boundary(self) -> None:
        assert judge_sentence_status(0.90, 0.0) == "correct"

    def test_paraphrase(self) -> None:
        assert judge_sentence_status(0.75, 0.0) == "paraphrase"

    def test_paraphrase_at_lower_boundary(self) -> None:
        assert judge_sentence_status(0.50, 0.0) == "paraphrase"

    def test_error_low_similarity(self) -> None:
        assert judge_sentence_status(0.40, 0.0) == "error"

    def test_error_at_boundary(self) -> None:
        assert judge_sentence_status(0.4999, 0.0) == "error"

    def test_error_high_omission_overrides_similarity(self) -> None:
        assert judge_sentence_status(0.80, 0.55) == "error"

    def test_error_omission_at_boundary(self) -> None:
        assert judge_sentence_status(0.95, 0.51) == "error"

    def test_correct_with_low_omission(self) -> None:
        assert judge_sentence_status(0.95, 0.10) == "correct"

    def test_zero_similarity(self) -> None:
        assert judge_sentence_status(0.0, 0.0) == "error"


class TestJudgePassage:
    def test_all_correct(self) -> None:
        statuses = ["correct", "correct", "correct"]
        assert judge_passage(statuses) is True

    def test_mixed_correct_paraphrase(self) -> None:
        statuses = ["correct", "paraphrase", "correct"]
        assert judge_passage(statuses) is True

    def test_all_paraphrase(self) -> None:
        statuses = ["paraphrase", "paraphrase"]
        assert judge_passage(statuses) is True

    def test_one_error_fails(self) -> None:
        statuses = ["correct", "error", "correct"]
        assert judge_passage(statuses) is False

    def test_all_error(self) -> None:
        statuses = ["error", "error"]
        assert judge_passage(statuses) is False

    def test_empty_passes(self) -> None:
        assert judge_passage([]) is True
