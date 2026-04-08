"""V11: 検証設定."""

import os
from dataclasses import dataclass


@dataclass
class V11Config:
    cefr_level: str = "B1"
    num_runs: int = 3
    language: str = "en-US"
    # LLM（paraphrase/error 判定用、最小限）
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_reasoning_effort: str = "minimal"
    llm_max_retries: int = 2
    # diff 判定閾値
    correct_threshold: float = 0.90  # SequenceMatcher ratio >= これなら correct
    error_threshold: float = 0.50  # ratio < これなら error


def get_azure_speech_key() -> str:
    key = os.environ.get("AZURE_SPEECH_KEY", "")
    if not key:
        raise ValueError("AZURE_SPEECH_KEY 環境変数を設定してください")
    return key


def get_azure_speech_region() -> str:
    region = os.environ.get("AZURE_SPEECH_REGION", "")
    if not region:
        raise ValueError("AZURE_SPEECH_REGION 環境変数を設定してください")
    return region
