"""V9: オーバーラッピング遅れ検知 — データモデル."""

from __future__ import annotations

from pydantic import BaseModel


# --- Forced Alignment API 出力 ---


class FAWord(BaseModel):
    """単語レベルのタイミング情報.

    FA API 由来の場合は loss あり。TTS with timestamps 由来の場合は loss なし。
    """

    text: str
    start: float  # 秒
    end: float
    loss: float = 0.0  # アライメント信頼度（低いほど良い）。TTS由来は0.0


class FAResult(BaseModel):
    """単語タイミング情報の集合.

    FA API または TTS with timestamps のどちらからでも生成可能。
    """

    words: list[FAWord]
    loss: float = 0.0  # 全体のアライメント信頼度。TTS由来は0.0
    source: str = "forced_alignment"  # "forced_alignment" or "tts_timestamps"


# --- 遅れ検出 ---


class WordDelay(BaseModel):
    """単語レベルの遅れ情報."""

    word: str
    word_index: int
    reference_start: float
    user_start: float
    delay_sec: float  # user_start - reference_start（正規化済み）
    is_delayed: bool
    reference_loss: float
    user_loss: float


class PhraseDelay(BaseModel):
    """フレーズレベルの遅れ情報."""

    phrase: str
    word_indices: list[int]
    avg_delay_sec: float
    max_delay_sec: float
    is_delayed: bool


class HighLossWord(BaseModel):
    """FA loss が高い単語（発音不明瞭 / スキップ / 言い間違いの可能性）."""

    word: str
    word_index: int
    loss: float


class DelayDetectionResult(BaseModel):
    """遅れ検出の全体結果."""

    word_delays: list[WordDelay]
    phrase_delays: list[PhraseDelay]
    delayed_phrase_count: int
    total_phrase_count: int
    offset_sec: float  # 正規化に使った先頭オフセット
    high_loss_words: list[HighLossWord] = []


# --- LLM フィードバック ---


class PhraseFeedback(BaseModel):
    """LLM が生成する各フレーズのフィードバック."""

    phrase: str
    delay_sec: float
    estimated_cause: str  # pronunciation_difficulty / vocabulary_recall / syntactic_complexity / discourse_boundary
    suggestion: str


class LLMFeedback(BaseModel):
    """LLM が生成するフィードバック全体."""

    delayed_phrases: list[PhraseFeedback]
    overall_comment: str


# --- Azure Pronunciation Assessment ---


class PronWordResult(BaseModel):
    """Azure Pronunciation Assessment の単語レベル結果."""

    word: str
    accuracy_score: float  # 0-100
    error_type: str  # None / Omission / Insertion / Mispronunciation
    offset_sec: float = -1.0  # 音声先頭からの開始時刻（秒）。-1 は未取得
    duration_sec: float = 0.0  # 単語の発話時間（秒）


class PronunciationResult(BaseModel):
    """Azure Pronunciation Assessment の全体結果."""

    words: list[PronWordResult]
    accuracy_score: float  # 全体 0-100
    fluency_score: float
    completeness_score: float
    prosody_score: float
    pronunciation_score: float  # 総合


# --- テストケース ---


class DelayedSegment(BaseModel):
    """フレーズ遅延音声生成用: 遅延させるセグメント."""

    start_word: int  # 開始単語インデックス（0始まり）
    end_word: int  # 終了単語インデックス（exclusive）
    speed: float


class TestCase(BaseModel):
    """テストケース定義."""

    case_id: str
    passage_text: str  # パッセージ全体の英文
    pattern: str  # sync / slow_uniform / slow_phrase / fast / different_voice
    speed: float  # 全体速度（slow_phrase の場合はデフォルト部分の速度）
    voice_id: str  # 模擬ユーザー用 Voice ID
    delayed_segments: list[DelayedSegment]  # slow_phrase 用
    delayed_word_indices: list[int]  # ground truth: 遅延させた単語インデックス


# --- 実験結果 ---


class ExperimentResult(BaseModel):
    """1テストケースの実験結果."""

    case_id: str
    pattern: str
    # 検知精度
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    # レイテンシ (ms)
    fa_user_latency_ms: float  # ユーザー音声の FA 呼び出し
    llm_latency_ms: float
    total_latency_ms: float  # FA + LLM（模範側 TTS タイムスタンプはキャッシュ前提）
    # FA 信頼度
    user_loss: float
    # 遅れ検出サマリ
    delayed_phrase_count: int
    total_phrase_count: int
    # LLM フィードバック
    feedback: LLMFeedback | None
    timestamp: str
