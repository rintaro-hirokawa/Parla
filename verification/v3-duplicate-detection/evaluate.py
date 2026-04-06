"""V3: 意味的重複検出 — 評価スクリプト."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_results(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate(results: list[dict]) -> None:
    # エラー結果を除外
    valid = [r for r in results if r["actual_judgment"] != "error"]
    errors = [r for r in results if r["actual_judgment"] == "error"]

    if errors:
        print(f"\n⚠ エラー: {len(errors)} 件")
        for e in errors:
            print(f"  - {e['case_id']} (stock={e['stock_size']}, run={e['run_number']}): {e['reasoning'][:80]}")

    # ケースタイプ別 × ストックサイズ別の集計
    stats: dict[str, dict[int, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"correct": 0, "total": 0})
    )

    for r in valid:
        case_type = r["case_type"]
        stock_size = r["stock_size"]
        stats[case_type][stock_size]["total"] += 1
        if r["is_correct"]:
            stats[case_type][stock_size]["correct"] += 1

    # 合格基準
    thresholds = {
        "duplicate": 0.80,
        "non_duplicate": 0.90,
        "reappearance": 0.85,
    }
    threshold_labels = {
        "duplicate": "重複ペア正答率",
        "non_duplicate": "非重複ペア正答率",
        "reappearance": "再出検知率",
    }

    print(f"\n{'='*70}")
    print("V3: 意味的重複検出 — 評価結果")
    print(f"{'='*70}")

    all_passed = True

    for case_type in ["duplicate", "non_duplicate", "reappearance"]:
        if case_type not in stats:
            continue

        label = threshold_labels[case_type]
        threshold = thresholds[case_type]
        print(f"\n--- {label} (基準: {threshold*100:.0f}%+) ---")

        for stock_size in sorted(stats[case_type].keys()):
            s = stats[case_type][stock_size]
            rate = s["correct"] / s["total"] if s["total"] > 0 else 0
            passed = rate >= threshold
            mark = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
            print(f"  stock={stock_size:>3}: {s['correct']}/{s['total']} ({rate*100:.1f}%) [{mark}]")

    # 全体サマリ
    total_correct = sum(r["is_correct"] for r in valid)
    total = len(valid)
    print(f"\n--- 全体 ---")
    print(f"  正答: {total_correct}/{total} ({total_correct/total*100:.1f}%)")

    # レイテンシ
    latencies = [r["latency_ms"] for r in valid if r["latency_ms"] > 0]
    if latencies:
        latencies.sort()
        print(f"\n--- レイテンシ ---")
        print(f"  平均: {sum(latencies)/len(latencies):.0f}ms")
        print(f"  p50:  {latencies[len(latencies)//2]:.0f}ms")
        print(f"  p95:  {latencies[int(len(latencies)*0.95)]:.0f}ms")

    # 失敗ケースの詳細
    failures = [r for r in valid if not r["is_correct"]]
    if failures:
        print(f"\n--- 失敗ケース詳細 ---")
        for f in failures:
            print(
                f"  {f['case_id']} (stock={f['stock_size']}, run={f['run_number']}): "
                f"expected={f['expected_judgment']}, actual={f['actual_judgment']}"
            )
            if f.get("reasoning"):
                print(f"    reasoning: {f['reasoning'][:100]}")

    # 最終判定
    print(f"\n{'='*70}")
    if all_passed:
        print("最終判定: PASSED — 全ての合格基準を満たしています")
    else:
        print("最終判定: FAILED — 一部の合格基準を満たしていません")
    print(f"{'='*70}")

    sys.exit(0 if all_passed else 1)


def main():
    parser = argparse.ArgumentParser(description="V3: 評価スクリプト")
    parser.add_argument("result_file", type=Path, help="結果JSONファイルのパス")
    args = parser.parse_args()

    if not args.result_file.exists():
        print(f"ファイルが見つかりません: {args.result_file}")
        sys.exit(1)

    results = load_results(args.result_file)
    evaluate(results)


if __name__ == "__main__":
    main()
