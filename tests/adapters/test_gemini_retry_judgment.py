"""Snapshot tests for GeminiRetryJudgmentAdapter's LLM output parsing."""

from parla.adapters.gemini_retry_judgment import LLMRetryJudgmentResult

# Based on V5 verification outputs

CORRECT_JSON = '{"correct": true, "reason": "一致しています"}'
INCORRECT_VOCAB_JSON = '{"correct": false, "reason": "複数の語彙が異なる"}'
INCORRECT_JP_JSON = '{"correct": false, "reason": "日本語の混入"}'
INCORRECT_INCOMPLETE_JSON = '{"correct": false, "reason": "文が未完成のため"}'


class TestRetryJudgmentParsing:
    def test_correct_judgment(self) -> None:
        result = LLMRetryJudgmentResult.model_validate_json(CORRECT_JSON)
        assert result.correct is True
        assert result.reason == "一致しています"

    def test_incorrect_vocab(self) -> None:
        result = LLMRetryJudgmentResult.model_validate_json(INCORRECT_VOCAB_JSON)
        assert result.correct is False

    def test_incorrect_japanese_mixed(self) -> None:
        result = LLMRetryJudgmentResult.model_validate_json(INCORRECT_JP_JSON)
        assert result.correct is False
        assert "日本語" in result.reason

    def test_incorrect_incomplete(self) -> None:
        result = LLMRetryJudgmentResult.model_validate_json(INCORRECT_INCOMPLETE_JSON)
        assert result.correct is False
