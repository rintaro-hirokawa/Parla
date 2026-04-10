"""Snapshot tests for GeminiFeedbackAdapter's LLM output parsing.

Tests the internal LLM schema parsing and conversion to RawFeedback,
using fixture data modeled after V2 verification outputs.
"""

from parla.adapters.gemini_feedback import (
    LLMFeedbackResult,
    LLMTranscriptionResult,
    _convert_to_raw_feedback,
)

# --- Fixture data (based on V2 verification outputs) ---

TRANSCRIPTION_JSON = (
    '{"user_utterance": "I think this is [pause] very hard because it has （急な坂がわからない） and sharp curves."}'
)

FEEDBACK_JSON = """{
    "model_answer": "I think this is very tough because it has steep slopes and sharp curves.",
    "is_acceptable": false,
    "learning_items": [
        {
            "pattern": "steep",
            "explanation": "「急な」を表す形容詞。例: The road has a steep hill.",
            "category": "語彙",
            "sub_tag": "形容詞",
            "priority": 4,
            "is_reappearance": false,
            "matched_stock_item_id": null
        },
        {
            "pattern": "slope",
            "explanation": "「坂」「斜面」を表す名詞。例: We walked up the slope.",
            "category": "語彙",
            "sub_tag": "名詞",
            "priority": 3,
            "is_reappearance": false,
            "matched_stock_item_id": null
        }
    ]
}"""

FEEDBACK_WITH_REAPPEARANCE_JSON = """{
    "model_answer": "As a result, Toyota has been the top car maker for six years in a row.",
    "is_acceptable": true,
    "learning_items": [
        {
            "pattern": "in a row",
            "explanation": "「連続で」を表す表現。例: I won three games in a row.",
            "category": "表現",
            "sub_tag": "",
            "priority": 5,
            "is_reappearance": false,
            "matched_stock_item_id": null
        },
        {
            "pattern": "as a result of",
            "explanation": "「〜の結果として」を表す表現。例: As a result of the rain, ...",
            "category": "表現",
            "sub_tag": "",
            "priority": 3,
            "is_reappearance": true,
            "matched_stock_item_id": "si-008"
        }
    ]
}"""

FEEDBACK_NO_ITEMS_JSON = """{
    "model_answer": "He is 69 years old but he still tests his company's cars by himself.",
    "is_acceptable": true,
    "learning_items": []
}"""


class TestTranscriptionParsing:
    def test_parse_valid(self) -> None:
        result = LLMTranscriptionResult.model_validate_json(TRANSCRIPTION_JSON)
        assert "sharp curves" in result.user_utterance
        assert "[pause]" in result.user_utterance

    def test_parse_preserves_japanese(self) -> None:
        result = LLMTranscriptionResult.model_validate_json(TRANSCRIPTION_JSON)
        assert "急な坂がわからない" in result.user_utterance


class TestFeedbackParsing:
    def test_parse_with_items(self) -> None:
        result = LLMFeedbackResult.model_validate_json(FEEDBACK_JSON)
        assert result.is_acceptable is False
        assert len(result.learning_items) == 2
        assert result.learning_items[0].pattern == "steep"
        assert result.learning_items[0].category == "語彙"
        assert result.learning_items[0].priority == 4

    def test_parse_with_reappearance(self) -> None:
        result = LLMFeedbackResult.model_validate_json(FEEDBACK_WITH_REAPPEARANCE_JSON)
        reapp = [i for i in result.learning_items if i.is_reappearance]
        assert len(reapp) == 1
        assert reapp[0].matched_stock_item_id == "si-008"

    def test_parse_no_items(self) -> None:
        result = LLMFeedbackResult.model_validate_json(FEEDBACK_NO_ITEMS_JSON)
        assert result.is_acceptable is True
        assert len(result.learning_items) == 0


class TestConvertToRawFeedback:
    def test_converts_correctly(self) -> None:
        llm_result = LLMFeedbackResult.model_validate_json(FEEDBACK_JSON)
        transcription = "I think this is [pause] very hard."

        raw = _convert_to_raw_feedback(llm_result, transcription)

        assert raw.user_utterance == transcription
        assert raw.model_answer == llm_result.model_answer
        assert raw.is_acceptable is False
        assert len(raw.items) == 2
        assert raw.items[0].pattern == "steep"
        assert raw.items[0].priority == 4

    def test_empty_items(self) -> None:
        llm_result = LLMFeedbackResult.model_validate_json(FEEDBACK_NO_ITEMS_JSON)
        raw = _convert_to_raw_feedback(llm_result, "test utterance")
        assert raw.items == ()

    def test_reappearance_preserved(self) -> None:
        llm_result = LLMFeedbackResult.model_validate_json(FEEDBACK_WITH_REAPPEARANCE_JSON)
        raw = _convert_to_raw_feedback(llm_result, "test")
        reapp = [i for i in raw.items if i.is_reappearance]
        assert len(reapp) == 1
        assert reapp[0].matched_stock_item_id == "si-008"
