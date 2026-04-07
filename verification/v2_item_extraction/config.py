"""V2: 検証設定."""

from dataclasses import dataclass


@dataclass
class V2Config:
    stage1_model: str = "gemini/gemini-3.1-flash-lite-preview"  # 音声テキスト化（例: "gemini/gemini-3.1-pro-preview"）
    stage2_model: str = "gemini/gemini-3-flash-preview"  # フィードバック生成（例: "gemini/gemini-3.1-pro-preview"）
    cefr_level: str = "B1"
    english_variant: str = "American English"
    max_retries: int = 2
