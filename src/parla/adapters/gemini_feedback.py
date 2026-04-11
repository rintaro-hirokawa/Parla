"""Gemini-based feedback generation adapter (2-stage pipeline).

Stage 1: Audio → Transcription (Flash Lite)
Stage 2: Transcription + Context → Feedback (Flash)

Prompts and pipeline design from verification/v2_item_extraction.
"""

import asyncio
import base64
from collections.abc import Sequence

import litellm
import structlog
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.adapters.audio_formats import MIME_TYPES as _MIME_TYPES
from parla.ports.feedback_generation import (
    RawFeedback,
    RawLearningItem,
    StockedItemInfo,
)

logger = structlog.get_logger()

# --- LLM output schemas (internal to this adapter) ---


class _LLMTranscription(BaseModel):
    user_utterance: str


class _LLMLearningItem(BaseModel):
    pattern: str
    explanation: str
    category: str
    sub_tag: str = ""
    priority: int = Field(ge=2, le=5)
    is_reappearance: bool = False
    matched_stock_item_id: str | None = None


class _LLMFeedback(BaseModel):
    model_answer: str
    is_acceptable: bool
    learning_items: list[_LLMLearningItem] = Field(default_factory=list)


# --- Prompts (migrated from verification/v2_item_extraction/prompt.py) ---

_STAGE1_SYSTEM_PROMPT = """\
You are a speech transcription assistant for English language learners.

The learner was given the following Japanese sentence and asked to say it in English:
Japanese prompt: {ja_prompt}

Your task:
1. Listen carefully to the audio and transcribe what the learner actually said in English.
2. If there is no audible speech in the audio (silence, background noise only, or \
unintelligible sounds with no recognizable words), output exactly: <no_speech>
Do NOT guess or infer what the learner might have said based on the Japanese prompt. \
Only transcribe speech that is actually present in the audio.
3. Be generous: interpret their pronunciation charitably and reconstruct their intended English.
4. If parts are clearly inaudible or incomprehensible, mark them as <unclear>.
5. If the learner switches to Japanese mid-sentence (e.g., expressing confusion), \
summarize what they said in Japanese (not English). \
Example: "I think... （ここわからない）... it's important"
6. Mark noticeable pauses (roughly 1 second or longer) with [pause]. \
If a pause is notably long (roughly 3 seconds or more), mark it as [long pause]. \
Place the marker at the position where the pause occurred. \
Example: "He surprised a student by [long pause] inviting him to the seat."
7. Output only the transcription — do not evaluate or correct.\
"""

_STAGE1_USER_PROMPT = "Please transcribe this English speech audio."

_STAGE2_SYSTEM_PROMPT = """\
You are an English tutor for a spoken English practice app.

A Japanese learner saw a Japanese sentence and tried to say it in English.
You have the Japanese sentence and a transcription of what they actually said.
Your job: figure out what they couldn't say in English, and help them.

IMPORTANT: This is spoken English practice. All your output (model answers, learning items, \
explanations) must target natural spoken/conversational English. Do NOT suggest written-only \
or overly formal expressions. If a casual spoken form exists, prefer it.

## Input
- CEFR level: {cefr_level}
- English variant: {english_variant}
- Japanese sentence: {ja_prompt}
- What the learner said: {user_utterance}

{stock_items_section}

## Task 1: Model answer

Write a natural **spoken** English sentence that:
1. Conveys the full meaning of the Japanese sentence.
2. Stays as close as possible to the learner's own words and sentence structure.
3. Fills in any gaps where the learner switched to Japanese or left parts out.
4. Fixes grammar errors only where necessary.
5. Sounds natural in conversation (avoid bookish or overly formal phrasing).

If the learner's English already fully conveys the Japanese meaning, return it as-is \
or with minimal corrections.

## Task 2: Acceptability

Did the learner convey the meaning of the Japanese sentence in English?
- true: A native speaker would understand the intended meaning without difficulty.
- false: Critical parts are missing, left in Japanese, or incomprehensible.

Be lenient. Imperfect grammar, informal style, and different word choices are all fine \
as long as the meaning comes through.

## Task 3: Learning items (0-3 items)

Identify specific things the learner COULD NOT express in English.

Evidence of a gap:
- The learner switched to Japanese for that part (e.g., "...えっと...急な坂...")
- The learner omitted a meaningful part of the Japanese sentence entirely
- The learner produced broken/ungrammatical English that shows they don't know the pattern
- The learner paused notably ([pause] or [long pause]) before or during a phrase, \
suggesting they struggled to construct that part — especially combined with other evidence

NOT a gap:
- The learner used different but valid English words (big vs large, but vs however)
- The learner used a different sentence structure that still conveys the meaning
- Minor slips (article errors, hesitation) that don't show a knowledge gap
- Style differences (formal vs informal) — this is speaking practice, not an essay
- Written/formal expressions the learner didn't use (e.g., don't suggest "as a result of" \
when "because of" works fine in conversation)

### Granularity and usefulness
Each item must be a concrete, reusable pattern — not an abstract grammar category.

Prioritize items that are **broadly useful** for a second-language learner. \
Ask yourself: "Will the learner encounter this pattern frequently in everyday English?" \
Prefer high-frequency, versatile patterns over niche vocabulary or situation-specific expressions.

Good examples (high reuse value):
- "by ~ing" — grammar pattern usable in countless contexts
- "one of the + 最上級 + 複数名詞" — common structure
- "in a row" — frequently used phrase
- "keep ~ing" — everyday pattern

Acceptable but lower priority:
- "steep" — useful word, but limited to describing slopes/prices
- "passenger seat" — correct, but very situation-specific

Bad examples:
- "Passive voice" — too abstract
- "Better vocabulary" — not actionable
- "Conjunction usage" — too vague

When choosing between items, prefer the one the learner will need more often.

Note: When a pattern includes grammar terms, write them in Japanese \
(e.g., "最上級" not "superlative", "複数名詞" not "plural noun", "動名詞" not "gerund").

### Classification

**category** (exactly one):
| Category | Use when |
|----------|----------|
| 文法 | Couldn't form a grammar pattern (tense, comparison, etc.) |
| 語彙 | Didn't know a specific word |
| コロケーション | Couldn't produce a natural word combination |
| 構文 | Couldn't organize the sentence structure |
| 表現 | Didn't know an idiomatic expression or fixed phrase |

**sub_tag** (from fixed list, or "" if none applies):
- 文法: 時制 / 比較 / 関係詞 / 仮定法 / 受動態 / 不定詞 / 動名詞 / \
分詞 / 助動詞 / 冠詞 / 前置詞 / 接続詞
- 語彙: 名詞 / 動詞 / 形容詞 / 副詞 / その他
- コロケーション / 構文 / 表現: ""

### Priority (習得優先度)
Rate how urgently the learner needs to acquire this item, on a scale of 2-5.
Do not include items at level 1 (niche vocabulary or situation-specific expressions).

5 = Must learn: Essential everyday pattern, clearly unknown (switched to Japanese)
4 = Should learn soon: Broadly useful, clear struggle evidence. Expected at CEFR level
3 = Good to learn: Moderately common. Learner worked around it. Would expand range
2 = Nice to have: Less frequent or above-level expression. Low priority for now

Three axes for judgment:
1. Versatility: How often will the learner need this? (daily vs rare)
2. Depth of gap: Completely unknown vs. vaguely known but couldn't produce
3. CEFR fit: Should a learner at this level already know this?

### Reappearance detection
{reappearance_instructions}

### explanation field
Write in Japanese. Briefly explain the pattern with 1-2 example sentences.\
"""

_STAGE2_USER_PROMPT = "Please evaluate this learner's response and provide feedback."


# --- Helpers ---


def _format_stock_items(items: Sequence[StockedItemInfo]) -> str:
    if not items:
        return ""
    lines = [
        "## Previously stocked learning items",
        "The learner already has these items in their stock. Check if any extracted item matches one below.",
        "",
    ]
    for item in items:
        lines.append(f"- [{item.item_id}] {item.pattern} ({item.category}) — {item.example_sentence}")
    return "\n".join(lines)


def _format_reappearance_instructions(items: Sequence[StockedItemInfo]) -> str:
    if not items:
        return "No stocked items provided. Set is_reappearance=false and matched_stock_item_id=null for all items."
    return (
        "Compare each extracted item against the stocked items list above. "
        "If an extracted item is semantically the same pattern as a stocked item "
        "(not just string match — consider meaning), set is_reappearance=true "
        "and matched_stock_item_id to the matching item's ID. "
        "Otherwise, set is_reappearance=false and matched_stock_item_id=null."
    )


def _convert_to_raw_feedback(llm_result: _LLMFeedback, transcription: str) -> RawFeedback:
    items = tuple(
        RawLearningItem(
            pattern=li.pattern,
            explanation=li.explanation,
            category=li.category,
            sub_tag=li.sub_tag,
            priority=li.priority,
            is_reappearance=li.is_reappearance,
            matched_stock_item_id=li.matched_stock_item_id,
        )
        for li in llm_result.learning_items
    )
    return RawFeedback(
        user_utterance=transcription,
        model_answer=llm_result.model_answer,
        is_acceptable=llm_result.is_acceptable,
        items=items,
    )


# Exported for snapshot testing
LLMTranscriptionResult = _LLMTranscription
LLMFeedbackResult = _LLMFeedback


# --- Adapter ---


class GeminiFeedbackAdapter:
    """2-stage feedback generation via Gemini (LiteLLM).

    Stage 1: Flash Lite — audio → transcription
    Stage 2: Flash — transcription + context → feedback
    """

    def __init__(
        self,
        stage1_model: str = "gemini/gemini-3-flash-preview",
        stage2_model: str = "gemini/gemini-3-flash-preview",
    ) -> None:
        self._stage1_model = stage1_model
        self._stage2_model = stage2_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _transcribe(
        self,
        audio_data: bytes,
        audio_format: str,
        ja_prompt: str,
    ) -> str:
        """Stage 1: Audio → transcription text."""
        encoded = base64.b64encode(audio_data).decode("utf-8")
        mime_type = _MIME_TYPES.get(audio_format, f"audio/{audio_format}")

        messages = [
            {
                "role": "system",
                "content": _STAGE1_SYSTEM_PROMPT.format(ja_prompt=ja_prompt),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _STAGE1_USER_PROMPT},
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
            stage="transcription",
            model=self._stage1_model,
        )

        response = await asyncio.to_thread(litellm.completion,
            model=self._stage1_model,
            messages=messages,
            response_format=_LLMTranscription,
        )

        raw = response.choices[0].message.content
        result = _LLMTranscription.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            stage="transcription",
            model=self._stage1_model,
            utterance_length=len(result.user_utterance),
        )

        return result.user_utterance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _generate_feedback(
        self,
        user_utterance: str,
        ja_prompt: str,
        cefr_level: str,
        english_variant: str,
        stocked_items: Sequence[StockedItemInfo],
    ) -> _LLMFeedback:
        """Stage 2: Transcription + context → feedback."""
        system_prompt = _STAGE2_SYSTEM_PROMPT.format(
            cefr_level=cefr_level,
            english_variant=english_variant,
            ja_prompt=ja_prompt,
            user_utterance=user_utterance,
            stock_items_section=_format_stock_items(stocked_items),
            reappearance_instructions=_format_reappearance_instructions(stocked_items),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _STAGE2_USER_PROMPT},
        ]

        logger.info(
            "llm_call_start",
            stage="feedback",
            model=self._stage2_model,
            cefr_level=cefr_level,
        )

        response = await asyncio.to_thread(litellm.completion,
            model=self._stage2_model,
            messages=messages,
            response_format=_LLMFeedback,
        )

        raw = response.choices[0].message.content
        result = _LLMFeedback.model_validate_json(raw)

        logger.info(
            "llm_call_complete",
            stage="feedback",
            model=self._stage2_model,
            item_count=len(result.learning_items),
        )

        return result

    async def generate_feedback(
        self,
        audio_data: bytes,
        audio_format: str,
        ja_prompt: str,
        cefr_level: str,
        english_variant: str,
        stocked_items: Sequence[StockedItemInfo],
    ) -> RawFeedback:
        """Full 2-stage pipeline: audio → transcription → feedback."""
        transcription = await self._transcribe(audio_data, audio_format, ja_prompt)

        if transcription.strip() == "<no_speech>":
            logger.info("no_speech_detected", ja_prompt=ja_prompt)
            transcription = "<no_speech>"

        llm_feedback = await self._generate_feedback(
            user_utterance=transcription,
            ja_prompt=ja_prompt,
            cefr_level=cefr_level,
            english_variant=english_variant,
            stocked_items=stocked_items,
        )
        return _convert_to_raw_feedback(llm_feedback, transcription)
