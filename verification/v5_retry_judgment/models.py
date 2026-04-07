"""V5: リトライ判定の出力スキーマ."""

from pydantic import BaseModel


class RetryJudgmentResult(BaseModel):
    """LLM #5 の出力."""

    correct: bool
    reason: str  # 日本語15文字以内
