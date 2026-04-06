"""V3: 意味的重複検出 — Pydantic モデル定義."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# --- テストデータ用 ---


class StockItem(BaseModel):
    item_id: str
    pattern: str
    category: str
    sub_tag: str
    example_sentence: str


class DuplicatePairCase(BaseModel):
    case_id: str
    case_type: Literal["duplicate"]
    target_pattern: str
    expected_match_stock_id: str | None
    description: str


class NonDuplicatePairCase(BaseModel):
    case_id: str
    case_type: Literal["non_duplicate"]
    target_pattern: str
    nearest_stock_id: str | None
    description: str


class ReappearanceCase(BaseModel):
    case_id: str
    case_type: Literal["reappearance"]
    target_pattern: str
    expected_match_stock_id: str
    description: str


class Scenario(BaseModel):
    scenario_id: str
    case_ids: list[str]
    japanese_prompt: str
    model_answer: str
    user_utterance_text: str
    cefr_level: str
    english_variant: str
    passage_context: str


# --- LLM 出力用 ---


class ExtractedItem(BaseModel):
    """LLM #4 が抽出する学習項目."""

    pattern: str
    category: str
    sub_tag: str
    is_reappearance: bool
    matched_stock_item_id: str | None = None
    confidence: float
    default_action: Literal["auto_stock", "review_later"]
    reasoning: str = ""


class FeedbackOutput(BaseModel):
    """LLM #4 の出力（戦略A: フルシミュレーション）."""

    utterance_reproduction: str
    dynamic_model_answer: str
    learning_items: list[ExtractedItem]


class DuplicateJudgment(BaseModel):
    """戦略B: 重複検出特化の出力."""

    new_pattern: str
    is_duplicate: bool
    matched_stock_item_id: str | None = None
    confidence: float
    reasoning: str


class FocusedOutput(BaseModel):
    """戦略B: 重複検出特化の全体出力."""

    judgments: list[DuplicateJudgment]


# --- 実験結果用 ---


class ExperimentResult(BaseModel):
    case_id: str
    case_type: str
    stock_size: int
    run_number: int
    strategy: str
    expected_judgment: str
    actual_judgment: str
    matched_stock_id: str | None
    is_correct: bool
    confidence: float | None
    reasoning: str
    latency_ms: float
    model: str
    timestamp: str
