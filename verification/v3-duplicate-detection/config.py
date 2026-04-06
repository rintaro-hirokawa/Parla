"""V3: 意味的重複検出 — 設定."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
TEST_DATA_DIR = BASE_DIR / "test_data"
RESULTS_DIR = BASE_DIR / "results"

DEFAULT_MODEL = "gemini/gemini-3-flash-preview"
MAX_RETRIES = 2

# LiteLLM は GEMINI_API_KEY 環境変数を自動で参照する
def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY 環境変数を設定してください")
    return key
