"""V7: プロンプトテンプレート."""

SYSTEM_PROMPT_BASE = """\
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

## Constraints
- The learning item must appear in the English sentence (possibly in inflected form)
- The English sentence should be 10-25 words
- Japanese prompt must be natural Japanese, not translationese
- Use {english_variant} spelling and expressions\
"""

# Phase A/B: 基本プロンプト（制約なし）
USER_PROMPT_BASIC = """\
Learning item: {learning_item}

--- Source Text ---
{source_text}
--- End of Source Text ---

Generate one practice sentence using this learning item in a context inspired by \
the source text.\
"""

# Phase C: 履歴付きプロンプト
USER_PROMPT_WITH_HISTORY = """\
Learning item: {learning_item}

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

# Phase D: 次元制約プロンプト
USER_PROMPT_WITH_CONSTRAINTS = """\
Learning item: {learning_item}

--- Source Text ---
{source_text}
--- End of Source Text ---

**Grammar constraints for this sentence:**
{constraints}

Generate one practice sentence using this learning item. \
The sentence MUST follow the grammar constraints specified above. \
Make the sentence sound natural despite these constraints — do not force \
an awkward construction just to meet them.\
"""


def format_history(variations: list[dict]) -> str:
    """過去の類題をプロンプト用にフォーマットする."""
    lines = []
    for i, v in enumerate(variations, 1):
        item = v["variation"]
        g = item["grammar"]
        lines.append(f"Variation {i}:")
        lines.append(f"  EN: {item['en']}")
        lines.append(f"  JA: {item['ja']}")
        lines.append(
            f"  Grammar: {g['sentence_type']}/{g['polarity']}/{g['voice']}/"
            f"{g['tense_aspect']}/{g['modality']}/{g['clause_type']}/"
            f"{g['info_structure']}"
        )
    return "\n".join(lines)


def format_constraints(constraints: dict[str, str]) -> str:
    """次元制約をプロンプト用にフォーマットする."""
    lines = []
    for dim, value in constraints.items():
        lines.append(f"- {dim}: {value}")
    return "\n".join(lines)
