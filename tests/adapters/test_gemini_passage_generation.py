"""Snapshot tests for GeminiPassageGenerationAdapter.

Tests the LLM response → domain model conversion logic without calling the LLM.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from parla.adapters.gemini_passage_generation import (
    LLMPassageResult,
    convert_to_domain,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def llm_response() -> dict[str, object]:
    with (FIXTURES_DIR / "passage_generation_response.json").open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class TestLLMResponseParsing:
    def test_parse_valid_response(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        assert len(result.passages) == 6

    def test_each_passage_has_sentences(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        for passage in result.passages:
            assert len(passage.sentences) >= 1

    def test_each_sentence_has_hints(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        for passage in result.passages:
            for sentence in passage.sentences:
                assert sentence.hints.hint1
                assert sentence.hints.hint2


class TestConvertToDomain:
    def test_converts_all_passages(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        source_id = uuid4()
        passages = convert_to_domain(result, source_id)
        assert len(passages) == 6

    def test_sets_source_id(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        source_id = uuid4()
        passages = convert_to_domain(result, source_id)
        for p in passages:
            assert p.source_id == source_id

    def test_passage_order_is_zero_based(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        passages = convert_to_domain(result, uuid4())
        orders = [p.order for p in passages]
        assert orders == list(range(6))

    def test_sentence_order_is_zero_based(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        passages = convert_to_domain(result, uuid4())
        for passage in passages:
            orders = [s.order for s in passage.sentences]
            assert orders == list(range(len(passage.sentences)))

    def test_preserves_japanese_and_english(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        passages = convert_to_domain(result, uuid4())
        first_sentence = passages[0].sentences[0]
        assert first_sentence.ja
        assert first_sentence.en

    def test_preserves_hints(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        passages = convert_to_domain(result, uuid4())
        first_sentence = passages[0].sentences[0]
        assert first_sentence.hints.hint1
        assert first_sentence.hints.hint2

    def test_passages_are_frozen(self, llm_response: dict[str, object]) -> None:
        result = LLMPassageResult.model_validate(llm_response)
        passages = convert_to_domain(result, uuid4())
        with pytest.raises(Exception):  # noqa: B017
            passages[0].topic = "changed"  # type: ignore[misc]


class TestInvalidResponses:
    def test_empty_passages_fails(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            LLMPassageResult.model_validate({"source_summary": "x", "passages": []})

    def test_missing_hints_fails(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            LLMPassageResult.model_validate(
                {
                    "source_summary": "x",
                    "passages": [
                        {
                            "passage_index": 1,
                            "topic": "t",
                            "passage_type": "説明型",
                            "sentences": [{"ja": "a", "en": "b"}],
                        }
                    ],
                }
            )
