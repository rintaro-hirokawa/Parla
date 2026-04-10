"""Snapshot tests for GeminiReviewJudgmentAdapter's LLM output parsing."""

from parla.adapters.gemini_review_judgment import (
    LLMReviewJudgmentResult,
    LLMTranscriptionResult,
)

TRANSCRIPTION_JSON = '{"user_utterance": "This company is responsible for making AI systems safe."}'

JUDGMENT_CORRECT_JSON = """{
    "correct": true,
    "item_used": true,
    "reason": "学習項目を正しく使用"
}"""

JUDGMENT_INCORRECT_JSON = """{
    "correct": false,
    "item_used": false,
    "reason": "学習項目の不使用"
}"""

JUDGMENT_ITEM_USED_BUT_WRONG_JSON = """{
    "correct": false,
    "item_used": true,
    "reason": "意味が大きく異なる"
}"""


class TestTranscriptionParsing:
    def test_parse_transcription(self) -> None:
        result = LLMTranscriptionResult.model_validate_json(TRANSCRIPTION_JSON)
        assert "responsible for" in result.user_utterance


class TestReviewJudgmentParsing:
    def test_correct_judgment(self) -> None:
        result = LLMReviewJudgmentResult.model_validate_json(JUDGMENT_CORRECT_JSON)
        assert result.correct is True
        assert result.item_used is True

    def test_incorrect_judgment(self) -> None:
        result = LLMReviewJudgmentResult.model_validate_json(JUDGMENT_INCORRECT_JSON)
        assert result.correct is False
        assert result.item_used is False

    def test_item_used_but_wrong_meaning(self) -> None:
        result = LLMReviewJudgmentResult.model_validate_json(JUDGMENT_ITEM_USED_BUT_WRONG_JSON)
        assert result.correct is False
        assert result.item_used is True
