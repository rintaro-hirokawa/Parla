"""V5: リトライ判定の速度と精度 — 実行スクリプト."""

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from verification.v5_retry_judgment.config import V5Config
from verification.v5_retry_judgment.judge import JudgmentWithLatency, judge_audio
from verification.v5_retry_judgment.test_cases import SCENARIOS

AUDIO_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR = Path(__file__).parent / "outputs"


def check_audio_files() -> list[str]:
    """不足している音声ファイルを返す."""
    missing = []
    for scenario in SCENARIOS:
        for case in scenario.audio_cases:
            path = AUDIO_DIR / scenario.audio_filename(case.audio_type)
            if not path.exists():
                missing.append(str(path.name))
    return missing


def run_single(scenario, case, config: V5Config) -> list[JudgmentWithLatency]:
    """1テストケースを num_runs 回実行し、結果リストを返す."""
    audio_path = AUDIO_DIR / scenario.audio_filename(case.audio_type)
    results = []
    for i in range(config.num_runs):
        print(f"    実行 {i + 1}/{config.num_runs}...", end=" ", flush=True)
        jwl = judge_audio(
            audio_path=audio_path,
            learning_item=scenario.learning_item,
            ja_prompt=scenario.ja_prompt,
            reference_answer=scenario.reference_answer,
            config=config,
        )
        print(f"{jwl.latency_seconds:.2f}s")
        results.append(jwl)
    return results


def print_results(all_results: list[dict]) -> dict:
    """結果テーブルを表示し、集計メトリクスを返す."""
    print(f"\n{'=' * 90}")
    print(f"{'Scenario':<8} {'Type':<14} {'Expected':<10} {'Got':<10} {'item_used':<10} "
          f"{'Latency':<10} {'Reason'}")
    print(f"{'-' * 90}")

    correct_matches = 0
    alt_correct_matches = 0
    alt_correct_total = 0
    all_latencies = []

    for r in all_results:
        expected_str = "correct" if r["expected_correct"] else "incorrect"
        got_str = "correct" if r["median_correct"] else "incorrect"
        match = r["expected_correct"] == r["median_correct"]
        marker = "  " if match else "X "

        if match:
            correct_matches += 1

        if r["audio_type"] == "alt_correct":
            alt_correct_total += 1
            if r["median_correct"]:
                alt_correct_matches += 1

        all_latencies.append(r["median_latency"])

        print(f"{marker}{r['scenario_id']:<6} {r['audio_type']:<14} {expected_str:<10} "
              f"{got_str:<10} {str(r['median_item_used']):<10} "
              f"{r['median_latency']:.2f}s     {r['median_reason']}")

    total = len(all_results)
    accuracy = correct_matches / total * 100 if total else 0
    alt_accuracy = alt_correct_matches / alt_correct_total * 100 if alt_correct_total else 0
    latency_median = statistics.median(all_latencies) if all_latencies else 0
    latency_max = max(all_latencies) if all_latencies else 0

    print(f"\n{'=' * 90}")
    print("集計メトリクス:")
    print(f"  正答率:           {correct_matches}/{total} ({accuracy:.1f}%)  目標: ≥85%")
    print(f"  alt_correct正答率: {alt_correct_matches}/{alt_correct_total} "
          f"({alt_accuracy:.1f}%)  目標: ≥80%")
    print(f"  レイテンシ中央値:  {latency_median:.2f}s  目標: ≤3.0s")
    print(f"  レイテンシ最大値:  {latency_max:.2f}s  目標: ≤5.0s")

    pass_criteria = (
        accuracy >= 85.0
        and alt_accuracy >= 80.0
        and latency_median <= 3.0
        and latency_max <= 5.0
    )
    print(f"\n  総合判定: {'PASS' if pass_criteria else 'FAIL'}")

    return {
        "accuracy": accuracy,
        "alt_correct_accuracy": alt_accuracy,
        "latency_median": latency_median,
        "latency_max": latency_max,
        "pass": pass_criteria,
    }


def save_output(all_results: list[dict], metrics: dict, config: V5Config) -> Path:
    """結果をJSONファイルに保存."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"result_{timestamp}.json"

    output = {
        "config": {
            "model": config.model,
            "cefr_level": config.cefr_level,
            "num_runs": config.num_runs,
        },
        "metrics": metrics,
        "results": all_results,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    """メイン実行."""
    config = V5Config()

    if not config.model:
        print("エラー: config.py の model にモデル名を設定してください")
        sys.exit(1)

    print(f"モデル: {config.model}")
    print(f"CEFR: {config.cefr_level} / 実行回数: {config.num_runs}")

    missing = check_audio_files()
    if missing:
        print(f"\nエラー: 以下の音声ファイルが見つかりません:")
        for f in missing:
            print(f"  - audio/{f}")
        print("\n録音ツールを使って録音してください:")
        print("  uv run python -m verification.v5_retry_judgment.record")
        sys.exit(1)

    all_results = []
    for scenario in SCENARIOS:
        print(f"\n--- {scenario.id}: {scenario.learning_item} ---")
        for case in scenario.audio_cases:
            print(f"  [{case.audio_type}] ({case.audio_type_ja})")
            runs = run_single(scenario, case, config)

            latencies = [r.latency_seconds for r in runs]
            # 中央値の実行結果を代表として使用
            median_idx = latencies.index(sorted(latencies)[len(latencies) // 2])
            median_run = runs[median_idx]

            all_results.append({
                "scenario_id": scenario.id,
                "audio_type": case.audio_type,
                "audio_type_ja": case.audio_type_ja,
                "expected_correct": case.expected.correct,
                "expected_item_used": case.expected.item_used,
                "median_correct": median_run.result.correct,
                "median_item_used": median_run.result.item_used,
                "median_reason": median_run.result.reason,
                "median_latency": median_run.latency_seconds,
                "all_latencies": latencies,
                "all_results": [
                    {
                        "correct": r.result.correct,
                        "item_used": r.result.item_used,
                        "reason": r.result.reason,
                        "latency": r.latency_seconds,
                    }
                    for r in runs
                ],
            })

    metrics = print_results(all_results)
    output_path = save_output(all_results, metrics, config)
    print(f"\n結果保存先: {output_path}")


if __name__ == "__main__":
    main()
