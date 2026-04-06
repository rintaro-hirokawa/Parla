"""V5: テストケース定義（5シナリオ × 4音声タイプ）."""

from dataclasses import dataclass


@dataclass
class ExpectedJudgment:
    correct: bool
    item_used: bool


@dataclass
class AudioCase:
    audio_type: str  # correct, alt_correct, partial, incorrect
    audio_type_ja: str
    script: str  # 録音時に話す内容
    expected: ExpectedJudgment


@dataclass
class Scenario:
    id: str  # "s01", "s02", ...
    learning_item: str
    ja_prompt: str
    reference_answer: str
    audio_cases: list[AudioCase]

    def audio_filename(self, audio_type: str) -> str:
        return f"{self.id}_{audio_type}.wav"


SCENARIOS: list[Scenario] = [
    Scenario(
        id="s01",
        learning_item="A is more X than B",
        ja_prompt="この問題は昨日の問題よりも難しいです。",
        reference_answer="This problem is more difficult than yesterday's problem.",
        audio_cases=[
            AudioCase(
                audio_type="correct",
                audio_type_ja="正解",
                script="This problem is more difficult than yesterday's problem.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="alt_correct",
                audio_type_ja="表現違いの正解",
                script="This question is more challenging than the one we had yesterday.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="partial",
                audio_type_ja="部分的に正解",
                script='This problem is more difficult than... (「えっと」) ...yesterday.',
                expected=ExpectedJudgment(correct=False, item_used=True),
            ),
            AudioCase(
                audio_type="incorrect",
                audio_type_ja="不正解",
                script="This problem is very difficult.",
                expected=ExpectedJudgment(correct=False, item_used=False),
            ),
        ],
    ),
    Scenario(
        id="s02",
        learning_item="have/has + past participle (experience)",
        ja_prompt="私はイタリアに3回行ったことがあります。",
        reference_answer="I have been to Italy three times.",
        audio_cases=[
            AudioCase(
                audio_type="correct",
                audio_type_ja="正解",
                script="I have been to Italy three times.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="alt_correct",
                audio_type_ja="表現違いの正解",
                script="I've visited Italy three times.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="partial",
                audio_type_ja="部分的に正解",
                script='I have been to Italy... (「さん」) ...three times.',
                expected=ExpectedJudgment(correct=False, item_used=True),
            ),
            AudioCase(
                audio_type="incorrect",
                audio_type_ja="不正解",
                script="I go to Italy three times.",
                expected=ExpectedJudgment(correct=False, item_used=False),
            ),
        ],
    ),
    Scenario(
        id="s03",
        learning_item="If + present, will + verb",
        ja_prompt="もし明日雨が降ったら、家にいるつもりです。",
        reference_answer="If it rains tomorrow, I will stay at home.",
        audio_cases=[
            AudioCase(
                audio_type="correct",
                audio_type_ja="正解",
                script="If it rains tomorrow, I will stay at home.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="alt_correct",
                audio_type_ja="表現違いの正解",
                script="If it rains tomorrow, I'll stay home.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="partial",
                audio_type_ja="部分的に正解",
                script='If it rains tomorrow, I will... (「うーん」) ...home.',
                expected=ExpectedJudgment(correct=False, item_used=True),
            ),
            AudioCase(
                audio_type="incorrect",
                audio_type_ja="不正解",
                script="Tomorrow rain, I stay home.",
                expected=ExpectedJudgment(correct=False, item_used=False),
            ),
        ],
    ),
    Scenario(
        id="s04",
        learning_item="be + past participle (passive)",
        ja_prompt="この本は多くの言語に翻訳されています。",
        reference_answer="This book has been translated into many languages.",
        audio_cases=[
            AudioCase(
                audio_type="correct",
                audio_type_ja="正解",
                script="This book has been translated into many languages.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="alt_correct",
                audio_type_ja="表現違いの正解",
                script="This book is translated into a lot of languages.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="partial",
                audio_type_ja="部分的に正解",
                script='This book has been translated... (「何だっけ」) ...many languages.',
                expected=ExpectedJudgment(correct=False, item_used=True),
            ),
            AudioCase(
                audio_type="incorrect",
                audio_type_ja="不正解",
                script="Many people translated this book.",
                expected=ExpectedJudgment(correct=False, item_used=False),
            ),
        ],
    ),
    Scenario(
        id="s05",
        learning_item="used to + verb",
        ja_prompt="子供の頃、毎日公園で遊んでいたものです。",
        reference_answer="I used to play in the park every day when I was a child.",
        audio_cases=[
            AudioCase(
                audio_type="correct",
                audio_type_ja="正解",
                script="I used to play in the park every day when I was a child.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="alt_correct",
                audio_type_ja="表現違いの正解",
                script="When I was a kid, I used to play at the park every day.",
                expected=ExpectedJudgment(correct=True, item_used=True),
            ),
            AudioCase(
                audio_type="partial",
                audio_type_ja="部分的に正解",
                script='I used to play in the park... (「毎日」) ...every day child.',
                expected=ExpectedJudgment(correct=False, item_used=True),
            ),
            AudioCase(
                audio_type="incorrect",
                audio_type_ja="不正解",
                script="I played in the park.",
                expected=ExpectedJudgment(correct=False, item_used=False),
            ),
        ],
    ),
]
