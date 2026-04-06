
``` python
import os

import litellm
from pydantic import ValidationError

from catapult_core.config import MaterialGenerationConfig
from catapult_core.models import MaterialContent

SYSTEM_PROMPT_TEMPLATE = """\
You are an expert English language educator specializing in creating high-quality \
Q&A materials for Japanese learners of English.

Target CEFR level: {cefr_level}
English variant: {english_variant}

Your task is to generate Q&A-style study materials based on a source text provided by the user. \
The materials should simulate a scenario where the learner explains the content of the source text \
to a third party in English.

Guidelines:
- Generate 6 to 8 Q&A sets (turns). If the source text is too short or lacks enough substance, \
reduce the number of sets accordingly (minimum 1).
- Each question should be 10-20 words long. Each answer should be approximately 100 words.
- For each set, produce BOTH Japanese (question_ja, answer_ja) and English (question_en, answer_en).
- Incorporate vocabulary and diverse grammar structures that are educationally valuable \
for second-language learners at the {cefr_level} level.
- Design the English text first for maximum educational value, then reverse-engineer \
appropriate Japanese questions and answers.
- Use {english_variant} spelling and expressions consistently.\
"""

USER_PROMPT_TEMPLATE = """\
以下のテキストを元に、Q&A形式の英語学習教材を生成してください。

--- Source Text ---
{source_text}
--- End of Source Text ---\
"""

MAX_RETRIES = 2


class LLMClient:
    """LiteLLM経由で複数LLMプロバイダーに統一的にアクセスする."""

    def __init__(self, config: MaterialGenerationConfig) -> None:
        self._setup_langfuse(config)

    def _setup_langfuse(self, config: MaterialGenerationConfig) -> None:
        langfuse = config.langfuse
        if langfuse.enabled and langfuse.public_key and langfuse.secret_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse.public_key
            os.environ["LANGFUSE_SECRET_KEY"] = langfuse.secret_key
            os.environ["LANGFUSE_HOST"] = langfuse.host
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]

    def generate_material(
        self,
        source_text: str,
        config: MaterialGenerationConfig,
    ) -> MaterialContent:
        """プロンプトを構築し、LLMを呼び出して構造化出力を取得する."""
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(
                    cefr_level=config.cefr_level,
                    english_variant=config.english_variant,
                ),
            },
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(source_text=source_text),
            },
        ]

        last_error: Exception | None = None
        for _ in range(MAX_RETRIES):
            response = litellm.completion(
                model=config.llm_model,
                messages=messages,
                response_format=MaterialContent,
            )
            raw_content = response.choices[0].message.content
            try:
                return MaterialContent.model_validate_json(raw_content)
            except ValidationError as e:
                last_error = e

        msg = f"LLM出力のバリデーションに失敗しました（{MAX_RETRIES}回リトライ後）: {last_error}"
        raise ValueError(msg)
```
