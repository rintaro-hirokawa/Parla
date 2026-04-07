"""V2: 出力スキーマ定義."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Stage 1: 音声 → テキスト ---


class TranscriptionResult(BaseModel):
    """Stage 1 の出力: ユーザー発話の書き起こし."""

    user_utterance: str


# --- Stage 2: テキスト → フィードバック ---

VALID_CATEGORIES = ("文法", "語彙", "コロケーション", "構文", "表現")

SUBTAGS_BY_CATEGORY: dict[str, list[str]] = {
    "文法": [
        "時制", "比較", "関係詞", "仮定法", "受動態",
        "不定詞", "動名詞", "分詞", "助動詞", "冠詞", "前置詞", "接続詞",
    ],
    "語彙": ["名詞", "動詞", "形容詞", "副詞", "その他"],
    "コロケーション": [],
    "構文": [],
    "表現": [],
}


class LearningItem(BaseModel):
    """抽出された学習項目（フル仕様）."""

    pattern: str = Field(description="具体的パターン（例: 'A is more X than B'）")
    explanation: str = Field(description="日本語での説明（パターン解説 + 1-2例文）")
    category: Literal["文法", "語彙", "コロケーション", "構文", "表現"]
    sub_tag: str = Field(default="", description="カテゴリ別の固定サブタグ")
    priority: int = Field(ge=2, le=5, description="習得優先度（5=最優先, 2=余裕があれば）")
    is_reappearance: bool = Field(default=False, description="ストック済み項目の再出か")
    matched_stock_item_id: str | None = Field(
        default=None,
        description="再出の場合、マッチしたストック項目のID",
    )


class FeedbackResult(BaseModel):
    """Stage 2 の出力: フィードバック."""

    model_answer: str = Field(description="ユーザー発話を活かした模範英文")
    is_acceptable: bool = Field(description="CEFRレベルに対して許容可能か")
    learning_items: list[LearningItem] = Field(
        default_factory=list,
        description="学習項目（0-3個）",
    )
