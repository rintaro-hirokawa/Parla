"""Gemini-based overlapping lag detection adapter (LLM call #7).

Prompt design from verification/v9_overlapping_detection.
"""

import json

import litellm
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.domain.lag_detection import (
    DelayedPhrase,
    LagDetectionResult,
    LagPoint,
)

logger = structlog.get_logger()

# --- LLM output schema ---


class _PhraseFeedback(BaseModel):
    phrase: str
    delay_sec: float
    estimated_cause: str
    suggestion: str


class _LLMFeedback(BaseModel):
    delayed_phrases: list[_PhraseFeedback]
    overall_comment: str


# Exported for snapshot testing
LLMLagDetectionResult = _LLMFeedback

# --- Prompts (from V9 verification) ---

_SYSTEM_PROMPT = """\
You are an English pronunciation and fluency coach for Japanese learners.

You will receive:
1. An English passage (the reference text used in overlapping practice)
2. A list of phrases where the learner lagged behind the model audio, with delay times in seconds

Your task:
- For each delayed phrase, estimate the most likely cause from these categories:
  - "pronunciation_difficulty": unfamiliar sounds, consonant clusters, or long/uncommon words
  - "vocabulary_recall": less common words the learner may not have automatized yet
  - "syntactic_complexity": complex grammar structures (relative clauses, participial phrases, etc.) \
that slow real-time processing
  - "discourse_boundary": natural slowdown at sentence or clause boundaries (not a real problem)
- Provide a brief, encouraging suggestion for each phrase (1-2 sentences, in Japanese)
- Give an overall comment on the learner's overlapping performance (in Japanese, 2-3 sentences)

Important:
- Be encouraging and specific. Avoid vague feedback.
- If a delay is very small (< 0.5s), note it may be within normal variation.
- Focus on actionable advice the learner can practice.

Respond in the JSON format specified.\
"""

_USER_PROMPT_TEMPLATE = """\
## Reference Text
{passage_text}

## Delayed Phrases
{delayed_phrases_json}
"""


# --- Adapter ---


class GeminiOverlappingLagAdapter:
    """Detects lag causes in overlapping practice via Gemini."""

    def __init__(
        self,
        model: str = "gemini/gemini-3-flash-preview",
    ) -> None:
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def detect(
        self,
        passage_text: str,
        delayed_phrases: list[DelayedPhrase],
    ) -> LagDetectionResult:
        if not delayed_phrases:
            return LagDetectionResult(
                lag_points=(),
                overall_comment="遅れは検出されませんでした。素晴らしいパフォーマンスです！",
            )

        delayed_data = [
            {
                "phrase": p.phrase,
                "delay_sec": round(p.avg_delay_sec, 2),
                "word_indices": list(p.word_indices),
            }
            for p in delayed_phrases
        ]

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(
                    passage_text=passage_text,
                    delayed_phrases_json=json.dumps(delayed_data, ensure_ascii=False, indent=2),
                ),
            },
        ]

        logger.info(
            "llm_call_start",
            stage="overlapping_lag_detection",
            model=self._model,
            delayed_count=len(delayed_phrases),
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=_LLMFeedback,
        )

        raw = response.choices[0].message.content
        llm_result = _LLMFeedback.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            stage="overlapping_lag_detection",
            model=self._model,
            lag_count=len(llm_result.delayed_phrases),
        )

        lag_points = tuple(
            LagPoint(
                phrase=pf.phrase,
                delay_sec=pf.delay_sec,
                estimated_cause=pf.estimated_cause,  # type: ignore[arg-type]
                suggestion=pf.suggestion,
            )
            for pf in llm_result.delayed_phrases
        )

        return LagDetectionResult(
            lag_points=lag_points,
            overall_comment=llm_result.overall_comment,
        )
