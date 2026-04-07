"""V9: オーバーラッピング練習 CLI — 録音 → 解析 → 可視化.

模範音声をスピーカーで再生しながらマイクで録音し、
遅れ検知パイプラインで解析して結果を可視化する。

Usage:
    uv run python practice.py
    uv run python practice.py --passage p1 --feedback
"""

from __future__ import annotations

import argparse
import json
import textwrap
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from pydub import AudioSegment
from scipy.io import wavfile

from config import (
    DELAY_THRESHOLD_SEC,
    OUTPUTS_DIR,
    REFERENCE_AUDIO_DIR,
)
from delay_detection import detect_delays
from forced_alignment import run_forced_alignment
from llm_feedback import generate_feedback
from models import FAResult
from visualize import plot_delay_chart


PRACTICE_DIR = OUTPUTS_DIR / "practice"


def _list_passages() -> list[str]:
    """利用可能なパッセージIDを返す."""
    passages = []
    for ts_file in sorted(REFERENCE_AUDIO_DIR.glob("*_timestamps.json")):
        pid = ts_file.stem.replace("_timestamps", "")
        audio_file = REFERENCE_AUDIO_DIR / f"{pid}.mp3"
        if audio_file.exists():
            passages.append(pid)
    return passages


def _load_reference(passage_id: str) -> tuple[Path, FAResult, str]:
    """模範音声パスとタイムスタンプとテキストを読み込む.

    Returns:
        (audio_path, fa_result, passage_text)
    """
    audio_path = REFERENCE_AUDIO_DIR / f"{passage_id}.mp3"
    ts_path = REFERENCE_AUDIO_DIR / f"{passage_id}_timestamps.json"

    if not audio_path.exists():
        raise FileNotFoundError(f"模範音声が見つかりません: {audio_path}")
    if not ts_path.exists():
        raise FileNotFoundError(f"タイムスタンプが見つかりません: {ts_path}")

    with open(ts_path, encoding="utf-8") as f:
        fa_ref = FAResult.model_validate(json.load(f))

    passage_text = " ".join(w.text for w in fa_ref.words)
    return audio_path, fa_ref, passage_text


def _display_passage(passage_id: str, passage_text: str) -> None:
    """パッセージ英文をターミナルに表示する."""
    border = "\u2501" * 60
    print(f"\n{border}")
    print(f"  V9 Overlapping Practice \u2014 Passage {passage_id}")
    print(border)
    print()
    wrapped = textwrap.fill(passage_text, width=60, initial_indent="  ", subsequent_indent="  ")
    print(wrapped)
    print()


def play_and_record(audio_path: Path, extra_seconds: float = 2.0) -> tuple[np.ndarray, int]:
    """模範音声を再生しながらマイクで録音する.

    Returns:
        (recording, sample_rate)
    """
    audio = AudioSegment.from_mp3(audio_path)
    sample_rate = audio.frame_rate
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

    if audio.channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    samples = samples / np.max(np.abs(samples))

    total_duration = len(samples) / sample_rate + extra_seconds
    total_frames = int(total_duration * sample_rate)

    play_data = np.pad(samples, (0, total_frames - len(samples)))

    border = "\u2501" * 60
    print(border)
    print(f"  \U0001f3a4 Recording... ({total_duration:.1f}s)")
    print(f"  Speak along with the model audio!")
    print(border)

    recording = sd.playrec(
        play_data.reshape(-1, 1),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    print("\n  Recording complete.\n")
    return recording.flatten(), sample_rate


def _save_wav(recording: np.ndarray, sample_rate: int, output_path: Path) -> Path:
    """録音を WAV ファイルとして保存する."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    int16_data = (recording * 32767).astype(np.int16)
    wavfile.write(output_path, sample_rate, int16_data)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="V9: Overlapping practice + real-time analysis"
    )
    parser.add_argument(
        "--passage", default="p1", help="Passage ID (default: p1)"
    )
    parser.add_argument(
        "--feedback", action="store_true", help="Generate LLM feedback"
    )
    parser.add_argument(
        "--output", type=Path, default=PRACTICE_DIR,
        help=f"Output directory (default: {PRACTICE_DIR})"
    )
    args = parser.parse_args()

    # 利用可能パッセージ確認
    passages = _list_passages()
    if not passages:
        print("ERROR: No passages found. Run TTS generation first.")
        return
    if args.passage not in passages:
        print(f"ERROR: Passage '{args.passage}' not found. Available: {passages}")
        return

    # 模範データ読み込み
    audio_path, fa_ref, passage_text = _load_reference(args.passage)
    print(f"\nPassage: {args.passage} ({len(fa_ref.words)} words)")

    # 英文表示
    _display_passage(args.passage, passage_text)

    # 再生+録音
    input("  Press Enter to start... ")
    recording, sample_rate = play_and_record(audio_path)

    # 録音保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = args.output / f"{ts}_{args.passage}.wav"
    _save_wav(recording, sample_rate, wav_path)
    print(f"  Recording saved: {wav_path.name}")

    # FA 実行
    print("\n  Running Forced Alignment...")
    fa_user, fa_lat = run_forced_alignment(wav_path, passage_text)
    print(f"    {len(fa_user.words)} words, loss={fa_user.loss:.4f}, {fa_lat:.0f}ms")

    # 遅れ検知
    print("  Detecting delays...")
    detection = detect_delays(fa_ref, fa_user)
    print(f"    Delay regions: {detection.delayed_phrase_count}")
    print(f"    Baseline (shadowing delay): {detection.offset_sec:.3f}s")

    if detection.phrase_delays:
        print("\n  Delayed phrases:")
        for pd in detection.phrase_delays:
            print(f"    [{pd.avg_delay_sec:.2f}s] {pd.phrase}")

    # LLM フィードバック
    feedback = None
    llm_lat = 0.0
    if args.feedback and detection.phrase_delays:
        print("\n  Generating LLM feedback...")
        feedback, llm_lat = generate_feedback(passage_text, detection.phrase_delays)
        print(f"    LLM: {llm_lat:.0f}ms")
        if feedback.delayed_phrases:
            print("\n  Feedback:")
            for pf in feedback.delayed_phrases:
                print(f"    [{pf.estimated_cause}] {pf.phrase}")
                print(f"      {pf.suggestion}")
        if feedback.overall_comment:
            print(f"\n  Overall: {feedback.overall_comment}")

    # 結果保存
    result_data = {
        "passage_id": args.passage,
        "timestamp": ts,
        "fa_latency_ms": fa_lat,
        "llm_latency_ms": llm_lat,
        "baseline_sec": detection.offset_sec,
        "delay_regions": detection.delayed_phrase_count,
        "reference": fa_ref.model_dump(),
        "user": fa_user.model_dump(),
        "detection": detection.model_dump(),
        "feedback": feedback.model_dump() if feedback else None,
    }
    result_path = args.output / f"{ts}_{args.passage}_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"\n  Result saved: {result_path.name}")

    # チャート生成 + 画面表示
    chart_path = args.output / f"{ts}_{args.passage}_chart.png"
    print("  Generating chart...")
    plot_delay_chart(
        case_id=f"{args.passage} (practice)",
        pattern="real_voice",
        ref=fa_ref,
        user=fa_user,
        ground_truth_indices=[],
        threshold=DELAY_THRESHOLD_SEC,
        output_path=chart_path,
        show=True,
    )

    print(f"\n  Done! Total latency: FA {fa_lat:.0f}ms + LLM {llm_lat:.0f}ms")


if __name__ == "__main__":
    main()
