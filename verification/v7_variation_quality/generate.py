"""V7: LiteLLM呼び出し + バリデーション."""

import litellm
from pydantic import ValidationError

from verification.v7_variation_quality.config import V7Config
from verification.v7_variation_quality.models import VariationResult
from verification.v7_variation_quality.prompt import (
    SYSTEM_PROMPT_BASE,
    USER_PROMPT_BASIC,
    USER_PROMPT_WITH_CONSTRAINTS,
    USER_PROMPT_WITH_HISTORY,
    format_constraints,
    format_history,
)


def generate_variation(
    learning_item: str,
    source_text: str,
    config: V7Config,
    history: list[dict] | None = None,
    constraints: dict[str, str] | None = None,
) -> VariationResult:
    """類題を1件生成する."""
    system_content = SYSTEM_PROMPT_BASE.format(
        cefr_level=config.cefr_level,
        english_variant=config.english_variant,
    )

    if constraints:
        user_content = USER_PROMPT_WITH_CONSTRAINTS.format(
            learning_item=learning_item,
            source_text=source_text,
            constraints=format_constraints(constraints),
        )
    elif history:
        user_content = USER_PROMPT_WITH_HISTORY.format(
            learning_item=learning_item,
            source_text=source_text,
            history=format_history(history),
        )
    else:
        user_content = USER_PROMPT_BASIC.format(
            learning_item=learning_item,
            source_text=source_text,
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    last_error: Exception | None = None
    for attempt in range(config.max_retries):
        print(f"    LLM呼び出し (試行 {attempt + 1}/{config.max_retries})...")
        response = litellm.completion(
            model=config.model,
            messages=messages,
            response_format=VariationResult,
        )
        raw_content = response.choices[0].message.content
        try:
            return VariationResult.model_validate_json(raw_content)
        except ValidationError as e:
            last_error = e
            print(f"    バリデーション失敗: {e}")

    msg = f"LLM出力のバリデーションに{config.max_retries}回失敗: {last_error}"
    raise ValueError(msg)
