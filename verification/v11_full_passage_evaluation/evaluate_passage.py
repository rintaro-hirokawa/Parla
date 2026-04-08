"""V11: Azure ストリーミング Pronunciation Assessment + プログラム判定パイプライン."""

from __future__ import annotations

import difflib
import json
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from verification.v11_full_passage_evaluation.config import V11Config, get_azure_speech_key, get_azure_speech_region
from verification.v11_full_passage_evaluation.models import (
    AzureResult,
    DiffSegment,
    PassageEvaluation,
    RecognizedWord,
    SentenceResult,
)
from verification.v11_full_passage_evaluation.test_cases import Passage

TICKS_PER_SECOND = 10_000_000  # Azure Offset は 100ナノ秒単位
CHUNK_SIZE = 3200  # 100ms @ 16kHz, 16bit, mono


@dataclass
class PipelineResult:
    evaluation: PassageEvaluation
    stream_latency_seconds: float  # 音声送信完了から最終 recognized コールバック到着まで
    postprocess_latency_seconds: float  # 後処理（difflib + 文判定）の所要時間
    total_latency_seconds: float  # stream_latency + postprocess_latency（ユーザー体感レイテンシ）


def _read_wav_data(audio_path: Path) -> tuple[bytes, int, int, int]:
    """WAV ファイルからヘッダーを解析し、(pcm_data, sample_rate, bits_per_sample, channels) を返す."""
    with open(audio_path, "rb") as f:
        # RIFF header
        riff, size, wave = struct.unpack("<4sI4s", f.read(12))
        assert riff == b"RIFF" and wave == b"WAVE"

        # Find fmt chunk
        while True:
            chunk_id, chunk_size = struct.unpack("<4sI", f.read(8))
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack(
                    "<HHIIHH", fmt_data[:16]
                )
                break
            else:
                f.seek(chunk_size, 1)

        # Find data chunk
        while True:
            chunk_id, chunk_size = struct.unpack("<4sI", f.read(8))
            if chunk_id == b"data":
                pcm_data = f.read(chunk_size)
                break
            else:
                f.seek(chunk_size, 1)

    return pcm_data, sample_rate, bits_per_sample, channels


def _stream_audio_to_azure(
    audio_path: Path,
    reference_text: str,
    config: V11Config,
) -> AzureResult:
    """Azure Pronunciation Assessment をストリーミングモードで実行."""
    pcm_data, sample_rate, bits_per_sample, channels = _read_wav_data(audio_path)

    # PushAudioInputStream セットアップ
    audio_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=sample_rate,
        bits_per_sample=bits_per_sample,
        channels=channels,
    )
    stream = speechsdk.audio.PushAudioInputStream(audio_format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # Speech / Pronunciation Assessment 設定
    speech_config = speechsdk.SpeechConfig(
        subscription=get_azure_speech_key(),
        region=get_azure_speech_region(),
    )
    speech_config.speech_recognition_language = config.language

    pron_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,  # 連続認識モード（30秒超）では False 必須
    )
    pron_config.enable_prosody_assessment()

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    pron_config.apply_to(recognizer)

    # 結果蓄積用
    all_words: list[RecognizedWord] = []
    utterance_summaries: list[dict] = []
    recognized_texts: list[str] = []
    done = threading.Event()
    last_result_time = [0.0]  # ミュータブルで共有

    def on_recognized(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return

        last_result_time[0] = time.perf_counter()

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
        recognized_texts.append(data.get("DisplayText", ""))

        pron_assess = best.get("PronunciationAssessment", {})
        utterance_summaries.append({
            "accuracy_score": pron_assess.get("AccuracyScore", 0),
            "fluency_score": pron_assess.get("FluencyScore", 0),
            "completeness_score": pron_assess.get("CompletenessScore", 0),
            "pronunciation_score": pron_assess.get("PronScore", 0),
        })

        for w in best.get("Words", []):
            pa = w.get("PronunciationAssessment", {})
            all_words.append(RecognizedWord(
                word=w["Word"],
                accuracy_score=pa.get("AccuracyScore", 0),
                error_type=pa.get("ErrorType", "None"),
                offset_sec=w["Offset"] / TICKS_PER_SECOND,
                duration_sec=w["Duration"] / TICKS_PER_SECOND,
            ))

    def on_session_stopped(evt: speechsdk.SessionEventArgs) -> None:
        done.set()

    def on_canceled(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
        if evt.reason == speechsdk.CancellationReason.Error:
            print(f"    ERROR: {evt.error_details}")
        done.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.session_stopped.connect(on_session_stopped)
    recognizer.canceled.connect(on_canceled)

    # ストリーミング開始
    recognizer.start_continuous_recognition()

    # 音声データをリアルタイム速度でチャンク送信
    bytes_per_second = sample_rate * (bits_per_sample // 8) * channels
    chunk_duration = CHUNK_SIZE / bytes_per_second
    offset = 0
    stream_start = time.perf_counter()

    while offset < len(pcm_data):
        chunk = pcm_data[offset:offset + CHUNK_SIZE]
        stream.write(chunk)
        offset += CHUNK_SIZE
        # リアルタイム速度でストリーム
        elapsed = time.perf_counter() - stream_start
        expected = offset / bytes_per_second
        if expected > elapsed:
            time.sleep(expected - elapsed)

    stream_finish_time = time.perf_counter()
    stream.close()

    # 最終結果待ち
    done.wait(timeout=30)
    recognizer.stop_continuous_recognition()

    # ストリーム終了から最終結果到着までのレイテンシ
    stream_latency = last_result_time[0] - stream_finish_time if last_result_time[0] > 0 else 0

    # 全体スコア集計
    if utterance_summaries:
        n = len(utterance_summaries)
        accuracy = sum(u["accuracy_score"] for u in utterance_summaries) / n
        fluency = sum(u["fluency_score"] for u in utterance_summaries) / n
        completeness = sum(u.get("completeness_score", 0) or 0 for u in utterance_summaries) / n
        pron_score = sum(u["pronunciation_score"] for u in utterance_summaries) / n
    else:
        accuracy = fluency = completeness = pron_score = 0.0

    return AzureResult(
        recognized_words=all_words,
        recognized_text=" ".join(recognized_texts),
        accuracy_score=accuracy,
        fluency_score=fluency,
        completeness_score=completeness,
        pronunciation_score=pron_score,
        latency_seconds=stream_latency,
    )


def _apply_miscue_detection(
    reference_words: list[str],
    recognized_words: list[RecognizedWord],
) -> list[RecognizedWord]:
    """difflib で Omission/Insertion を検出する（V9 と同じロジック）."""
    recognized_lower = [w.word.lower().strip(".,!?;:") for w in recognized_words]
    ref_lower = [w.lower().strip(".,!?;:") for w in reference_words]

    diff = difflib.SequenceMatcher(None, ref_lower, recognized_lower)
    final_words: list[RecognizedWord] = []

    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for idx, k in enumerate(range(j1, j2)):
                w = recognized_words[k]
                final_words.append(RecognizedWord(
                    word=reference_words[i1 + idx],
                    accuracy_score=w.accuracy_score,
                    error_type=w.error_type,
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))
        elif tag == "delete":
            for k in range(i1, i2):
                final_words.append(RecognizedWord(
                    word=reference_words[k],
                    accuracy_score=0.0,
                    error_type="Omission",
                ))
        elif tag == "insert":
            for k in range(j1, j2):
                w = recognized_words[k]
                final_words.append(RecognizedWord(
                    word=w.word,
                    accuracy_score=0.0,
                    error_type="Insertion",
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))
        elif tag == "replace":
            for k in range(i1, i2):
                final_words.append(RecognizedWord(
                    word=reference_words[k],
                    accuracy_score=0.0,
                    error_type="Omission",
                ))
            for k in range(j1, j2):
                w = recognized_words[k]
                final_words.append(RecognizedWord(
                    word=w.word,
                    accuracy_score=0.0,
                    error_type="Insertion",
                    offset_sec=w.offset_sec,
                    duration_sec=w.duration_sec,
                ))

    return final_words


def _map_words_to_sentences(
    passage: Passage,
    final_words: list[RecognizedWord],
) -> list[SentenceResult]:
    """模範解答の単語列を文ごとに区切り、認識結果と比較して SentenceResult を生成."""
    # 模範の単語を文ごとに分割
    sentence_word_ranges: list[tuple[int, int]] = []
    word_offset = 0
    for s in passage.sentences:
        n_words = len(s.model_answer.split())
        sentence_word_ranges.append((word_offset, word_offset + n_words))
        word_offset += n_words

    # final_words から Insertion を除いた模範対応単語列
    ref_aligned = [w for w in final_words if w.error_type != "Insertion"]

    results: list[SentenceResult] = []
    for s in passage.sentences:
        start, end = sentence_word_ranges[s.index - 1]
        sentence_ref_words = ref_aligned[start:end] if start < len(ref_aligned) else []

        # ユーザーが実際に言ったテキスト（Omission を除く）
        user_words = [w.word for w in sentence_ref_words if w.error_type != "Omission"]
        user_text = " ".join(user_words) if user_words else "(no speech)"

        # 類似度計算
        model_lower = s.model_answer.lower()
        user_lower = user_text.lower()
        similarity = difflib.SequenceMatcher(None, model_lower.split(), user_lower.split()).ratio()

        # Omission の割合
        omission_count = sum(1 for w in sentence_ref_words if w.error_type == "Omission")
        omission_ratio = omission_count / max(len(sentence_ref_words), 1)

        # status 判定
        if omission_ratio > 0.5:
            status = "error"
        elif similarity >= 0.90:
            status = "correct"
        elif similarity >= 0.50:
            status = "paraphrase"
        else:
            status = "error"

        # diff_segments 生成
        diff_segments: list[DiffSegment] = []
        if status != "correct":
            model_words = s.model_answer.split()
            matcher = difflib.SequenceMatcher(None, model_words, user_words)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue
                m_part = " ".join(model_words[i1:i2])
                u_part = " ".join(user_words[j1:j2])
                if tag == "delete":
                    note = "欠落" if omission_ratio > 0.5 else "省略"
                elif tag == "insert":
                    note = "追加"
                elif tag == "replace":
                    note = "語彙の言い換え" if status == "paraphrase" else "意味の相違"
                else:
                    note = "差分"
                diff_segments.append(DiffSegment(
                    user_part=u_part,
                    model_part=m_part,
                    note=note,
                ))

        results.append(SentenceResult(
            index=s.index,
            status=status,
            user_text=user_text,
            model_text=s.model_answer,
            diff_segments=diff_segments,
            similarity=similarity,
        ))

    return results


def run_pipeline(
    audio_path: Path,
    passage: Passage,
    config: V11Config,
) -> PipelineResult:
    """Azure ストリーミング + プログラム判定パイプライン."""
    reference_text = passage.full_reference_text()

    # Azure ストリーミング実行
    print("  Azure ストリーミング実行中...")
    azure_result = _stream_audio_to_azure(audio_path, reference_text, config)
    print(f"  Azure 完了: {len(azure_result.recognized_words)} words, "
          f"stream latency={azure_result.latency_seconds:.2f}s")

    # 後処理の計時開始
    postprocess_start = time.perf_counter()

    # Omission/Insertion 後処理
    ref_words = reference_text.split()
    final_words = _apply_miscue_detection(ref_words, azure_result.recognized_words)

    # 文ごとの添削
    sentence_results = _map_words_to_sentences(passage, final_words)

    # 全体判定
    passed = all(s.status in ("correct", "paraphrase") for s in sentence_results)

    postprocess_latency = time.perf_counter() - postprocess_start
    total_latency = azure_result.latency_seconds + postprocess_latency
    print(f"  後処理: {postprocess_latency:.4f}s / 合計レイテンシ: {total_latency:.2f}s")
    print(f"  判定: {'PASS' if passed else 'FAIL'}")

    evaluation = PassageEvaluation(
        passed=passed,
        sentences=sentence_results,
        azure=azure_result,
    )

    return PipelineResult(
        evaluation=evaluation,
        stream_latency_seconds=azure_result.latency_seconds,
        postprocess_latency_seconds=postprocess_latency,
        total_latency_seconds=total_latency,
    )
