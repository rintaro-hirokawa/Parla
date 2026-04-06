"""V9: オーバーラッピング遅れ検知 — メイン実行スクリプト."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from config import (
    OUTPUTS_DIR,
    REFERENCE_AUDIO_DIR,
    SIMULATED_AUDIO_DIR,
)
from delay_detection import compute_accuracy, detect_delays
from evaluate import evaluate_results, print_summary
from forced_alignment import run_forced_alignment
from llm_feedback import generate_feedback
from models import ExperimentResult, FAResult, TestCase
from test_cases import build_test_cases
from tts_generate import (
    _get_passage_id,
    generate_all_audio,
    generate_reference_audio_with_timestamps,
)


def _load_reference_timestamps(cases: list[TestCase]) -> dict[str, FAResult]:
    """キャッシュ済みの模範タイムスタンプを読み込む."""
    timestamps: dict[str, FAResult] = {}
    seen: set[str] = set()
    for case in cases:
        pid = _get_passage_id(case)
        if pid in seen:
            continue
        seen.add(pid)
        ts_path = REFERENCE_AUDIO_DIR / f"{pid}_timestamps.json"
        if ts_path.exists():
            with open(ts_path, encoding="utf-8") as f:
                timestamps[pid] = FAResult.model_validate(json.load(f))
        else:
            # キャッシュがなければ TTS で生成
            _, fa = generate_reference_audio_with_timestamps(case.passage_text, pid)
            timestamps[pid] = fa
    return timestamps


def step_tts(cases: list[TestCase]) -> dict[str, FAResult]:
    """Step: TTS音声を生成し、模範タイムスタンプを返す."""
    print("\n=== Step: TTS 音声生成 ===")
    ref_ts = generate_all_audio(cases)
    print("TTS 音声生成完了")
    return ref_ts


def step_pipeline(
    cases: list[TestCase],
    ref_timestamps: dict[str, FAResult],
    runs: int,
) -> tuple[list[ExperimentResult], dict[str, dict]]:
    """Step: FA → 遅れ検知 → LLM の全パイプラインを実行する.

    Returns:
        (results, fa_data) — fa_data は可視化用の FA 生データ
    """
    print(f"\n=== Step: パイプライン実行 (runs={runs}) ===")
    all_results: list[ExperimentResult] = []
    fa_data: dict[str, dict] = {}

    for run_idx in range(runs):
        if runs > 1:
            print(f"\n--- Run {run_idx + 1}/{runs} ---")

        for case in cases:
            print(f"\n[{case.case_id}] pattern={case.pattern}")
            passage_id = _get_passage_id(case)
            user_audio = SIMULATED_AUDIO_DIR / f"{case.case_id}.mp3"

            fa_ref = ref_timestamps.get(passage_id)
            if fa_ref is None:
                print(f"  ERROR: 模範タイムスタンプが見つかりません: {passage_id}")
                continue
            if not user_audio.exists():
                print(f"  ERROR: 模擬音声が見つかりません: {user_audio}")
                continue

            print(f"  模範タイムスタンプ: {len(fa_ref.words)} words (source={fa_ref.source})")

            # ユーザー音声の Forced Alignment（リアルタイム処理に相当）
            print("  FA (模擬ユーザー)...")
            fa_user, fa_user_lat = run_forced_alignment(user_audio, case.passage_text)
            print(f"    {len(fa_user.words)} words, loss={fa_user.loss:.4f}, {fa_user_lat:.0f}ms")

            # FA 生データを保存（可視化用、最初の run のみ）
            if run_idx == 0:
                fa_data[case.case_id] = {
                    "reference": fa_ref.model_dump(),
                    "user": fa_user.model_dump(),
                    "ground_truth_indices": case.delayed_word_indices,
                }

            # 遅れ検知
            print("  遅れ検知...")
            detection = detect_delays(fa_ref, fa_user)
            print(f"    遅れフレーズ: {detection.delayed_phrase_count}/{detection.total_phrase_count}")

            # 精度計算
            tp, fp, fn, precision, recall = compute_accuracy(
                detection, case.delayed_word_indices
            )

            # LLM フィードバック
            print("  LLM フィードバック生成...")
            feedback, llm_lat = generate_feedback(
                case.passage_text, detection.phrase_delays
            )
            if feedback.delayed_phrases:
                for pf in feedback.delayed_phrases:
                    print(f"    [{pf.estimated_cause}] {pf.phrase} ({pf.delay_sec}s)")
            print(f"    LLM: {llm_lat:.0f}ms")

            # 合計レイテンシ: FA(ユーザー) + LLM のみ
            total_lat = fa_user_lat + llm_lat

            result = ExperimentResult(
                case_id=case.case_id,
                pattern=case.pattern,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=precision,
                recall=recall,
                fa_user_latency_ms=fa_user_lat,
                llm_latency_ms=llm_lat,
                total_latency_ms=total_lat,
                user_loss=fa_user.loss,
                delayed_phrase_count=detection.delayed_phrase_count,
                total_phrase_count=detection.total_phrase_count,
                feedback=feedback,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            all_results.append(result)
            print(f"  合計: {total_lat:.0f}ms | TP={tp} FP={fp} FN={fn}")

    return all_results, fa_data


def save_results(
    results: list[ExperimentResult],
    fa_data: dict[str, dict] | None = None,
) -> Path:
    """結果をJSONファイルに保存する."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUTS_DIR / f"result_{ts}.json"

    data: dict = {
        "results": [r.model_dump() for r in results],
    }
    if fa_data:
        data["fa_data"] = fa_data

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n結果を保存: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="V9: オーバーラッピング遅れ検知 技術検証")
    parser.add_argument(
        "--step",
        choices=["all", "tts", "pipeline"],
        default="all",
        help="実行ステップ (default: all)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="パイプラインの実行回数 (default: 1)",
    )
    args = parser.parse_args()

    cases = build_test_cases()
    print(f"テストケース: {len(cases)} 件")

    if args.step == "tts":
        step_tts(cases)
        return

    if args.step == "pipeline":
        ref_ts = _load_reference_timestamps(cases)
        results, fa_data = step_pipeline(cases, ref_ts, runs=args.runs)
        save_results(results, fa_data)
        summary = evaluate_results(results)
        print_summary(summary)
        return

    # all
    ref_ts = step_tts(cases)
    results, fa_data = step_pipeline(cases, ref_ts, runs=args.runs)
    save_results(results, fa_data)
    summary = evaluate_results(results)
    print_summary(summary)


if __name__ == "__main__":
    main()
