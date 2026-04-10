"""Gemini-based retry judgment adapter.

Ultra-simple prompt with reasoning_effort=minimal.
Design from verification/v5_retry_judgment.
"""

import base64

import litellm
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.domain.feedback import RetryResult

logger = structlog.get_logger()

# --- LLM output schema ---


class _LLMRetryJudgment(BaseModel):
    correct: bool
    reason: str


# Exported for snapshot testing
LLMRetryJudgmentResult = _LLMRetryJudgment

# --- Prompts (migrated from verification/v5_retry_judgment/prompt.py) ---

_SYSTEM_PROMPT = """\
音声がターゲット文と一致しているか判定せよ。
許容: 冠詞(a/an/the)の欠落・誤用、三単現-sの欠落、短縮形(I'll=I will)。
不一致: 上記以外の単語の違い、語の欠落、日本語の混入、文の未完成。
出力: JSON {{"correct": bool, "reason": "日本語15文字以内"}}\
"""

_USER_PROMPT_TEMPLATE = """\
ターゲット文: {reference_answer}\
"""

_MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mp3",
    "m4a": "audio/m4a",
    "ogg": "audio/ogg",
}


# --- Adapter ---


class GeminiRetryJudgmentAdapter:
    """Judges retry utterances against reference answers via Gemini.

    Uses reasoning_effort=minimal for speed (V5: median 2.37s).
    """

    def __init__(
        self,
        model: str = "gemini/gemini-3-flash-preview",
        reasoning_effort: str = "minimal",
    ) -> None:
        self._model = model
        self._reasoning_effort = reasoning_effort

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        reference_answer: str,
    ) -> RetryResult:
        encoded = base64.b64encode(audio_data).decode("utf-8")
        mime_type = _MIME_TYPES.get(audio_format, f"audio/{audio_format}")

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _USER_PROMPT_TEMPLATE.format(
                            reference_answer=reference_answer,
                        ),
                    },
                    {
                        "type": "file",
                        "file": {
                            "file_data": f"data:{mime_type};base64,{encoded}",
                        },
                    },
                ],
            },
        ]

        logger.info(
            "llm_call_start",
            stage="retry_judgment",
            model=self._model,
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=_LLMRetryJudgment,
            reasoning_effort=self._reasoning_effort,
        )

        raw = response.choices[0].message.content
        llm_result = _LLMRetryJudgment.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            stage="retry_judgment",
            model=self._model,
            correct=llm_result.correct,
        )

        return RetryResult(
            correct=llm_result.correct,
            reason=llm_result.reason,
        )
