"""V9: オーバーラッピング遅れ検知 — LLMフィードバック生成."""

from __future__ import annotations

import json
import time

import litellm
from pydantic import ValidationError

from config import LLM_MODEL, MAX_RETRIES
from models import LLMFeedback, PhraseDelay
from prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


def generate_feedback(
    passage_text: str,
    phrase_delays: list[PhraseDelay],
    model: str = LLM_MODEL,
) -> tuple[LLMFeedback, float]:
    """遅れ箇所データからLLMフィードバックを生成する.

    Returns:
        (LLMFeedback, latency_ms)
    """
    delayed_data = [
        {
            "phrase": p.phrase,
            "delay_sec": round(p.avg_delay_sec, 2),
            "word_indices": p.word_indices,
        }
        for p in phrase_delays
        if p.is_delayed
    ]

    if not delayed_data:
        return LLMFeedback(
            delayed_phrases=[],
            overall_comment="遅れは検出されませんでした。素晴らしいパフォーマンスです！",
        ), 0.0

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                passage_text=passage_text,
                delayed_phrases_json=json.dumps(delayed_data, ensure_ascii=False, indent=2),
            ),
        },
    ]

    last_error: Exception | None = None
    start = time.perf_counter()

    for attempt in range(MAX_RETRIES):
        print(f"    LLM呼び出し (試行 {attempt + 1}/{MAX_RETRIES})...")
        response = litellm.completion(
            model=model,
            messages=messages,
            response_format=LLMFeedback,
        )
        raw = response.choices[0].message.content
        try:
            result = LLMFeedback.model_validate_json(raw)
            latency_ms = (time.perf_counter() - start) * 1000
            return result, latency_ms
        except ValidationError as e:
            last_error = e
            print(f"    バリデーション失敗: {e}")

    msg = f"LLM出力のバリデーションに{MAX_RETRIES}回失敗: {last_error}"
    raise ValueError(msg)
