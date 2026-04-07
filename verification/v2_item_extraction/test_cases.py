"""V2: テストケース定義（6シナリオ × 2音声タイプ）.

V1最終出力（result_20260406_140705.json）から多様な文法パターンをカバーする6文を選択。
各文に jp_mixed（日本語混じり）と different_structure（構文・語彙が異なる）の2パターン。
"""

from dataclasses import dataclass


@dataclass
class AudioCase:
    audio_type: str  # jp_mixed, different_structure
    audio_type_ja: str
    instruction: str  # 人間向けの明確な指示（何をすればいいか）
    script: str  # 参考スクリプト（そのまま読んでもOK、アドリブでもOK）


@dataclass
class Scenario:
    id: str
    ja_prompt: str
    model_en: str
    passage_topic: str  # 参照元パッセージのトピック
    audio_cases: list[AudioCase]

    def audio_filename(self, audio_type: str) -> str:
        return f"{self.id}_{audio_type}.wav"


SCENARIOS: list[Scenario] = [
    # --- s01: although節 + by himself（譲歩 + 再帰表現）---
    Scenario(
        id="s01",
        ja_prompt="現在69歳ですが、彼は今でも自社の車を自らテストしています。",
        model_en="Although he is 69 years old now, he still tests his company's cars by himself.",
        passage_topic="Akio Toyoda's Philosophy on Making Cars",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="英語で言おうとして、途中で詰まって日本語が混ざる感じで話してください。「by himself」が出てこない想定。",
                script="Although he is 69 years old now, he still tests his company's cars... えっと... 自分で... by himself.",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに、日本語の意味を自分なりの英語で言い換えてください。althoughを使わなくてOK。",
                script="He is 69 years old, but he tests the cars of his company alone.",
            ),
        ],
    ),
    # --- s02: because節 + 形容詞 steep/sharp（原因節 + 語彙）---
    Scenario(
        id="s02",
        ja_prompt="そのコースは急な坂や急カーブがあるため、非常に厳しいです。",
        model_en="The course is extremely tough because it has steep hills and sharp curves.",
        passage_topic="Akio Toyoda's Philosophy on Making Cars",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="「steep」が出てこなくて「急な坂」と日本語で言ってしまう感じで。",
                script="The course is very... えっと... tough because it has... 急な坂... and sharp curves.",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに自分の言葉で。extremely/steep/sharpを使わなくてOK。",
                script="It is a very hard course. There are steep hills and dangerous turns.",
            ),
        ],
    ),
    # --- s03: 現在完了 + as a result of + in a row（複合表現）---
    Scenario(
        id="s03",
        ja_prompt="この努力の結果として、トヨタは6年連続で世界トップの自動車メーカーとなっています。",
        model_en="As a result of this effort, Toyota has been the top car maker in the world for six years in a row.",
        passage_topic="Akio Toyoda's Philosophy on Making Cars",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="「in a row」（連続で）が出てこなくて「6年連続」と日本語で言ってしまう感じで。",
                script="As a result of this effort, Toyota has been the top car maker... えっと... 6年連続... in the world.",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに自分の言葉で。has beenや in a rowを使わなくてOK。",
                script="Because of this effort, Toyota became the number one car company in the world for six years.",
            ),
        ],
    ),
    # --- s04: by + 動名詞（手段表現 + 過去形）---
    Scenario(
        id="s04",
        ja_prompt="ある講義の後、彼はある学生を自分の車の助手席に招待して驚かせました。",
        model_en="After one of his lectures, he surprised a student by inviting him to the passenger seat of his car.",
        passage_topic="Teaching Young People About Cars",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="「by inviting」の部分が出てこなくて「招待して」と日本語になる感じで。",
                script="After one of his lectures, he surprised a student by... えっと... 招待して... to the passenger seat.",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに自分の言葉で。by ~ingの構文を使わなくてOK。",
                script="After a lecture, he asked a student to sit in his car and the student was very surprised.",
            ),
        ],
    ),
    # --- s05: 受動態 + as（知覚動詞 + 受動態の be known as）---
    Scenario(
        id="s05",
        ja_prompt="しかし現在では、全世界で最も大きな投資会社の一つとして認識されています。",
        model_en="However, it is now recognized as one of the largest investment companies in the entire world.",
        passage_topic="Masayoshi Son's Huge Investments",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="「one of the largest」が出てこなくて「一番大きい投資会社」と日本語になる感じで。",
                script="However, it is now recognized as... うーん... 一番大きい投資会社... in the world.",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに自分の言葉で。受動態を使わず能動態にしてもOK。",
                script="But now, people know it as one of the biggest investment companies in the world.",
            ),
        ],
    ),
    # --- s06: unless節 + keep ~ing（条件 + 継続表現）---
    Scenario(
        id="s06",
        ja_prompt="彼は、企業は成長し続けない限り市場で生き残れないと信じています。",
        model_en="He believes that companies cannot survive in the market unless they keep growing.",
        passage_topic="Tadashi Yanai's Goal to be Number One",
        audio_cases=[
            AudioCase(
                audio_type="jp_mixed",
                audio_type_ja="日本語混じり",
                instruction="「unless they keep growing」が出てこなくて日本語で「成長し続けない限り」と言ってしまう感じで。",
                script="He believes that companies cannot survive in the market... えっと... 成長し続けない限り...",
            ),
            AudioCase(
                audio_type="different_structure",
                audio_type_ja="構文・語彙が異なる",
                instruction="模範解答を見ずに自分の言葉で。unlessをifに変えるなど自由に。",
                script="He thinks that if companies do not continue to grow, they will die in the market.",
            ),
        ],
    ),
]


# --- ストック済み学習項目（再出検知テスト用）---
# V3の stock_items_10.json から流用 + V2テストケースと意図的に一致する項目を含む

STOCK_ITEMS: list[dict] = [
    {
        "item_id": "si-001",
        "pattern": "A is more X than B",
        "category": "文法",
        "sub_tag": "比較",
        "example_sentence": "This approach is more effective than the previous one.",
    },
    {
        "item_id": "si-002",
        "pattern": "be responsible for ~ing",
        "category": "コロケーション",
        "sub_tag": "",
        "example_sentence": "She is responsible for managing the entire project.",
    },
    {
        "item_id": "si-005",
        "pattern": "take a look at",
        "category": "表現",
        "sub_tag": "",
        "example_sentence": "Let me take a look at the report before the meeting.",
    },
    {
        "item_id": "si-008",
        "pattern": "as a result of",
        "category": "表現",
        "sub_tag": "",
        "example_sentence": "As a result of the policy change, sales increased.",
    },
    {
        "item_id": "si-011",
        "pattern": "be recognized as",
        "category": "コロケーション",
        "sub_tag": "",
        "example_sentence": "The city is recognized as one of the safest in the country.",
    },
    {
        "item_id": "si-012",
        "pattern": "keep ~ing",
        "category": "文法",
        "sub_tag": "動名詞",
        "example_sentence": "You should keep practicing every day.",
    },
]
