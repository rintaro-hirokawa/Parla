"""V3: 意味的重複検出 — LLMクライアント (LiteLLM経由)."""

from __future__ import annotations

import litellm
from pydantic import ValidationError

from config import MAX_RETRIES
from models import FeedbackOutput, FocusedOutput


def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: type[FeedbackOutput] | type[FocusedOutput],
) -> FeedbackOutput | FocusedOutput:
    """LiteLLM経由でLLMを呼び出し、構造化出力を取得する."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for _ in range(MAX_RETRIES):
        response = litellm.completion(
            model=model,
            messages=messages,
            response_format=response_model,
        )
        raw_content = response.choices[0].message.content
        try:
            return response_model.model_validate_json(raw_content)
        except ValidationError as e:
            last_error = e

    msg = f"LLM出力のバリデーションに失敗しました（{MAX_RETRIES}回リトライ後）: {last_error}"
    raise ValueError(msg)
