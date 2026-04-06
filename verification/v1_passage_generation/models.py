"""V1: パッセージ生成の出力スキーマ."""

from pydantic import BaseModel


class Hint(BaseModel):
    """2段階ヒント（07-hint-system.md準拠）."""

    hint1: str  # はじめの1語 + 学習者が出てきにくい単語
    hint2: str  # 構文スケルトン + 学習者が出てきにくい単語


class Sentence(BaseModel):
    """パッセージ内の1センテンス."""

    ja: str
    en: str
    hints: Hint


class Passage(BaseModel):
    """1パッセージ（約100語、5〜8文）."""

    passage_index: int
    topic: str
    passage_type: str  # "説明型" | "対話型" | "意見型"
    sentences: list[Sentence]


class PassageGenerationResult(BaseModel):
    """LLM #1 の出力全体."""

    source_summary: str
    passages: list[Passage]
