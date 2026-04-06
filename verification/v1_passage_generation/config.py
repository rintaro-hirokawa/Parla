"""V1: 検証設定."""

from dataclasses import dataclass


@dataclass
class V1Config:
    model: str = "gemini/gemini-3.1-pro-preview"  # ← ここにモデル名を記入（例: "gemini/gemini-2.0-flash"）
    cefr_level: str = "B1"
    english_variant: str = "American English"
    passage_type: str = "説明型"
    max_retries: int = 2
