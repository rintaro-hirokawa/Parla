"""V5: 検証設定."""

from dataclasses import dataclass


@dataclass
class V5Config:
    model: str = ""  # ← ここにモデル名を記入（例: "gemini/gemini-2.0-flash"）
    cefr_level: str = "B1"
    num_runs: int = 3  # 各テストケースの実行回数（中央値算出用）
    max_retries: int = 2  # バリデーション失敗時のリトライ回数
