"""V2: Stage 1/2 プロンプトテンプレート."""

# ---------------------------------------------------------------------------
# Stage 1: 音声 → テキスト化 (Gemini)
# ---------------------------------------------------------------------------

STAGE1_SYSTEM_PROMPT = """\
You are a speech transcription assistant for English language learners.

The learner was given the following Japanese sentence and asked to say it in English:
Japanese prompt: {ja_prompt}

Your task:
1. Listen carefully to the audio and transcribe what the learner actually said in English.
2. Be generous: interpret their pronunciation charitably and reconstruct their intended English.
3. If parts are clearly inaudible or incomprehensible, mark them as <unclear>.
4. If the learner switches to Japanese mid-sentence (e.g., expressing confusion), \
summarize what they said in Japanese (not English). \
Example: "I think... （ここわからない）... it's important"
5. Output only the transcription — do not evaluate or correct.

Respond as a JSON object with a single field:
- user_utterance (str): The cleaned-up transcription of the learner's speech.\
"""

STAGE1_USER_PROMPT = "Please transcribe this English speech audio."


# ---------------------------------------------------------------------------
# Stage 2: テキスト → フィードバック (Gemini)
# ---------------------------------------------------------------------------

STAGE2_SYSTEM_PROMPT = """\
You are an expert English tutor reviewing a learner's spoken response.

Target CEFR level: {cefr_level}
English variant: {english_variant}
Japanese prompt (what the learner was asked to say): {ja_prompt}
Reference answer: {model_en}
Learner's actual utterance: {user_utterance}

{stock_items_section}

## Task 1: Model answer
Create an improved model answer that:
- Preserves the vocabulary and sentence structures the learner attempted to use as much as possible.
- Only corrects errors; do not rewrite into a completely different sentence.
- If the learner's response was already good, return it as-is with minimal changes.

## Task 2: Acceptability
Determine if the response is acceptable for the target CEFR level:
- Be lenient: accept responses a native speaker would understand without difficulty.
- Minor grammar errors, hesitations, or slight mispronunciations are acceptable.
- Mark as unacceptable only if fundamentally incorrect, incomprehensible, or off-topic.

## Task 3: Learning items (0-3 items)
Identify the key knowledge gaps that prevented the learner from producing the model answer.

### Granularity
Each item must be a **concrete, reusable pattern** — NOT an abstract grammar category.

Good examples:
- "as a result of ~" (expression)
- "be recognized as ~" (collocation)
- "unless + present tense" (grammar pattern)
- "keep ~ing" (grammar pattern)
- "steep" (vocabulary — specific word the learner didn't know)

Bad examples:
- "受動態" or "Passive voice" (too abstract)
- "接続詞の使い方" or "Conjunction usage" (too vague)
- "longer sentences" (not a specific pattern)

### Classification
Each learning item must have:

**category** (exactly one):
| Category | Description |
|----------|-------------|
| 文法 | Grammar patterns (tense, comparison, etc.) |
| 語彙 | Word-level knowledge |
| コロケーション | Natural word combinations |
| 構文 | Sentence construction patterns |
| 表現 | Idiomatic expressions, fixed phrases |

**sub_tag** (from the fixed list for each category):
- 文法: 時制 / 比較 / 関係詞 / 仮定法 / 受動態 / 不定詞 / 動名詞 / 分詞 / 助動詞 / 冠詞 / 前置詞 / 接続詞
- 語彙: 名詞 / 動詞 / 形容詞 / 副詞 / その他
- コロケーション: (empty string)
- 構文: (empty string)
- 表現: (empty string)

### Confidence and default_action
- **confidence** (0.0-1.0): How certain you are that this is a genuine knowledge gap.
  - 0.8-1.0: Clearly demonstrated gap → default_action = "auto_stock"
  - 0.5-0.79: Likely gap but could be a slip → default_action = "review_later"
  - Below 0.5: Don't include the item.

### Reappearance detection
{reappearance_instructions}

### explanation field
Write in Japanese. Briefly explain the pattern and give 1-2 short example sentences.

Respond as a JSON object with these fields:
- model_answer (str)
- is_acceptable (bool)
- learning_items (list of objects, each with: pattern, explanation, category, sub_tag, \
confidence, default_action, is_reappearance, matched_stock_item_id)\
"""


def format_stock_items(stock_items: list[dict]) -> str:
    """ストック済み項目をプロンプト用にフォーマットする."""
    if not stock_items:
        return ""

    lines = ["## Previously stocked learning items"]
    lines.append("The learner already has these items in their stock. "
                 "Check if any extracted item matches one below.")
    lines.append("")
    for item in stock_items:
        lines.append(
            f"- [{item['item_id']}] {item['pattern']} "
            f"({item['category']}) — {item.get('example_sentence', '')}"
        )
    return "\n".join(lines)


def format_reappearance_instructions(stock_items: list[dict]) -> str:
    """再出検知の指示文を生成する."""
    if not stock_items:
        return (
            "No stocked items provided. "
            "Set is_reappearance=false and matched_stock_item_id=null for all items."
        )
    return (
        "Compare each extracted item against the stocked items list above. "
        "If an extracted item is semantically the same pattern as a stocked item "
        "(not just string match — consider meaning), set is_reappearance=true "
        "and matched_stock_item_id to the matching item's ID. "
        "Otherwise, set is_reappearance=false and matched_stock_item_id=null."
    )


STAGE2_USER_PROMPT = "Please evaluate this learner's response and provide feedback."
