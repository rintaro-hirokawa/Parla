"""V2: 2段階パイプライン — 音声 → テキスト → フィードバック."""

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path

import litellm
from pydantic import ValidationError

from verification.v2_item_extraction.config import V2Config
from verification.v2_item_extraction.models import FeedbackResult, TranscriptionResult
from verification.v2_item_extraction.prompt import (
    STAGE1_SYSTEM_PROMPT,
    STAGE1_USER_PROMPT,
    STAGE2_SYSTEM_PROMPT,
    STAGE2_USER_PROMPT,
    format_reappearance_instructions,
    format_stock_items,
)

MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".ogg": "audio/ogg",
}


@dataclass
class Stage1Result:
    transcription: TranscriptionResult
    latency_seconds: float


@dataclass
class Stage2Result:
    feedback: FeedbackResult
    latency_seconds: float


@dataclass
class AnalysisResult:
    stage1: Stage1Result
    stage2: Stage2Result


def _encode_audio(audio_path: Path) -> tuple[str, str]:
    """音声ファイルをbase64エンコードし、(encoded_data, mime_type) を返す."""
    suffix = audio_path.suffix.lower()
    mime_type = MIME_TYPES.get(suffix)
    if mime_type is None:
        msg = f"未対応の音声形式: {suffix} (対応: {list(MIME_TYPES.keys())})"
        raise ValueError(msg)
    raw = audio_path.read_bytes()
    encoded = base64.b64encode(raw).decode("utf-8")
    return encoded, mime_type


def _parse_response(raw_content: str, model_class: type):
    """LLMレスポンスをパースする。model_validate_json → JSONフォールバック."""
    try:
        return model_class.model_validate_json(raw_content)
    except ValidationError:
        data = json.loads(raw_content)
        return model_class.model_validate(data)


def transcribe(
    audio_path: Path,
    ja_prompt: str,
    config: V2Config,
) -> Stage1Result:
    """Stage 1: 音声 → ユーザー発話テキスト."""
    encoded_data, mime_type = _encode_audio(audio_path)

    system_prompt = STAGE1_SYSTEM_PROMPT.format(ja_prompt=ja_prompt)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": STAGE1_USER_PROMPT},
                {
                    "type": "file",
                    "file": {
                        "file_data": f"data:{mime_type};base64,{encoded_data}",
                    },
                },
            ],
        },
    ]

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        start = time.perf_counter()
        response = litellm.completion(
            model=config.stage1_model,
            messages=messages,
            response_format=TranscriptionResult,
        )
        elapsed = time.perf_counter() - start

        raw_content = response.choices[0].message.content
        try:
            result = _parse_response(raw_content, TranscriptionResult)
            return Stage1Result(transcription=result, latency_seconds=elapsed)
        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            print(f"  Stage 1 バリデーション失敗 (試行 {attempt + 1}): {e}")

    msg = f"Stage 1 が{config.max_retries}回失敗: {last_error}"
    raise ValueError(msg)


def generate_feedback(
    user_utterance: str,
    ja_prompt: str,
    stock_items: list[dict],
    config: V2Config,
) -> Stage2Result:
    """Stage 2: テキスト → フィードバック."""
    system_prompt = STAGE2_SYSTEM_PROMPT.format(
        cefr_level=config.cefr_level,
        english_variant=config.english_variant,
        ja_prompt=ja_prompt,
        user_utterance=user_utterance,
        stock_items_section=format_stock_items(stock_items),
        reappearance_instructions=format_reappearance_instructions(stock_items),
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": STAGE2_USER_PROMPT},
    ]

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        start = time.perf_counter()
        response = litellm.completion(
            model=config.stage2_model,
            messages=messages,
            response_format=FeedbackResult,
        )
        elapsed = time.perf_counter() - start

        raw_content = response.choices[0].message.content
        try:
            result = _parse_response(raw_content, FeedbackResult)
            return Stage2Result(feedback=result, latency_seconds=elapsed)
        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            print(f"  Stage 2 バリデーション失敗 (試行 {attempt + 1}): {e}")

    msg = f"Stage 2 が{config.max_retries}回失敗: {last_error}"
    raise ValueError(msg)


def analyze(
    audio_path: Path,
    ja_prompt: str,
    stock_items: list[dict],
    config: V2Config,
) -> AnalysisResult:
    """2段階パイプライン統合: Stage 1 → Stage 2."""
    stage1 = transcribe(audio_path, ja_prompt, config)
    print(f"  Stage 1 完了: \"{stage1.transcription.user_utterance}\" ({stage1.latency_seconds:.1f}s)")

    stage2 = generate_feedback(
        user_utterance=stage1.transcription.user_utterance,
        ja_prompt=ja_prompt,
        stock_items=stock_items,
        config=config,
    )
    print(f"  Stage 2 完了: {len(stage2.feedback.learning_items)}項目抽出 ({stage2.latency_seconds:.1f}s)")

    return AnalysisResult(stage1=stage1, stage2=stage2)
