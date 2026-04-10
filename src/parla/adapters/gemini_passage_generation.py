"""Gemini-based passage generation adapter using LiteLLM."""

from uuid import UUID

import litellm
import structlog
from pydantic import BaseModel, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from parla.domain.passage import Hint, Passage, Sentence

logger = structlog.get_logger()

# --- LLM output schema (internal to this adapter) ---


class _LLMHint(BaseModel):
    hint1: str
    hint2: str


class _LLMSentence(BaseModel):
    ja: str
    en: str
    hints: _LLMHint


class _LLMPassage(BaseModel):
    passage_index: int
    topic: str
    passage_type: str
    sentences: list[_LLMSentence]


class LLMPassageResult(BaseModel):
    """Schema for the raw LLM response. Exported for snapshot testing."""

    source_summary: str
    passages: list[_LLMPassage]

    @model_validator(mode="after")
    def _validate_non_empty(self) -> "LLMPassageResult":
        if len(self.passages) == 0:
            msg = "LLM must generate at least one passage"
            raise ValueError(msg)
        return self


# --- Conversion ---


def convert_to_domain(result: LLMPassageResult, source_id: UUID) -> list[Passage]:
    """Convert LLM output to domain Passage objects."""
    passages: list[Passage] = []
    for i, llm_passage in enumerate(result.passages):
        sentences = tuple(
            Sentence(
                order=j,
                ja=s.ja,
                en=s.en,
                hints=Hint(hint1=s.hints.hint1, hint2=s.hints.hint2),
            )
            for j, s in enumerate(llm_passage.sentences)
        )
        passages.append(
            Passage(
                source_id=source_id,
                order=i,
                topic=llm_passage.topic,
                passage_type=llm_passage.passage_type,
                sentences=sentences,
            )
        )
    return passages


# --- Prompts (migrated from verification/v1_passage_generation/prompt.py) ---

_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert English language educator specializing in creating \
study materials for Japanese learners of English.

Target CEFR level: {cefr_level}
English variant: {english_variant}
Passage type: {passage_type}

Your task is to generate passage-based study materials from a source text. \
Each passage is an English text (approximately 120-180 words, 7-10 sentences) \
that the learner will practice producing in English from a Japanese prompt.

## Output requirements

1. **Passage count**: Decide the optimal number of passages based on the source \
text length and content density. Typically 5-6 passages for a source text of \
around 3000 characters. Each passage should cover a coherent subtopic.

2. **For each sentence in each passage**, produce:
   - `ja`: A natural Japanese sentence that serves as the prompt for the learner. \
This must NOT be a literal translation of the English — write it as a native \
Japanese speaker would naturally express the idea.
   - `en`: A model English sentence at {cefr_level} level. Use vocabulary and \
grammar appropriate for {cefr_level}. Do NOT use vocabulary or structures \
significantly above this level.
   - `hints`: Two-level progressive hints for Japanese learners:
     - `hint1`: The first word of the English sentence + key words the learner \
is unlikely to produce on their own. Format: "First_word ... keyword1 / keyword2"
     - `hint2`: A syntactic skeleton using Japanese grammatical terms mixed with \
English key words. This helps Japanese learners map their grammar knowledge to \
English sentence structure.
       - Use Japanese terms for grammar: 主語, be動詞, 動詞(現在形), 動詞(過去形), \
動詞(原形), 目的語, 補語, 形容詞, 副詞, 関係代名詞節, that節, to不定詞, \
動名詞(V-ing), 前置詞句 etc.
       - For subordinate clauses introduced by conjunctions, name them by the \
specific conjunction: when節, if節, because節, although節 etc.
       - Use grammatically accurate terminology. For example, "until" and "before" \
are prepositions (前置詞), not conjunctions — write 前置詞句 or "until + 主語 + 動詞" \
rather than "until節".
       - Keep English content words (nouns, verbs, adjectives) in English.
       - **Clause nesting**: When a sentence contains clauses (that節, 関係代名詞節, \
when節, if節, etc.), show the internal structure of the clause using square brackets []. \
Use nested brackets for deeper nesting. This makes the parent-child structure \
of the sentence visually clear. Grammar annotations like 動詞(現在形) use round \
parentheses () — these are NOT nesting, just labels.
       - Format examples:
         "主語 + be動詞 + 補語[関係代名詞 + 動詞(現在形) + 目的語] / Uniqlo"
         "主語 + 動詞(現在形) + that節[主語 + 助動詞 + 動詞(原形) + 目的語] / forever"
         "接続詞[主語 + 動詞(現在形) + 目的語], 主語 + will + 副詞 + 動詞(原形) / come back"
         "主語 + 動詞(現在形) + that節[主語 + 助動詞 + 動詞(原形) + 目的語 + by 動名詞[目的語]] / parts"

3. **Passage type "{passage_type}"**: Ensure the passage style matches this type.
   - 説明型: Organize and convey facts clearly
   - 対話型: Simulate a conversation with an imagined listener
   - 意見型: Structure and present a personal opinion

4. **Source fidelity**: The passages must reflect the content and topics of the \
source text. Do not introduce unrelated topics.

5. **{english_variant}**: Use {english_variant} spelling and expressions consistently.

## Constraints
- Each passage: approximately 120-180 words total, 7-10 sentences
- Japanese prompts must be natural Japanese, not translationese
- English must stay within {cefr_level} level — avoid C1/C2 vocabulary in B1 passages. \
When in doubt, prefer vocabulary familiar to second-language learners over rare or \
literary synonyms (e.g. "driver" not "chauffeur")
- Each ja/en pair must have matching subject-predicate correspondence — do not \
let the subject or agent shift between the Japanese and English versions
- Hints must be progressively more informative (hint2 reveals more structure than hint1)\
"""

_USER_PROMPT_TEMPLATE = """\
以下のソーステキストから学習用パッセージを生成してください。

--- Source Text ---
{source_text}
--- End of Source Text ---\
"""


# --- Adapter ---


class GeminiPassageGenerationAdapter:
    """Generates passages via Gemini (LiteLLM)."""

    def __init__(
        self,
        model: str = "gemini/gemini-3.1-pro-preview",
        passage_type: str = "説明型",
    ) -> None:
        self._model = model
        self._passage_type = passage_type

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate(
        self,
        source_id: UUID,
        source_text: str,
        cefr_level: str,
        english_variant: str,
    ) -> list[Passage]:
        """Generate passages from source text via LLM."""
        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT_TEMPLATE.format(
                    cefr_level=cefr_level,
                    english_variant=english_variant,
                    passage_type=self._passage_type,
                ),
            },
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(source_text=source_text),
            },
        ]

        logger.info(
            "llm_call_start",
            model=self._model,
            cefr_level=cefr_level,
            source_text_length=len(source_text),
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=messages,
            response_format=LLMPassageResult,
        )

        raw_content = response.choices[0].message.content
        result = LLMPassageResult.model_validate_json(raw_content)

        logger.info(
            "llm_call_complete",
            model=self._model,
            passage_count=len(result.passages),
            total_sentences=sum(len(p.sentences) for p in result.passages),
        )

        return convert_to_domain(result, source_id)
