"""V11: 出力スキーマ定義."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Azure 認識結果 ---


class RecognizedWord(BaseModel):
    """Azure から返る単語レベル結果."""

    word: str
    accuracy_score: float = 0.0
    error_type: str = "None"  # None / Omission / Insertion / Mispronunciation
    offset_sec: float = -1.0
    duration_sec: float = 0.0


class AzureResult(BaseModel):
    """Azure Pronunciation Assessment の全体結果."""

    recognized_words: list[RecognizedWord]
    recognized_text: str
    accuracy_score: float = 0.0
    fluency_score: float = 0.0
    completeness_score: float = 0.0
    pronunciation_score: float = 0.0
    latency_seconds: float = 0.0


# --- 添削結果 ---


class DiffSegment(BaseModel):
    """差分箇所."""

    user_part: str = Field(description="ユーザーが言った部分（空文字列 = 欠落）")
    model_part: str = Field(description="模範の対応部分（空文字列 = 挿入）")
    note: str = Field(description="日本語の短い説明")


class SentenceResult(BaseModel):
    """1文の添削結果."""

    index: int
    status: str  # "correct" | "paraphrase" | "error"
    user_text: str
    model_text: str
    diff_segments: list[DiffSegment] = Field(default_factory=list)
    similarity: float = 0.0  # SequenceMatcher ratio


class PassageEvaluation(BaseModel):
    """パッセージ全体の添削結果."""

    passed: bool
    sentences: list[SentenceResult]
    azure: AzureResult
