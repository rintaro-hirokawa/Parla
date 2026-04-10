"""Gemini-based variation generation adapter using LiteLLM.

Implements the history-based method (V7 Phase C) for grammatical diversity.
"""

from collections.abc import Sequence

import litellm
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.ports.variation_generation import PastVariationInfo, RawVariation

logger = structlog.get_logger()

# --- LLM output schema (internal to this adapter) ---


class _LLMGrammarProfile(BaseModel):
    """Grammar structure descriptor for diversity tracking."""

    sentence_type: str
    polarity: str
    voice: str
    tense_aspect: str
    modality: str
    clause_type: str
    info_structure: str


class _LLMHint(BaseModel):
    hint1: str
    hint2: str


class _LLMVariation(BaseModel):
    ja: str
    en: str
    grammar: _LLMGrammarProfile
    hints: _LLMHint


class LLMVariationResult(BaseModel):
    """Full LLM response schema. Exported for snapshot testing."""

    learning_item: str
    source_summary: str
    variation: _LLMVariation


# --- Prompts (adapted from V7 verification Phase C) ---


_SYSTEM_PROMPT = """\
You are an expert English language educator creating practice sentences \
for Japanese learners of English.

Target CEFR level: {cefr_level}
English variant: {english_variant}

## Your task

Given a **learning item** (a target expression, grammar pattern, or collocation) \
and a **source text** for context, generate ONE practice sentence that:

1. Uses the learning item correctly and naturally
2. Draws context/topic from the source text (but is NOT a direct quote)
3. Includes a Japanese prompt (お題) that a learner would translate into English
4. Includes two-stage progressive hints for the model English sentence

## Output requirements

- `learning_item`: The target expression exactly as given
- `source_summary`: A one-line summary of the source text topic
- `variation.ja`: A natural Japanese sentence as the prompt. \
This must NOT be a literal translation — write it as a native Japanese speaker \
would naturally express the idea.
- `variation.en`: A model English sentence at {cefr_level} level that correctly \
uses the learning item. Stay within {cefr_level} vocabulary and grammar.
- `variation.grammar`: A profile describing the grammatical structure of the \
English sentence across 7 dimensions:
  - `sentence_type`: "declarative" | "interrogative" | "imperative"
  - `polarity`: "affirmative" | "negative"
  - `voice`: "active" | "passive"
  - `tense_aspect`: "present_simple" | "past_simple" | "present_perfect" | \
"past_perfect" | "future_will" | "future_going_to" | "present_progressive" | \
"past_progressive"
  - `modality`: "none" | "obligation" | "possibility" | "hypothetical"
  - `clause_type`: "simple" | "compound" | "adverbial" | "relative" | \
"noun_clause" | "participial"
  - `info_structure`: "canonical" | "fronted_adverbial" | "cleft" | \
"there_construction" | "topicalization"
- `variation.hints`: Two-stage progressive hints for the English sentence.
  - `hint1`: The first word of the sentence + any words that learners at \
{cefr_level} would find hard to recall (separated by " / "). \
Example: "Chairman ... test / himself"
  - `hint2`: A grammatical skeleton showing the sentence structure + hard-to-recall \
words. Use grammatical labels for each slot. \
Example: "Chairman + 動詞(現在形) + 目的語 + himself / test"

## Constraints
- The learning item must appear in the English sentence (possibly in inflected form)
- The English sentence should be 10-25 words
- Japanese prompt must be natural Japanese, not translationese
- Use {english_variant} spelling and expressions
- hint1 must NOT reveal the sentence structure
- hint2 must reveal more structure than hint1 (progressive disclosure)\
"""


_USER_PROMPT_BASIC = """\
Learning item: {learning_item}
Explanation: {explanation}

--- Source Text ---
{source_text}
--- End of Source Text ---

Generate one practice sentence using this learning item in a context inspired by \
the source text.\
"""


_USER_PROMPT_WITH_HISTORY = """\
Learning item: {learning_item}
Explanation: {explanation}

--- Source Text ---
{source_text}
--- End of Source Text ---

--- Previous Variations (DO NOT repeat these) ---
{history}
--- End of Previous Variations ---

Generate one practice sentence using this learning item. \
You MUST vary the grammatical structure from previous variations. \
Look at the grammar profiles above and choose dimensions that have NOT been used yet. \
For example, if all previous sentences are declarative/active/present_simple, \
try interrogative, passive, past tense, conditional, etc.\
"""


def _format_history(past: Sequence[PastVariationInfo]) -> str:
    lines = []
    for i, v in enumerate(past, 1):
        lines.append(f"Variation {i}:")
        lines.append(f"  EN: {v.en}")
        lines.append(f"  JA: {v.ja}")
    return "\n".join(lines)


# --- Adapter ---


class GeminiVariationAdapter:
    """Generates variations via Gemini (LiteLLM) using history-based method."""

    def __init__(self, model: str = "gemini/gemini-3-flash-preview") -> None:
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate_variation(
        self,
        learning_item_pattern: str,
        learning_item_explanation: str,
        cefr_level: str,
        english_variant: str,
        source_text: str,
        past_variations: Sequence[PastVariationInfo],
    ) -> RawVariation:
        """Generate a practice variation for a learning item."""
        system_content = _SYSTEM_PROMPT.format(
            cefr_level=cefr_level,
            english_variant=english_variant,
        )

        if past_variations:
            user_content = _USER_PROMPT_WITH_HISTORY.format(
                learning_item=learning_item_pattern,
                explanation=learning_item_explanation,
                source_text=source_text,
                history=_format_history(past_variations),
            )
        else:
            user_content = _USER_PROMPT_BASIC.format(
                learning_item=learning_item_pattern,
                explanation=learning_item_explanation,
                source_text=source_text,
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        logger.info(
            "llm_call_start",
            call_type="variation_generation",
            model=self._model,
            learning_item=learning_item_pattern,
            has_history=bool(past_variations),
            history_count=len(past_variations),
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=LLMVariationResult,
        )

        raw_content = response.choices[0].message.content
        result = LLMVariationResult.model_validate_json(raw_content)

        logger.info(
            "llm_call_complete",
            call_type="variation_generation",
            model=self._model,
            learning_item=learning_item_pattern,
        )

        return RawVariation(
            ja=result.variation.ja,
            en=result.variation.en,
            hint1=result.variation.hints.hint1,
            hint2=result.variation.hints.hint2,
        )
