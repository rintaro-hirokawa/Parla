# リファレンス実装

``` python
"""2段階LLM音声解析クライアント.

Stage 1 (Gemini): 音声ファイル → ユーザー発話のテキスト化
Stage 2 (任意LLM): テキスト → 模範解答・学習項目の生成
"""

import base64
import logging
from pathlib import Path

import litellm
from pydantic import ValidationError
from tenacity import retry, stop_after_delay, wait_exponential

from catapult_core.models import SpeechFeedback, TranscriptionResult

logger = logging.getLogger(__name__)

RETRY_MAX_DELAY = 120  # seconds
RETRY_MIN_WAIT = 2
RETRY_MAX_WAIT = 30

# --- Stage 1: 音声 → テキスト化 (Gemini) ---

TRANSCRIPTION_PROMPT_TEMPLATE = """\
You are a speech transcription assistant for English language learners.

The learner was given the following Japanese sentence and asked to say it in English:
Japanese prompt: {sentence_ja}

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

# --- Stage 2: テキスト → フィードバック (任意LLM) ---

EVALUATION_PROMPT_TEMPLATE = """\
You are an expert English tutor reviewing a learner's spoken response.

Target CEFR level: {cefr_level}
Japanese prompt (what the learner was asked to say): {sentence_ja}
Reference answer: {answer_en}
Learner's actual utterance: {user_utterance}

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

Guidelines:
- The "expression" field does NOT have to be a specific English phrase. \
When the gap is a broader pattern or rule, use an abstract/generalized form instead. \
Example: if the learner couldn't say "3:14:50 PM", don't write "3:14:50 PM" as the expression. \
Instead, write "時刻の英語表現 (何時何分何秒)" — a reusable pattern the learner can apply broadly.
- Prioritize generality: each learning item should be useful beyond this single sentence. \
Ask yourself: "Will the learner encounter this pattern again?" If the item is too niche \
or only applies to this exact sentence, generalize it or skip it.
- The "explanation" field (in Japanese) should briefly explain the pattern and give 1-2 short examples.

Bad examples:
- "Practice more natural phrasing." (too vague, not actionable)
- "the key to success" (too specific to this sentence, not reusable)

Good examples:
- expression: "take advantage of ~", explanation: "〜を活用する。'use' より自然な表現。例: take advantage of the opportunity"
- expression: "時刻の英語表現 (何時何分何秒)", explanation: "3:14 → three fourteen / three-fourteen。秒まで言う場合: 3:14:50 → three fourteen and fifty seconds"
- expression: "可算名詞と不可算名詞の使い分け", explanation: "information, advice, furniture などは不可算。× an information → ○ a piece of information"

Respond as a JSON object with these fields:
- model_answer (str)
- is_acceptable (bool)
- learning_items (list of objects with "expression" (str) and "explanation" (str, in Japanese))\
"""


class SpeechAnalysisError(Exception):
    """音声解析が最大リトライ後も失敗した場合のエラー."""


class SpeechAnalysisClient:
    """2段階パイプラインで音声解析を行うクライアント.

    Stage 1: Gemini で音声をテキスト化
    Stage 2: 任意の LLM でフィードバック生成
    """

    def __init__(
        self,
        transcription_model: str = "gemini/gemini-3.1-pro-preview",
        evaluation_model: str = "anthropic/claude-opus-4-6",
        max_retry_delay: int = RETRY_MAX_DELAY,
        *,
        debug: bool = False,
    ) -> None:
        self._transcription_model = transcription_model
        self._evaluation_model = evaluation_model
        self._max_retry_delay = max_retry_delay
        if debug:
            litellm._turn_on_debug()

    def analyze(
        self,
        audio_path: Path,
        sentence_ja: str,
        answer_en: str,
        cefr_level: str,
    ) -> SpeechFeedback:
        """音声を2段階で解析し、SpeechFeedbackを返す.

        Stage 1: 音声 → ユーザー発話テキスト (Gemini)
        Stage 2: テキスト → 模範解答・学習項目 (任意LLM)

        Raises:
            SpeechAnalysisError: いずれかのステージが最大リトライ後も失敗した場合

        """
        # Stage 1: Transcription
        try:
            transcription = self._transcribe(audio_path, sentence_ja)
        except Exception as e:
            msg = f"Stage 1 (音声テキスト化) に失敗しました: {e}"
            raise SpeechAnalysisError(msg) from e

        logger.info("Stage 1 完了: user_utterance=%s", transcription.user_utterance)

        # Stage 2: Evaluation
        try:
            feedback = self._evaluate(
                user_utterance=transcription.user_utterance,
                sentence_ja=sentence_ja,
                answer_en=answer_en,
                cefr_level=cefr_level,
            )
        except Exception as e:
            msg = f"Stage 2 (フィードバック生成) に失敗しました: {e}"
            raise SpeechAnalysisError(msg) from e

        # Stage 1 の transcription を最終結果に統合
        return SpeechFeedback(
            user_utterance=transcription.user_utterance,
            model_answer=feedback.model_answer,
            is_acceptable=feedback.is_acceptable,
            learning_items=feedback.learning_items,
        )

    def _transcribe(self, audio_path: Path, sentence_ja: str) -> TranscriptionResult:
        """Stage 1: Gemini で音声をテキスト化する."""
        retryer = retry(
            stop=stop_after_delay(self._max_retry_delay),
            wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
            reraise=True,
        )
        return retryer(self._call_transcription)(audio_path, sentence_ja)

    def _call_transcription(self, audio_path: Path, sentence_ja: str) -> TranscriptionResult:
        """Stage 1 の LLM 呼び出し."""
        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")

        system_prompt = TRANSCRIPTION_PROMPT_TEMPLATE.format(sentence_ja=sentence_ja)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please transcribe this English speech audio."},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_b64,
                            "format": "wav",
                        },
                    },
                ],
            },
        ]

        response = litellm.completion(
            model=self._transcription_model,
            messages=messages,
            response_format=TranscriptionResult,
        )

        raw_content = response.choices[0].message.content
        try:
            return TranscriptionResult.model_validate_json(raw_content)
        except ValidationError:
            logger.warning("Stage 1 バリデーション失敗。リトライします。content=%s", raw_content[:200])
            raise

    def _evaluate(
        self,
        user_utterance: str,
        sentence_ja: str,
        answer_en: str,
        cefr_level: str,
    ) -> SpeechFeedback:
        """Stage 2: テキストからフィードバックを生成する."""
        retryer = retry(
            stop=stop_after_delay(self._max_retry_delay),
            wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
            reraise=True,
        )
        return retryer(self._call_evaluation)(
            user_utterance=user_utterance,
            sentence_ja=sentence_ja,
            answer_en=answer_en,
            cefr_level=cefr_level,
        )

    def _call_evaluation(
        self,
        user_utterance: str,
        sentence_ja: str,
        answer_en: str,
        cefr_level: str,
    ) -> SpeechFeedback:
        """Stage 2 の LLM 呼び出し."""
        system_prompt = EVALUATION_PROMPT_TEMPLATE.format(
            cefr_level=cefr_level,
            sentence_ja=sentence_ja,
            answer_en=answer_en,
            user_utterance=user_utterance,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please evaluate this learner's response and provide feedback."},
        ]

        response = litellm.completion(
            model=self._evaluation_model,
            messages=messages,
            response_format=SpeechFeedback,
        )

        raw_content = response.choices[0].message.content
        try:
            return SpeechFeedback.model_validate_json(raw_content)
        except ValidationError:
            logger.warning("Stage 2 バリデーション失敗。リトライします。content=%s", raw_content[:200])
            raise
```