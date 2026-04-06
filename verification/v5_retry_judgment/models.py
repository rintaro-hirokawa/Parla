"""V5: リトライ判定の出力スキーマ."""

from pydantic import BaseModel


class RetryJudgmentResult(BaseModel):
    """LLM #5 の出力（12-evaluation-criteria.md 準拠）."""

    correct: bool
    reason: str  # 20語以内
    item_used: bool
