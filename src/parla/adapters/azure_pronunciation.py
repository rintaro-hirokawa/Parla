"""Azure Speech Service Pronunciation Assessment adapter (streaming).

Uses PushAudioInputStream for low-latency (~1.2s post-utterance) assessment.
Supports 30s+ audio via continuous recognition with enable_miscue=False.
Includes difflib post-processing for Omission/Insertion detection.

Implementation informed by V9/V11 verification results.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from parla.ports.pronunciation_assessment import RawAssessedWord, RawAssessmentResult

if TYPE_CHECKING:
    from parla.domain.audio import AudioData

logger = structlog.get_logger()

TICKS_PER_SECOND = 10_000_000  # Azure Offset is in 100-nanosecond units
CHUNK_SIZE = 3200  # 100ms @ 16kHz, 16bit, mono


def _get_speech_key() -> str:
    key = os.environ.get("AZURE_SPEECH_KEY", "")
    if not key:
        msg = "AZURE_SPEECH_KEY not set"
        raise RuntimeError(msg)
    return key


def _get_speech_region() -> str:
    return os.environ.get("AZURE_SPEECH_REGION", "japaneast")


@dataclass
class _StreamingState:
    """Mutable state shared between streaming thread and callbacks."""

    words: list[dict[str, Any]] = field(default_factory=list)
    utterance_scores: list[dict[str, Any]] = field(default_factory=list)
    recognized_texts: list[str] = field(default_factory=list)
    done: threading.Event = field(default_factory=threading.Event)
    error: str | None = None


def _run_streaming_assessment(
    audio: AudioData,
    reference_text: str,
) -> tuple[_StreamingState, float]:
    """Run Azure streaming pronunciation assessment (blocking).

    Returns (state, stream_latency_seconds).
    """
    import azure.cognitiveservices.speech as speechsdk

    # PushAudioInputStream setup
    audio_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=audio.sample_rate,
        bits_per_sample=audio.sample_width * 8,
        channels=audio.channels,
    )
    stream = speechsdk.audio.PushAudioInputStream(audio_format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # Speech / Pronunciation Assessment config
    speech_config = speechsdk.SpeechConfig(
        subscription=_get_speech_key(),
        region=_get_speech_region(),
    )
    speech_config.speech_recognition_language = "en-US"

    pron_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,  # Required for continuous recognition (30s+)
    )
    pron_config.enable_prosody_assessment()

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    pron_config.apply_to(recognizer)

    state = _StreamingState()
    last_result_time = [0.0]

    def on_recognized(evt: Any) -> None:
        if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech:
            return
        last_result_time[0] = time.perf_counter()

        raw_json = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        if not raw_json:
            return

        data = json.loads(raw_json)
        nbest = data.get("NBest", [])
        if not nbest:
            return

        best = nbest[0]
        state.recognized_texts.append(data.get("DisplayText", ""))

        pron_assess = best.get("PronunciationAssessment", {})
        state.utterance_scores.append(
            {
                "accuracy_score": pron_assess.get("AccuracyScore", 0),
                "fluency_score": pron_assess.get("FluencyScore", 0),
                "completeness_score": pron_assess.get("CompletenessScore", 0),
                "pronunciation_score": pron_assess.get("PronScore", 0),
                "prosody_score": pron_assess.get("ProsodyScore", 0),
            }
        )

        for w in best.get("Words", []):
            pa = w.get("PronunciationAssessment", {})
            state.words.append(
                {
                    "word": w["Word"],
                    "accuracy_score": pa.get("AccuracyScore", 0),
                    "error_type": pa.get("ErrorType", "None"),
                    "offset_seconds": w["Offset"] / TICKS_PER_SECOND,
                    "duration_seconds": w["Duration"] / TICKS_PER_SECOND,
                }
            )

    def on_session_stopped(evt: Any) -> None:
        state.done.set()

    def on_canceled(evt: Any) -> None:
        if evt.reason == speechsdk.CancellationReason.Error:
            state.error = evt.error_details
        state.done.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.session_stopped.connect(on_session_stopped)
    recognizer.canceled.connect(on_canceled)

    # Start continuous recognition
    recognizer.start_continuous_recognition()

    # Stream audio in real-time 100ms chunks
    pcm_data = audio.data
    bytes_per_second = audio.sample_rate * audio.sample_width * audio.channels
    offset = 0
    stream_start = time.perf_counter()

    while offset < len(pcm_data):
        chunk = pcm_data[offset : offset + CHUNK_SIZE]
        stream.write(chunk)
        offset += CHUNK_SIZE
        elapsed = time.perf_counter() - stream_start
        expected = offset / bytes_per_second
        if expected > elapsed:
            time.sleep(expected - elapsed)

    stream_finish_time = time.perf_counter()
    stream.close()

    # Wait for final result
    state.done.wait(timeout=30)
    recognizer.stop_continuous_recognition()

    stream_latency = last_result_time[0] - stream_finish_time if last_result_time[0] > 0 else 0

    return state, stream_latency


def _apply_difflib_miscue(
    reference_words: list[str],
    recognized_words: list[dict[str, Any]],
) -> list[RawAssessedWord]:
    """Apply difflib post-processing for Omission/Insertion detection.

    Azure continuous recognition mode with enable_miscue=False does not
    report Omission/Insertion. This function uses difflib.SequenceMatcher
    to align reference words with recognized words and detect miscues.
    """
    rec_normalized = [w["word"].lower().strip(".,!?;:") for w in recognized_words]
    ref_normalized = [w.lower().strip(".,!?;:") for w in reference_words]

    diff = difflib.SequenceMatcher(None, ref_normalized, rec_normalized)
    result: list[RawAssessedWord] = []

    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for idx, k in enumerate(range(j1, j2)):
                w = recognized_words[k]
                result.append(
                    RawAssessedWord(
                        word=reference_words[i1 + idx],
                        accuracy_score=w["accuracy_score"],
                        error_type=w["error_type"],
                        offset_seconds=w["offset_seconds"],
                        duration_seconds=w["duration_seconds"],
                    )
                )
        elif tag == "delete":
            for k in range(i1, i2):
                result.append(
                    RawAssessedWord(
                        word=reference_words[k],
                        accuracy_score=0.0,
                        error_type="Omission",
                        offset_seconds=-1.0,
                        duration_seconds=0.0,
                    )
                )
        elif tag == "insert":
            for k in range(j1, j2):
                w = recognized_words[k]
                result.append(
                    RawAssessedWord(
                        word=w["word"],
                        accuracy_score=0.0,
                        error_type="Insertion",
                        offset_seconds=w["offset_seconds"],
                        duration_seconds=w["duration_seconds"],
                    )
                )
        elif tag == "replace":
            for k in range(i1, i2):
                result.append(
                    RawAssessedWord(
                        word=reference_words[k],
                        accuracy_score=0.0,
                        error_type="Omission",
                        offset_seconds=-1.0,
                        duration_seconds=0.0,
                    )
                )
            for k in range(j1, j2):
                w = recognized_words[k]
                result.append(
                    RawAssessedWord(
                        word=w["word"],
                        accuracy_score=0.0,
                        error_type="Insertion",
                        offset_seconds=w["offset_seconds"],
                        duration_seconds=w["duration_seconds"],
                    )
                )

    return result


class AzurePronunciationAdapter:
    """Azure Speech Service Pronunciation Assessment via PushAudioInputStream."""

    async def assess(
        self,
        audio: AudioData,
        reference_text: str,
    ) -> RawAssessmentResult:
        """Assess pronunciation by streaming audio to Azure.

        Bridges sync threading (Azure SDK) with async Python via asyncio.to_thread.
        """
        logger.info(
            "azure_assessment_start",
            audio_duration=audio.duration_seconds,
            reference_length=len(reference_text),
        )

        state, latency = await asyncio.to_thread(
            _run_streaming_assessment,
            audio,
            reference_text,
        )

        if state.error:
            msg = f"Azure recognition error: {state.error}"
            raise RuntimeError(msg)

        logger.info(
            "azure_assessment_stream_done",
            word_count=len(state.words),
            stream_latency=f"{latency:.2f}s",
        )

        # Apply difflib miscue detection
        ref_words = reference_text.split()
        words = _apply_difflib_miscue(ref_words, state.words)

        # Aggregate scores
        if state.utterance_scores:
            n = len(state.utterance_scores)
            accuracy = sum(u["accuracy_score"] for u in state.utterance_scores) / n
            fluency = sum(u["fluency_score"] for u in state.utterance_scores) / n
            completeness = sum(u.get("completeness_score", 0) for u in state.utterance_scores) / n
            prosody = sum(u.get("prosody_score", 0) for u in state.utterance_scores) / n
            pron_score = sum(u["pronunciation_score"] for u in state.utterance_scores) / n
        else:
            accuracy = fluency = completeness = prosody = pron_score = 0.0

        logger.info(
            "azure_assessment_done",
            accuracy=f"{accuracy:.1f}",
            fluency=f"{fluency:.1f}",
            pronunciation=f"{pron_score:.1f}",
            latency=f"{latency:.2f}s",
        )

        return RawAssessmentResult(
            recognized_text=" ".join(state.recognized_texts),
            words=tuple(words),
            accuracy_score=accuracy,
            fluency_score=fluency,
            completeness_score=completeness,
            prosody_score=prosody,
            pronunciation_score=pron_score,
        )
