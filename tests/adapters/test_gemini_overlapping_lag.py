"""Snapshot tests for GeminiOverlappingLagAdapter's LLM output parsing."""

from parla.adapters.gemini_overlapping_lag import LLMLagDetectionResult

# Based on V9 verification outputs

SINGLE_DELAY_JSON = """\
{
  "delayed_phrases": [
    {
      "phrase": "establish a connection",
      "delay_sec": 0.8,
      "estimated_cause": "vocabulary_recall",
      "suggestion": "establish は日常会話ではあまり使わない単語なので、音読で口に馴染ませましょう。"
    }
  ],
  "overall_comment": "全体的にスムーズなオーバーラッピングでした。練習を重ねれば解消できます。"
}
"""

MULTIPLE_DELAYS_JSON = """\
{
  "delayed_phrases": [
    {
      "phrase": "The chairman",
      "delay_sec": 0.45,
      "estimated_cause": "discourse_boundary",
      "suggestion": "文頭の少しの遅れは自然なものです。気にしなくて大丈夫です。"
    },
    {
      "phrase": "tested himself",
      "delay_sec": 0.72,
      "estimated_cause": "pronunciation_difficulty",
      "suggestion": "tested の -ed と himself の h の連結が難しいポイントです。ゆっくり繰り返し練習してみましょう。"
    }
  ],
  "overall_comment": "2箇所の遅れが検出されました。発音面での改善点を意識して練習を続けましょう。"
}
"""

NO_DELAYS_JSON = """\
{
  "delayed_phrases": [],
  "overall_comment": "遅れは検出されませんでした。素晴らしいパフォーマンスです！"
}
"""

SYNTACTIC_DELAY_JSON = """\
{
  "delayed_phrases": [
    {
      "phrase": "which had been carefully prepared",
      "delay_sec": 1.2,
      "estimated_cause": "syntactic_complexity",
      "suggestion": "関係代名詞節が長いため処理に時間がかかっています。この構文を含む短い文から練習するとよいでしょう。"
    }
  ],
  "overall_comment": "複雑な構文で遅れが出ましたが、これは上達の過程で自然なことです。構文を意識した音読が効果的です。"
}
"""


class TestLagDetectionParsing:
    def test_single_delay(self) -> None:
        result = LLMLagDetectionResult.model_validate_json(SINGLE_DELAY_JSON)
        assert len(result.delayed_phrases) == 1
        assert result.delayed_phrases[0].estimated_cause == "vocabulary_recall"
        assert result.delayed_phrases[0].delay_sec == 0.8

    def test_multiple_delays(self) -> None:
        result = LLMLagDetectionResult.model_validate_json(MULTIPLE_DELAYS_JSON)
        assert len(result.delayed_phrases) == 2
        causes = {p.estimated_cause for p in result.delayed_phrases}
        assert "discourse_boundary" in causes
        assert "pronunciation_difficulty" in causes

    def test_no_delays(self) -> None:
        result = LLMLagDetectionResult.model_validate_json(NO_DELAYS_JSON)
        assert len(result.delayed_phrases) == 0
        assert "素晴らしい" in result.overall_comment

    def test_syntactic_complexity(self) -> None:
        result = LLMLagDetectionResult.model_validate_json(SYNTACTIC_DELAY_JSON)
        assert result.delayed_phrases[0].estimated_cause == "syntactic_complexity"
        assert result.delayed_phrases[0].delay_sec > 1.0

    def test_overall_comment_present(self) -> None:
        for json_str in [SINGLE_DELAY_JSON, MULTIPLE_DELAYS_JSON, NO_DELAYS_JSON, SYNTACTIC_DELAY_JSON]:
            result = LLMLagDetectionResult.model_validate_json(json_str)
            assert len(result.overall_comment) > 0
