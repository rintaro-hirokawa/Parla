"""V11: テストケース定義（1パッセージ × 4音声パターン、日本語なし）."""

from dataclasses import dataclass


@dataclass
class Sentence:
    index: int
    ja_prompt: str
    model_answer: str


@dataclass
class AudioCase:
    audio_type: str
    audio_type_ja: str
    script: list[str]  # 録音時に読む全文（文ごとに1要素）
    expected_pass: bool


@dataclass
class Passage:
    id: str
    topic: str
    sentences: list[Sentence]

    def audio_filename(self, audio_type: str) -> str:
        return f"{self.id}_{audio_type}.wav"

    def full_reference_text(self) -> str:
        """Azure に渡す reference_text（全文結合）."""
        return " ".join(s.model_answer for s in self.sentences)


# V1 出力 result_20260406_140705.json より
PASSAGE = Passage(
    id="p01",
    topic="Akio Toyoda's Philosophy on Making Cars",
    sentences=[
        Sentence(
            index=1,
            ja_prompt="豊田章男氏は、日本の有名な企業であるトヨタ自動車の会長です。",
            model_answer="Akio Toyoda is the chairman of Toyota Motor Corporation, a famous Japanese company.",
        ),
        Sentence(
            index=2,
            ja_prompt="現在69歳ですが、彼は今でも自社の車を自らテストしています。",
            model_answer="Although he is 69 years old now, he still tests his company's cars by himself.",
        ),
        Sentence(
            index=3,
            ja_prompt="特別なテストコースで車を運転するために、彼はよくレーシングスーツとヘルメットを着用します。",
            model_answer="He often wears a racing suit and a helmet to drive cars on a special test course.",
        ),
        Sentence(
            index=4,
            ja_prompt="そのコースは急な坂や急カーブがあるため、非常に厳しいです。",
            model_answer="The course is extremely tough because it has steep hills and sharp curves.",
        ),
        Sentence(
            index=5,
            ja_prompt="彼の基本的な哲学は、車が完全に壊れるまでテストすることです。",
            model_answer="His basic philosophy is to test cars until they completely break.",
        ),
        Sentence(
            index=6,
            ja_prompt="彼は、壊れた部品が車の中で最も弱い場所を示していると信じています。",
            model_answer="He believes that a broken part shows the weakest place in the car.",
        ),
        Sentence(
            index=7,
            ja_prompt="エンジニアたちはその部品を強くすることで、一歩ずつより良い車を作ることができます。",
            model_answer="Engineers can make that part stronger to build a much better car step by step.",
        ),
        Sentence(
            index=8,
            ja_prompt="この努力の結果として、トヨタは6年連続で世界トップの自動車メーカーとなっています。",
            model_answer="As a result of this effort, Toyota has been the top car maker in the world for six years in a row.",
        ),
    ],
)

AUDIO_CASES: list[AudioCase] = [
    AudioCase(
        audio_type="pass_fluent",
        audio_type_ja="流暢な全文英語（模範通り）",
        script=[
            "Akio Toyoda is the chairman of Toyota Motor Corporation, a famous Japanese company.",
            "Although he is 69 years old now, he still tests his company's cars by himself.",
            "He often wears a racing suit and a helmet to drive cars on a special test course.",
            "The course is extremely tough because it has steep hills and sharp curves.",
            "His basic philosophy is to test cars until they completely break.",
            "He believes that a broken part shows the weakest place in the car.",
            "Engineers can make that part stronger to build a much better car step by step.",
            "As a result of this effort, Toyota has been the top car maker in the world for six years in a row.",
        ],
        expected_pass=True,
    ),
    AudioCase(
        audio_type="pass_paraphrase",
        audio_type_ja="一部言い換え（意味は同じ）",
        script=[
            "Akio Toyoda is the chairman of Toyota Motor Corporation, a famous Japanese company.",
            "Although he is 69 years old now, he still tests his company's cars by himself.",
            "He often wears a racing suit and a helmet to drive cars on a special test course.",
            "The course is really hard because it has steep hills and sharp curves.",
            "His basic philosophy is to test cars until they completely break.",
            "He believes that a broken part shows the weakest place in the car.",
            "Engineers can make that part stronger to build a much better car little by little.",
            "Because of this effort, Toyota has been the top car maker in the world for six years in a row.",
        ],
        expected_pass=True,
    ),
    AudioCase(
        audio_type="fail_omission",
        audio_type_ja="文スキップ（文6を沈黙）",
        script=[
            "Akio Toyoda is the chairman of Toyota Motor Corporation, a famous Japanese company.",
            "Although he is 69 years old now, he still tests his company's cars by himself.",
            "He often wears a racing suit and a helmet to drive cars on a special test course.",
            "The course is extremely tough because it has steep hills and sharp curves.",
            "His basic philosophy is to test cars until they completely break.",
            "(この文は読まず、3秒ほど沈黙してから次へ進む)",
            "Engineers can make that part stronger to build a much better car step by step.",
            "As a result of this effort, Toyota has been the top car maker in the world for six years in a row.",
        ],
        expected_pass=False,
    ),
    AudioCase(
        audio_type="fail_semantic",
        audio_type_ja="意味逸脱（文8の内容が違う）",
        script=[
            "Akio Toyoda is the chairman of Toyota Motor Corporation, a famous Japanese company.",
            "Although he is 69 years old now, he still tests his company's cars by himself.",
            "He often wears a racing suit and a helmet to drive cars on a special test course.",
            "The course is extremely tough because it has steep hills and sharp curves.",
            "His basic philosophy is to test cars until they completely break.",
            "He believes that a broken part shows the weakest place in the car.",
            "Engineers can make that part stronger to build a much better car step by step.",
            "Toyota is a very big company in Japan.",
        ],
        expected_pass=False,
    ),
]
