"""V1: LiteLLM呼び出し + バリデーション."""

import litellm
from pydantic import ValidationError

from verification.v1_passage_generation.config import V1Config
from verification.v1_passage_generation.models import PassageGenerationResult
from verification.v1_passage_generation.prompt import (
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)


def generate_passages(source_text: str, config: V1Config) -> PassageGenerationResult:
    """ソーステキストからパッセージを生成する."""
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT_TEMPLATE.format(
                cefr_level=config.cefr_level,
                english_variant=config.english_variant,
                passage_type=config.passage_type,
            ),
        },
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(source_text=source_text),
        },
    ]

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        print(f"  LLM呼び出し (試行 {attempt + 1}/{config.max_retries})...")
        response = litellm.completion(
            model=config.model,
            messages=messages,
            response_format=PassageGenerationResult,
        )
        raw_content = response.choices[0].message.content
        try:
            return PassageGenerationResult.model_validate_json(raw_content)
        except ValidationError as e:
            last_error = e
            print(f"  バリデーション失敗: {e}")

    msg = f"LLM出力のバリデーションに{config.max_retries}回失敗: {last_error}"
    raise ValueError(msg)
