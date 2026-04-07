"""V9: オーバーラッピング遅れ検知 — 設定."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
REFERENCE_AUDIO_DIR = AUDIO_DIR / "reference"
SIMULATED_AUDIO_DIR = AUDIO_DIR / "simulated"
OUTPUTS_DIR = BASE_DIR / "outputs"

V1_OUTPUTS_DIR = BASE_DIR.parent / "v1_passage_generation" / "outputs"

# ElevenLabs Voice IDs
REFERENCE_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George (male)
SIMULATED_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah (female)
DIFFERENT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"  # Daniel (male, British)

TTS_MODEL_ID = "eleven_multilingual_v2"

# 速度設定
DEFAULT_SPEED = 1.0
SLOW_SPEED = 0.85
SLOW_PHRASE_SPEED = 0.7
FAST_SPEED = 1.15

# 遅れ検知パラメータ
DELAY_THRESHOLD_SEC = 0.3
PHRASE_WINDOW_WORDS = 3
LOSS_THRESHOLD = 0.5

# LLM
LLM_MODEL = "gemini/gemini-3-flash-preview"
MAX_RETRIES = 2


# Azure Speech Service
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


def get_elevenlabs_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise ValueError("ELEVENLABS_API_KEY 環境変数を設定してください")
    return key


def get_gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY 環境変数を設定してください")
    return key
