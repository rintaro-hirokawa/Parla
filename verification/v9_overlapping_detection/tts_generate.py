"""V9: オーバーラッピング遅れ検知 — TTS音声生成."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from elevenlabs import ElevenLabs
from elevenlabs.types import VoiceSettings

from config import (
    DEFAULT_SPEED,
    REFERENCE_AUDIO_DIR,
    REFERENCE_VOICE_ID,
    SIMULATED_AUDIO_DIR,
    TTS_MODEL_ID,
    get_elevenlabs_api_key,
)
from models import FAResult, FAWord, TestCase


def _get_client() -> ElevenLabs:
    return ElevenLabs(api_key=get_elevenlabs_api_key())


def _chars_to_words(
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[FAWord]:
    """文字レベルのタイムスタンプを単語レベルに集約する."""
    words: list[FAWord] = []
    current_word = ""
    word_start: float | None = None
    word_end: float = 0.0

    for char, s, e in zip(characters, start_times, end_times):
        if char == " ":
            if current_word:
                words.append(FAWord(
                    text=current_word, start=word_start or 0.0, end=word_end,
                ))
                current_word = ""
                word_start = None
        else:
            if word_start is None:
                word_start = s
            current_word += char
            word_end = e

    if current_word:
        words.append(FAWord(
            text=current_word, start=word_start or 0.0, end=word_end,
        ))

    return words


def generate_reference_audio_with_timestamps(
    text: str,
    passage_id: str,
) -> tuple[Path, FAResult]:
    """模範TTS音声を生成し、同時にタイムスタンプも取得する.

    convert_with_timestamps API を使うことで、FA API 呼び出しなしで
    模範音声の単語タイミングを取得できる。

    Returns:
        (audio_path, FAResult)
    """
    audio_path = REFERENCE_AUDIO_DIR / f"{passage_id}.mp3"
    timestamps_path = REFERENCE_AUDIO_DIR / f"{passage_id}_timestamps.json"

    # キャッシュがあればそれを使う
    if audio_path.exists() and timestamps_path.exists():
        print(f"  スキップ（既存）: {audio_path.name}")
        with open(timestamps_path, encoding="utf-8") as f:
            fa_data = json.load(f)
        return audio_path, FAResult.model_validate(fa_data)

    print(f"  模範音声+タイムスタンプを生成中: {passage_id}")
    client = _get_client()
    response = client.text_to_speech.convert_with_timestamps(
        voice_id=REFERENCE_VOICE_ID,
        text=text,
        model_id=TTS_MODEL_ID,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(speed=DEFAULT_SPEED),
    )

    # 音声を保存
    audio_bytes = base64.b64decode(response.audio_base_64)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    # タイムスタンプを単語レベルに変換
    alignment = response.normalized_alignment or response.alignment
    if alignment is None:
        raise ValueError("TTS API がタイムスタンプを返しませんでした")

    words = _chars_to_words(
        alignment.characters,
        alignment.character_start_times_seconds,
        alignment.character_end_times_seconds,
    )
    fa_result = FAResult(words=words, source="tts_timestamps")

    # タイムスタンプをキャッシュ
    with open(timestamps_path, "w", encoding="utf-8") as f:
        json.dump(fa_result.model_dump(), f, ensure_ascii=False, indent=2)

    print(f"    {len(words)} words, duration={words[-1].end:.1f}s")
    return audio_path, fa_result


def generate_audio(
    text: str,
    voice_id: str,
    speed: float,
    output_path: Path,
) -> Path:
    """ElevenLabs TTS で音声を生成し、mp3ファイルとして保存する."""
    client = _get_client()
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=TTS_MODEL_ID,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(speed=speed),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_iter:
            f.write(chunk)
    return output_path


def generate_simulated_audio(case: TestCase) -> Path:
    """模擬ユーザー音声を生成する."""
    output_path = SIMULATED_AUDIO_DIR / f"{case.case_id}.mp3"
    if output_path.exists():
        print(f"  スキップ（既存）: {output_path.name}")
        return output_path

    if case.delayed_segments:
        return _generate_phrase_delayed_audio(case, output_path)

    print(f"  模擬音声を生成中: {case.case_id} (speed={case.speed})")
    return generate_audio(case.passage_text, case.voice_id, case.speed, output_path)


def _generate_phrase_delayed_audio(case: TestCase, output_path: Path) -> Path:
    """フレーズ単位で速度を変えた音声を生成し pydub で結合する."""
    from pydub import AudioSegment

    words = case.passage_text.split()
    segments_config: list[tuple[str, float]] = []

    prev_end = 0
    for seg in case.delayed_segments:
        if seg.start_word > prev_end:
            normal_text = " ".join(words[prev_end:seg.start_word])
            segments_config.append((normal_text, case.speed))
        delayed_text = " ".join(words[seg.start_word:seg.end_word])
        segments_config.append((delayed_text, seg.speed))
        prev_end = seg.end_word

    if prev_end < len(words):
        remaining_text = " ".join(words[prev_end:])
        segments_config.append((remaining_text, case.speed))

    print(f"  フレーズ分割音声を生成中: {case.case_id} ({len(segments_config)} segments)")

    combined = AudioSegment.empty()
    for i, (text, speed) in enumerate(segments_config):
        seg_path = SIMULATED_AUDIO_DIR / f"{case.case_id}_seg{i}.mp3"
        generate_audio(text, case.voice_id, speed, seg_path)
        segment_audio = AudioSegment.from_mp3(seg_path)
        combined += segment_audio
        seg_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, format="mp3")
    print(f"  結合完了: {output_path.name}")
    return output_path


def generate_all_audio(cases: list[TestCase]) -> dict[str, FAResult]:
    """全テストケースの音声を生成する.

    Returns:
        パッセージID → 模範FAResult のマッピング（TTSタイムスタンプ由来）
    """
    reference_timestamps: dict[str, FAResult] = {}

    seen_passages: set[str] = set()
    for case in cases:
        passage_id = _get_passage_id(case)
        if passage_id not in seen_passages:
            _, fa_result = generate_reference_audio_with_timestamps(
                case.passage_text, passage_id,
            )
            reference_timestamps[passage_id] = fa_result
            seen_passages.add(passage_id)

    for case in cases:
        generate_simulated_audio(case)

    return reference_timestamps


def _get_passage_id(case: TestCase) -> str:
    for pat in ("sync", "stumble", "no_linking", "gradual", "different_voice"):
        if case.case_id.endswith(f"_{pat}"):
            return case.case_id[: -len(f"_{pat}")]
    return case.case_id.rsplit("_", 1)[0]


if __name__ == "__main__":
    from test_cases import build_test_cases

    cases = build_test_cases()
    ref_ts = generate_all_audio(cases)
    print(f"\n音声生成完了 (模範タイムスタンプ: {len(ref_ts)} passages)")
    for pid, fa in ref_ts.items():
        print(f"  {pid}: {len(fa.words)} words")
