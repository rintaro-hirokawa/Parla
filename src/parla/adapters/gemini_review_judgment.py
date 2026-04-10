"""Gemini-based review judgment adapter (2-stage pipeline).

Stage 1: Audio → Transcription (Flash Lite)
Stage 2: Transcription + Context → Judgment (Flash)

Judges whether the target learning item pattern was used correctly.
Based on 12-evaluation-criteria.md Block 1/3 template.
"""

import base64

import litellm
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.adapters.audio_formats import MIME_TYPES as _MIME_TYPES
from parla.domain.review import ReviewResult

logger = structlog.get_logger()

# --- LLM output schemas ---


class _LLMTranscription(BaseModel):
    user_utterance: str


class _LLMReviewJudgment(BaseModel):
    correct: bool
    item_used: bool
    reason: str


# Exported for snapshot testing
LLMTranscriptionResult = _LLMTranscription
LLMReviewJudgmentResult = _LLMReviewJudgment


# --- Prompts ---

_STAGE1_SYSTEM_PROMPT = """\
You are a speech transcription assistant. Transcribe the learner's English speech \
as accurately as possible.

Rules:
- Transcribe exactly what was said, including hesitations and errors
- If the learner switches to Japanese, include it in parentheses: (日本語部分)
- If parts are unclear, use [...] to mark them
- If there is no speech or only noise, return an empty string for user_utterance\
"""

_STAGE1_USER_PROMPT = """\
Transcribe this audio recording of a learner speaking English.\
"""

_STAGE2_SYSTEM_PROMPT = """\
あなたは英語学習の判定を行うアシスタントです。

学習者の発話を以下の基準で判定してください:

1. 対象の学習項目「{target_pattern}」が適切に使われているか → 最重要
2. 模範解答の意味内容がおおむねカバーされているか
3. 英語として意味が通じるか

許容: 学習項目以外の部分の言い換え、冠詞の間違い、語順の軽微な違い
不合格: 対象学習項目の不使用、意味が大きく異なる

出力:
- correct: 総合判定（trueなら正解）
- item_used: 学習項目が使われたか
- reason: 日本語20文字以内の理由\
"""

_STAGE2_USER_PROMPT = """\
学習項目: {target_pattern}
模範解答: {reference_answer}
日本語お題: {ja_prompt}
学習者の発話: {user_utterance}\
"""


# --- Adapter ---


class GeminiReviewJudgmentAdapter:
    """Judges Block 1/3 review utterances via Gemini 2-stage pipeline.

    Stage 1 (Flash Lite): Audio → text transcription
    Stage 2 (Flash): Text → judgment (is the learning item used?)
    """

    def __init__(
        self,
        transcription_model: str = "gemini/gemini-3-flash-lite-preview",
        judgment_model: str = "gemini/gemini-3-flash-preview",
    ) -> None:
        self._transcription_model = transcription_model
        self._judgment_model = judgment_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        target_pattern: str,
        reference_answer: str,
        ja_prompt: str,
        cefr_level: str,
    ) -> ReviewResult:
        """Judge a review utterance via 2-stage pipeline."""
        # Stage 1: Transcribe audio
        transcription = await self._transcribe(audio_data, audio_format)

        # Stage 2: Judge transcription against learning item
        return await self._judge(
            user_utterance=transcription,
            target_pattern=target_pattern,
            reference_answer=reference_answer,
            ja_prompt=ja_prompt,
        )

    async def _transcribe(self, audio_data: bytes, audio_format: str) -> str:
        encoded = base64.b64encode(audio_data).decode("utf-8")
        mime_type = _MIME_TYPES.get(audio_format, f"audio/{audio_format}")

        messages = [
            {"role": "system", "content": _STAGE1_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _STAGE1_USER_PROMPT},
                    {
                        "type": "file",
                        "file": {"file_data": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            },
        ]

        logger.info(
            "llm_call_start",
            call_type="review_transcription",
            model=self._transcription_model,
        )

        response = await litellm.acompletion(
            model=self._transcription_model,
            messages=messages,
            response_format=_LLMTranscription,
        )

        raw = response.choices[0].message.content
        result = _LLMTranscription.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            call_type="review_transcription",
            model=self._transcription_model,
            utterance_length=len(result.user_utterance),
        )

        return result.user_utterance

    async def _judge(
        self,
        user_utterance: str,
        target_pattern: str,
        reference_answer: str,
        ja_prompt: str,
    ) -> ReviewResult:
        messages = [
            {
                "role": "system",
                "content": _STAGE2_SYSTEM_PROMPT.format(
                    target_pattern=target_pattern,
                ),
            },
            {
                "role": "user",
                "content": _STAGE2_USER_PROMPT.format(
                    target_pattern=target_pattern,
                    reference_answer=reference_answer,
                    ja_prompt=ja_prompt,
                    user_utterance=user_utterance,
                ),
            },
        ]

        logger.info(
            "llm_call_start",
            call_type="review_judgment",
            model=self._judgment_model,
            target_pattern=target_pattern,
        )

        response = await litellm.acompletion(
            model=self._judgment_model,
            messages=messages,
            response_format=_LLMReviewJudgment,
        )

        raw = response.choices[0].message.content
        result = _LLMReviewJudgment.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            call_type="review_judgment",
            model=self._judgment_model,
            correct=result.correct,
            item_used=result.item_used,
        )

        return ReviewResult(
            correct=result.correct,
            item_used=result.item_used,
            reason=result.reason,
        )
