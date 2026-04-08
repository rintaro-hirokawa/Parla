"""V11: 本番発話の内容評価 — 実行スクリプト（Azure ストリーミング版）."""

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from verification.v11_full_passage_evaluation.config import V11Config
from verification.v11_full_passage_evaluation.evaluate_passage import (
    PipelineResult,
    run_pipeline,
)
from verification.v11_full_passage_evaluation.test_cases import AUDIO_CASES, PASSAGE

AUDIO_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR = Path(__file__).parent / "outputs"


def check_audio_files() -> list[str]:
    """不足している音声ファイルを返す."""
    missing = []
    for case in AUDIO_CASES:
        path = AUDIO_DIR / PASSAGE.audio_filename(case.audio_type)
        if not path.exists():
            missing.append(PASSAGE.audio_filename(case.audio_type))
    return missing


def run_single(case, config: V11Config) -> list[PipelineResult]:
    """1テストケースを num_runs 回実行し、結果リストを返す."""
    audio_path = AUDIO_DIR / PASSAGE.audio_filename(case.audio_type)
    results = []
    for i in range(config.num_runs):
        print(f"    実行 {i + 1}/{config.num_runs}...")
        result = run_pipeline(audio_path, PASSAGE, config)
        print(f"    total latency: {result.total_latency_seconds:.2f}s "
              f"(stream={result.stream_latency_seconds:.2f}s + post={result.postprocess_latency_seconds:.4f}s)")
        results.append(result)
    return results


def _serialize_result(result: PipelineResult) -> dict:
    """PipelineResult をシリアライズ可能な dict に変換."""
    return {
        "stream_latency": result.stream_latency_seconds,
        "postprocess_latency": result.postprocess_latency_seconds,
        "total_latency": result.total_latency_seconds,
        "evaluation": result.evaluation.model_dump(),
    }


def print_results(all_results: list[dict]) -> dict:
    """結果テーブルを表示し、集計メトリクスを返す."""
    print(f"\n{'=' * 90}")
    print(f"{'Type':<20} {'Expected':<10} {'Got':<10} "
          f"{'Latency':<12} {'Completeness':<14} {'Details'}")
    print(f"{'-' * 90}")

    correct_matches = 0
    all_latencies = []

    for r in all_results:
        expected = "PASS" if r["expected_pass"] else "FAIL"
        got = "PASS" if r["median_passed"] else "FAIL"
        match = r["expected_pass"] == r["median_passed"]
        marker = "  " if match else "X "

        if match:
            correct_matches += 1

        lat = r["median_stream_latency"]
        all_latencies.append(lat)
        comp = r["median_completeness"]

        statuses = r["median_statuses"]
        status_summary = " ".join(
            f"[{s['index']}]{s['status'][0].upper()}" for s in statuses
        )

        print(f"{marker}{r['audio_type']:<18} {expected:<10} {got:<10} "
              f"{lat:>6.2f}s      {comp:>5.1f}%        {status_summary}")

    total_count = len(all_results)
    accuracy = correct_matches / total_count * 100 if total_count else 0
    latency_median = statistics.median(all_latencies) if all_latencies else 0
    latency_max = max(all_latencies) if all_latencies else 0

    print(f"\n{'=' * 90}")
    print("集計メトリクス:")
    print(f"  正答率:                {correct_matches}/{total_count} ({accuracy:.1f}%)  目標: >=85%")
    print(f"  ストリームレイテンシ中央値: {latency_median:.2f}s  目標: <=2.0s")
    print(f"  ストリームレイテンシ最大値: {latency_max:.2f}s")

    pass_criteria = accuracy >= 85.0 and latency_median <= 2.0
    print(f"\n  総合判定: {'PASS' if pass_criteria else 'FAIL'}")

    return {
        "accuracy": accuracy,
        "stream_latency_median": latency_median,
        "stream_latency_max": latency_max,
        "pass": pass_criteria,
    }


def save_output(all_results: list[dict], metrics: dict, config: V11Config) -> Path:
    """結果をJSONファイルに保存."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"result_{timestamp}.json"

    output = {
        "config": {
            "language": config.language,
            "cefr_level": config.cefr_level,
            "num_runs": config.num_runs,
            "correct_threshold": config.correct_threshold,
            "error_threshold": config.error_threshold,
        },
        "passage": {
            "id": PASSAGE.id,
            "topic": PASSAGE.topic,
            "num_sentences": len(PASSAGE.sentences),
        },
        "metrics": metrics,
        "results": all_results,
    }
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def main() -> None:
    """メイン実行."""
    config = V11Config()

    print("=== V11: Azure ストリーミング Pronunciation Assessment ===")
    print(f"Language: {config.language} / CEFR: {config.cefr_level} / 実行回数: {config.num_runs}")
    print(f"パッセージ: {PASSAGE.topic} ({len(PASSAGE.sentences)}文)")

    missing = check_audio_files()
    if missing:
        print(f"\nエラー: 以下の音声ファイルが見つかりません:")
        for f in missing:
            print(f"  - audio/{f}")
        print("\n録音ツールを使って録音してください:")
        print("  uv run python -m verification.v11_full_passage_evaluation.record")
        sys.exit(1)

    all_results = []
    for case in AUDIO_CASES:
        print(f"\n--- {case.audio_type} ({case.audio_type_ja}) ---")
        runs = run_single(case, config)

        # 中央値の実行結果を代表として使用（total_latency 基準）
        latencies = [r.total_latency_seconds for r in runs]
        median_idx = latencies.index(sorted(latencies)[len(latencies) // 2])
        median_run = runs[median_idx]

        all_results.append({
            "audio_type": case.audio_type,
            "audio_type_ja": case.audio_type_ja,
            "expected_pass": case.expected_pass,
            "median_passed": median_run.evaluation.passed,
            "median_stream_latency": median_run.stream_latency_seconds,
            "median_postprocess_latency": median_run.postprocess_latency_seconds,
            "median_total_latency": median_run.total_latency_seconds,
            "median_completeness": median_run.evaluation.azure.completeness_score,
            "median_statuses": [
                {"index": s.index, "status": s.status}
                for s in median_run.evaluation.sentences
            ],
            "all_runs": [_serialize_result(r) for r in runs],
        })

    metrics = print_results(all_results)
    output_path = save_output(all_results, metrics, config)
    print(f"\n結果保存先: {output_path}")


if __name__ == "__main__":
    main()
