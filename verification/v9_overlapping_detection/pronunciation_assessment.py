"""V9: Azure Pronunciation Assessment — 発音評価 + タイミング情報.

連続認識モードで30秒超の音声に対応。
Omission/Insertion は difflib.SequenceMatcher による後処理で検出。
生 JSON レスポンスから Offset/Duration を抽出してタイミング偏差も計算。

Usage:
    uv run python pronunciation_assessment.py <audio_path> [passage_id]
"""

from __future__ import annotations

import difflib
import json
import sys
import threading
import time
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from config import REFERENCE_AUDIO_DIR, get_azure_speech_key, get_azure_speech_region
from models import FAResult, PronunciationResult, PronWordResult

TICKS_PER_SECOND = 10_000_000  # Azure Offset は 100ナノ秒単位


def _collect_continuous_results(
    audio_path: Path,
    reference_text: str,
    language: str,
) -> tuple[list[PronWordResult], list[dict]]:
    """連続認識モードで発音評価を実行し、生 JSON から全情報を収集する."""
    speech_config = speechsdk.SpeechConfig(
        subscription=get_azure_speech_key(),
        region=get_azure_speech_region(),
    )
    speech_config.speech_recognition_language = language

    pron_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,
    )
    pron_config.enable_prosody_assessment()

    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_path))
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    pron_config.apply_to(recognizer)

    all_words: list[PronWordResult] = []
    utterance_summaries: list[dict] = []
    done = threading.Event()

    def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return

        # 生 JSON から Offset/Duration を含む完全な単語情報を取得
        raw_json = evt.result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        if not raw_json:
            return

        data = json.loads(raw_json)
        nbest = data.get("NBest", [])
        if not nbest:
            return

        best = nbest[0]

        # utterance レベルのスコア
        pron_assess = best.get("PronunciationAssessment", {})
        utterance_summaries.append({
            "text": data.get("DisplayText", ""),
            "accuracy_score": pron_assess.get("AccuracyScore", 0),
            "fluency_score": pron_assess.get("FluencyScore", 0),
            "completeness_score": pron_assess.get("CompletenessScore", 0),
            "pronunciation_score": pron_assess.get("PronScore", 0),
            "prosody_score": pron_assess.get("ProsodyScore", 0),
        })

        # 単語レベル（Offset/Duration 含む）
        for w in best.get("Words", []):
            pa = w.get("PronunciationAssessment", {})
            all_words.append(PronWordResult(
                word=w["Word"],
                accuracy_score=pa.get("AccuracyScore", 0),
                error_type=pa.get("ErrorType", "None"),
                offset_sec=w["Offset"] / TICKS_PER_SECOND,
                duration_sec=w["Duration"] / TICKS_PER_SECOND,
            ))

        display = data.get("DisplayText", "")
        print(f"    Recognized: {display[:60]}...")

    def on_session_stopped(evt: speechsdk.SessionEventArgs) -> None:
        done.set()

    def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f"    ERROR: {evt.error_details}")
        done.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.session_stopped.connect(on_session_stopped)
    recognizer.canceled.connect(on_canceled)

    recognizer.start_continuous_recognition()
    done.wait(timeout=120)
    recognizer.stop_continuous_recognition()

    return all_words, utterance_summaries


def _apply_miscue_detection(
    reference_words: list[str],
    recognized_results: list[PronWordResult],
) -> list[PronWordResult]:
    """difflib.SequenceMatcher でリファレンスと認識結果を比較し、
    Omission/Insertion を検出する."""
    recognized_lower = [w.word.lower().strip(".,!?;:") for w in recognized_results]
    ref_lower = [w.lower().strip(".,!?;:") for w in reference_words]

    diff = difflib.SequenceMatcher(None, ref_lower, recognized_lower)
    final_words: list[PronWordResult] = []

    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for idx, k in enumerate(range(j1, j2)):
                w = recognized_results[k]
                final_words.append(PronWordResult(
                    word=reference_words[i1 + idx],
                    accuracy_score=w.accuracy_score,
                    error_type=w.error_type,
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))
        elif tag == "delete":
            for k in range(i1, i2):
                final_words.append(PronWordResult(
                    word=reference_words[k],
                    accuracy_score=0.0,
                    error_type="Omission",
                ))
        elif tag == "insert":
            for k in range(j1, j2):
                w = recognized_results[k]
                final_words.append(PronWordResult(
                    word=w.word,
                    accuracy_score=0.0,
                    error_type="Insertion",
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))
        elif tag == "replace":
            for k in range(i1, i2):
                final_words.append(PronWordResult(
                    word=reference_words[k],
                    accuracy_score=0.0,
                    error_type="Omission",
                ))
            for k in range(j1, j2):
                w = recognized_results[k]
                final_words.append(PronWordResult(
                    word=w.word,
                    accuracy_score=0.0,
                    error_type="Insertion",
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))

    return final_words


def assess_pronunciation(
    audio_path: Path,
    reference_text: str,
    language: str = "en-US",
) -> PronunciationResult:
    """WAV ファイルの発音を評価する（30秒超対応）."""
    print(f"  Azure Pronunciation Assessment...")
    start = time.perf_counter()

    raw_words, utterance_summaries = _collect_continuous_results(
        audio_path, reference_text, language,
    )
    latency = (time.perf_counter() - start) * 1000
    print(f"    {len(raw_words)} words recognized in {latency:.0f}ms")
    print(f"    {len(utterance_summaries)} utterances")

    # Omission/Insertion 後処理
    ref_words = reference_text.split()
    final_words = _apply_miscue_detection(ref_words, raw_words)

    # 全体スコアの集計
    if utterance_summaries:
        n = len(utterance_summaries)
        accuracy = sum(u["accuracy_score"] for u in utterance_summaries) / n
        fluency = sum(u["fluency_score"] for u in utterance_summaries) / n
        completeness = sum(u.get("completeness_score", 0) or 0 for u in utterance_summaries) / n
        prosody = sum(u.get("prosody_score", 0) or 0 for u in utterance_summaries) / n
        pron_score = sum(u["pronunciation_score"] for u in utterance_summaries) / n
    else:
        accuracy = fluency = completeness = prosody = pron_score = 0.0

    return PronunciationResult(
        words=final_words,
        accuracy_score=accuracy,
        fluency_score=fluency,
        completeness_score=completeness,
        prosody_score=prosody,
        pronunciation_score=pron_score,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pronunciation_assessment.py <audio_path> [passage_id]")
        sys.exit(1)

    audio = Path(sys.argv[1])
    passage_id = sys.argv[2] if len(sys.argv) > 2 else "p1"

    ts_path = REFERENCE_AUDIO_DIR / f"{passage_id}_timestamps.json"
    with open(ts_path, encoding="utf-8") as f:
        fa = FAResult.model_validate(json.load(f))
    ref_text = " ".join(w.text for w in fa.words)

    result = assess_pronunciation(audio, ref_text)

    print(f"\n=== Results ===")
    print(f"PronScore: {result.pronunciation_score:.1f}")
    print(f"Accuracy:  {result.accuracy_score:.1f}")
    print(f"Fluency:   {result.fluency_score:.1f}")
    print(f"Completeness: {result.completeness_score:.1f}")
    print(f"Prosody:   {result.prosody_score:.1f}")
    print(f"\nWords ({len(result.words)}):")
    for w in result.words:
        timing = f"  @{w.offset_sec:.2f}s" if w.offset_sec >= 0 else ""
        marker = "" if w.error_type == "None" else f" [{w.error_type}]"
        print(f"  {w.word:20s} accuracy={w.accuracy_score:5.1f}{timing}{marker}")
