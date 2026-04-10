"""Snapshot tests for GeminiVariationAdapter's LLM output parsing.

Tests the internal LLM schema parsing and conversion to RawVariation,
using fixture data modeled after V7 verification outputs.
"""

from parla.adapters.gemini_variation import LLMVariationResult
from parla.ports.variation_generation import RawVariation

VARIATION_JSON = """{
    "learning_item": "be responsible for ~ing",
    "source_summary": "AI technology in everyday life",
    "variation": {
        "ja": "この会社はAIシステムの安全性を確保する責任を負っています。",
        "en": "This company is responsible for ensuring the safety of AI systems.",
        "grammar": {
            "sentence_type": "declarative",
            "polarity": "affirmative",
            "voice": "active",
            "tense_aspect": "present_simple",
            "modality": "none",
            "clause_type": "simple",
            "info_structure": "canonical"
        },
        "hints": {
            "hint1": "This company ... responsible / ensuring",
            "hint2": "主語 + be動詞 + responsible for + 動名詞 + 目的語"
        }
    }
}"""


class TestLLMVariationParsing:
    def test_parse_valid_json(self) -> None:
        result = LLMVariationResult.model_validate_json(VARIATION_JSON)
        assert result.learning_item == "be responsible for ~ing"
        assert result.variation.ja.startswith("この会社は")
        assert "responsible for ensuring" in result.variation.en
        assert result.variation.grammar.sentence_type == "declarative"
        assert result.variation.hints.hint1.startswith("This company")
        assert "動名詞" in result.variation.hints.hint2

    def test_convert_to_raw_variation(self) -> None:
        result = LLMVariationResult.model_validate_json(VARIATION_JSON)
        raw = RawVariation(
            ja=result.variation.ja,
            en=result.variation.en,
            hint1=result.variation.hints.hint1,
            hint2=result.variation.hints.hint2,
        )
        assert raw.ja == result.variation.ja
        assert raw.en == result.variation.en
        assert raw.hint1 == result.variation.hints.hint1
        assert raw.hint2 == result.variation.hints.hint2


VARIATION_WITH_HISTORY_JSON = """{
    "learning_item": "take into account",
    "source_summary": "Environmental policy discussion",
    "variation": {
        "ja": "AIを教室で使う前に考慮すべき倫理的な問題がたくさんあります。",
        "en": "There are many ethical concerns that must be taken into account before AI is used in classrooms.",
        "grammar": {
            "sentence_type": "declarative",
            "polarity": "affirmative",
            "voice": "passive",
            "tense_aspect": "present_simple",
            "modality": "obligation",
            "clause_type": "relative",
            "info_structure": "there_construction"
        },
        "hints": {
            "hint1": "There ... ethical / taken into account",
            "hint2": "There + be動詞 + 名詞 + 関係代名詞 + must be + 過去分詞 + 前置詞句"
        }
    }
}"""


class TestHistoryBasedVariation:
    """V7 Phase C: history-based method produces diverse grammar."""

    def test_passive_voice_variation(self) -> None:
        result = LLMVariationResult.model_validate_json(VARIATION_WITH_HISTORY_JSON)
        assert result.variation.grammar.voice == "passive"
        assert result.variation.grammar.info_structure == "there_construction"
        assert "taken into account" in result.variation.en
