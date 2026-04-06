"""V5: 音声送信 + LLM判定 + レイテンシ計測."""

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path

import litellm
from pydantic import ValidationError

from verification.v5_retry_judgment.config import V5Config
from verification.v5_retry_judgment.models import RetryJudgmentResult
from verification.v5_retry_judgment.prompt import (
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)


MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".ogg": "audio/ogg",
}


@dataclass
class JudgmentWithLatency:
    result: RetryJudgmentResult
    latency_seconds: float


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


def judge_audio(
    audio_path: Path,
    learning_item: str,
    ja_prompt: str,
    reference_answer: str,
    config: V5Config,
) -> JudgmentWithLatency:
    """音声ファイルに対してLLM #5を実行し、判定結果とレイテンシを返す."""
    encoded_data, mime_type = _encode_audio(audio_path)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        learning_item=learning_item,
        cefr_level=config.cefr_level,
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        ja_prompt=ja_prompt,
        reference_answer=reference_answer,
        learning_item=learning_item,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
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
            model=config.model,
            messages=messages,
            response_format=RetryJudgmentResult,
        )
        elapsed = time.perf_counter() - start

        raw_content = response.choices[0].message.content
        try:
            result = RetryJudgmentResult.model_validate_json(raw_content)
            return JudgmentWithLatency(result=result, latency_seconds=elapsed)
        except ValidationError as e:
            last_error = e
            # response_format が効かない場合のフォールバック: JSONを手動抽出
            try:
                data = json.loads(raw_content)
                result = RetryJudgmentResult.model_validate(data)
                return JudgmentWithLatency(result=result, latency_seconds=elapsed)
            except (json.JSONDecodeError, ValidationError):
                pass
            print(f"  バリデーション失敗 (試行 {attempt + 1}): {e}")

    msg = f"LLM出力のバリデーションに{config.max_retries}回失敗: {last_error}"
    raise ValueError(msg)
