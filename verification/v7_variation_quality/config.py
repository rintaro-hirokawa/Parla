"""V7: 検証設定."""

from dataclasses import dataclass, field


@dataclass
class V7Config:
    model: str = "gemini/gemini-3-flash-preview"  # ← ここにモデル名を記入（例: "gemini/gemini-2.0-flash"）
    cefr_level: str = "B1"
    english_variant: str = "American English"
    max_retries: int = 2


# 学習項目の定義
LEARNING_ITEMS = [
    {
        "id": "L1",
        "item": "be responsible for ~ing",
        "category": "構文",
        "pattern": r"(?i)\b(be|is|are|was|were|been|being)\b.*\bresponsible\s+for\b",
    },
    {
        "id": "L2",
        "item": "environmental impact",
        "category": "コロケーション",
        "pattern": r"(?i)\benvironmental\s+impact\b",
    },
    {
        "id": "L3",
        "item": "more X than Y",
        "category": "文法（比較級）",
        "pattern": r"(?i)\bmore\b.+\bthan\b",
    },
    {
        "id": "L4",
        "item": "take into account",
        "category": "表現",
        "pattern": r"(?i)\b(take|takes|took|taken|taking)\b.*\binto\s+account\b",
    },
]

# Phase B〜D で使用する学習項目（L1: 構文, L4: 句動詞）
FOCUS_ITEM_IDS = ["L1", "L4"]

# Phase D: 各学習項目に対する次元制約セット（3種ずつ）
PHASE_D_CONSTRAINTS = {
    "L1": [
        {"voice": "passive", "tense_aspect": "present_simple"},
        {"sentence_type": "interrogative", "modality": "obligation"},
        {"clause_type": "adverbial", "polarity": "negative"},
    ],
    "L4": [
        {"voice": "passive", "tense_aspect": "past_perfect"},
        {"sentence_type": "interrogative", "modality": "hypothetical"},
        {"sentence_type": "imperative", "clause_type": "simple"},
    ],
}

# ソーステキストの割り当て
# Phase A: 各学習項目に対して S1〜S5 を使用
# Phase B/C/D: 各学習項目に対して S1 を固定
# Phase E: L4 に対して S6 を使用
SOURCE_FILES = [
    "s1_technology.txt",
    "s2_environment.txt",
    "s3_business.txt",
    "s4_health.txt",
    "s5_culture.txt",
    "s6_education.txt",
    "s7_food.txt",
    "s8_sports.txt",
]
