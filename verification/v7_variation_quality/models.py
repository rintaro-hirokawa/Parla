"""V7: 出力スキーマ."""

from pydantic import BaseModel


class GrammarProfile(BaseModel):
    """英文の文法構造を7次元で記述する."""

    sentence_type: str       # declarative / interrogative / imperative
    polarity: str            # affirmative / negative
    voice: str               # active / passive
    tense_aspect: str        # present_simple / past_simple / present_perfect / ...
    modality: str            # none / obligation / possibility / hypothetical
    clause_type: str         # simple / compound / adverbial / relative / noun_clause / participial
    info_structure: str      # canonical / fronted_adverbial / cleft / there_construction / topicalization


class VariationItem(BaseModel):
    """類題1件."""

    ja: str                  # 日本語お題
    en: str                  # 模範英文
    grammar: GrammarProfile  # 7次元の文法構造プロファイル


class VariationResult(BaseModel):
    """LLM #3 の出力."""

    learning_item: str
    source_summary: str
    variation: VariationItem
