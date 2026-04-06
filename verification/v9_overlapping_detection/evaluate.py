"""V9: オーバーラッピング遅れ検知 — 結果評価・集計."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from models import ExperimentResult

# 合格基準（definition.md より）
RECALL_THRESHOLD = 0.70       # 遅れ検知率 ≥ 70%
FPR_THRESHOLD = 0.20          # 誤検知率 < 20%
FA_LATENCY_THRESHOLD_MS = 3000  # FA 中央値 ≤ 3秒
TOTAL_LATENCY_THRESHOLD_MS = 8000  # 全体 中央値 ≤ 8秒


def evaluate_results(results: list[ExperimentResult]) -> dict:
    """実験結果を合格基準に照らして評価する."""
    summary: dict = {"pass_criteria": {}, "by_pattern": {}}

    # パターン別集計
    by_pattern: dict[str, list[ExperimentResult]] = {}
    for r in results:
        by_pattern.setdefault(r.pattern, []).append(r)

    # 1) 検知率（slow_phrase ケースで評価）
    slow_phrase = by_pattern.get("slow_phrase", [])
    if slow_phrase:
        recalls = [r.recall for r in slow_phrase]
        avg_recall = statistics.mean(recalls)
        summary["pass_criteria"]["recall"] = {
            "value": avg_recall,
            "threshold": RECALL_THRESHOLD,
            "pass": avg_recall >= RECALL_THRESHOLD,
        }

    # 2) 誤検知率（sync + fast ケースで評価）
    no_delay_cases = by_pattern.get("sync", []) + by_pattern.get("fast", [])
    if no_delay_cases:
        fps = [r.false_positives for r in no_delay_cases]
        totals = [r.false_positives + r.true_positives + r.false_negatives or 1 for r in no_delay_cases]
        # 遅れなしケースでの FP 数 / 全フレーズ数
        fp_counts = [r.false_positives for r in no_delay_cases]
        phrase_counts = [r.total_phrase_count for r in no_delay_cases]
        if sum(phrase_counts) > 0:
            fpr = sum(fp_counts) / sum(phrase_counts)
        else:
            fpr = 0.0
        summary["pass_criteria"]["false_positive_rate"] = {
            "value": fpr,
            "threshold": FPR_THRESHOLD,
            "pass": fpr < FPR_THRESHOLD,
        }

    # 3) FA レイテンシ
    fa_latencies = [r.fa_user_latency_ms for r in results]
    if fa_latencies:
        fa_median = statistics.median(fa_latencies)
        summary["pass_criteria"]["fa_latency_median_ms"] = {
            "value": fa_median,
            "threshold": FA_LATENCY_THRESHOLD_MS,
            "pass": fa_median <= FA_LATENCY_THRESHOLD_MS,
        }

    # 4) 全体レイテンシ
    total_latencies = [r.total_latency_ms for r in results]
    if total_latencies:
        total_median = statistics.median(total_latencies)
        summary["pass_criteria"]["total_latency_median_ms"] = {
            "value": total_median,
            "threshold": TOTAL_LATENCY_THRESHOLD_MS,
            "pass": total_median <= TOTAL_LATENCY_THRESHOLD_MS,
        }

    # パターン別サマリ
    for pattern, cases in by_pattern.items():
        summary["by_pattern"][pattern] = {
            "count": len(cases),
            "avg_delayed_phrases": statistics.mean([c.delayed_phrase_count for c in cases]),
            "avg_total_phrases": statistics.mean([c.total_phrase_count for c in cases]),
            "avg_fa_latency_ms": statistics.mean([c.fa_user_latency_ms for c in cases]),
            "avg_total_latency_ms": statistics.mean([c.total_latency_ms for c in cases]),
            "avg_user_loss": statistics.mean([c.user_loss for c in cases]),
        }
        if any(c.recall > 0 or c.true_positives > 0 for c in cases):
            summary["by_pattern"][pattern]["avg_recall"] = statistics.mean([c.recall for c in cases])
            summary["by_pattern"][pattern]["avg_precision"] = statistics.mean([c.precision for c in cases])

    return summary


def print_summary(summary: dict) -> None:
    """評価サマリをコンソール出力する."""
    print("\n" + "=" * 60)
    print("V9 検証結果サマリ")
    print("=" * 60)

    print("\n■ 合格基準判定:")
    all_pass = True
    for name, criterion in summary["pass_criteria"].items():
        status = "✓ PASS" if criterion["pass"] else "✗ FAIL"
        if not criterion["pass"]:
            all_pass = False
        print(f"  {name}: {criterion['value']:.4f} "
              f"(基準: {criterion['threshold']}) [{status}]")

    print(f"\n  総合判定: {'PASS' if all_pass else 'FAIL'}")

    print("\n■ パターン別:")
    for pattern, data in summary["by_pattern"].items():
        print(f"\n  [{pattern}] ({data['count']} cases)")
        print(f"    遅れフレーズ: {data['avg_delayed_phrases']:.1f} / {data['avg_total_phrases']:.1f}")
        print(f"    FA レイテンシ: {data['avg_fa_latency_ms']:.0f}ms")
        print(f"    全体レイテンシ: {data['avg_total_latency_ms']:.0f}ms")
        print(f"    ユーザー loss: {data['avg_user_loss']:.4f}")
        if "avg_recall" in data:
            print(f"    Recall: {data['avg_recall']:.4f}")
            print(f"    Precision: {data['avg_precision']:.4f}")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluate.py <result_json_path>")
        sys.exit(1)

    result_path = Path(sys.argv[1])
    with open(result_path, encoding="utf-8") as f:
        data = json.load(f)

    results = [ExperimentResult.model_validate(r) for r in data["results"]]
    summary = evaluate_results(results)
    print_summary(summary)
