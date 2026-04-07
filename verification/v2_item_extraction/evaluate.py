"""V2: 自動メトリクス集計 + 目視確認用レポート.

使い方:
    uv run python -m verification.v2_item_extraction.evaluate
    uv run python -m verification.v2_item_extraction.evaluate --file outputs/result_XXXX.json
"""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from verification.v2_item_extraction.models import SUBTAGS_BY_CATEGORY

OUTPUT_DIR = Path(__file__).parent / "outputs"


def load_latest_result(filepath: str | None = None) -> dict:
    """最新の結果ファイルを読み込む."""
    if filepath:
        path = Path(filepath)
        if not path.is_absolute():
            path = OUTPUT_DIR / filepath
    else:
        result_files = sorted(OUTPUT_DIR.glob("result_*.json"), reverse=True)
        if not result_files:
            raise FileNotFoundError(f"結果ファイルが見つかりません: {OUTPUT_DIR}")
        path = result_files[0]

    print(f"読み込み: {path.name}\n")
    return json.loads(path.read_text(encoding="utf-8"))


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def evaluate(data: dict) -> None:
    """メトリクス集計 + 目視確認用レポート."""
    results = [r for r in data["results"] if "error" not in r]
    errors = [r for r in data["results"] if "error" in r]

    if errors:
        print(f"\n⚠ エラー: {len(errors)}件")
        for e in errors:
            print(f"  {e['scenario_id']}_{e['audio_type']}: {e['error']}")

    # --- Stage 1: 書き起こし結果一覧 ---
    print_section("Stage 1: 書き起こし結果")
    for r in results:
        print(f"\n  [{r['scenario_id']}_{r['audio_type']}]")
        print(f"  日本語:     {r['ja_prompt']}")
        print(f"  模範解答:   {r['model_en']}")
        print(f"  書き起こし: {r['stage1']['user_utterance']}")
        print(f"  レイテンシ: {r['stage1']['latency_s']}s")

    # --- Stage 2: フィードバック詳細 ---
    print_section("Stage 2: フィードバック詳細")
    all_items = []
    for r in results:
        s2 = r["stage2"]
        print(f"\n  [{r['scenario_id']}_{r['audio_type']}]")
        print(f"  書き起こし:   {r['stage1']['user_utterance']}")
        print(f"  模範解答:     {s2['model_answer']}")
        print(f"  許容:         {'Yes' if s2['is_acceptable'] else 'No'}")
        print(f"  レイテンシ:   {s2['latency_s']}s")
        if s2["learning_items"]:
            for item in s2["learning_items"]:
                all_items.append(item)
                reapp = ""
                if item["is_reappearance"]:
                    reapp = f" [再出: {item['matched_stock_item_id']}]"
                print(f"    - [{item['category']}/{item['sub_tag'] or '-'}] "
                      f"{item['pattern']} "
                      f"(優先度={item['priority']})"
                      f"{reapp}")
                print(f"      {item['explanation']}")
        else:
            print(f"    (学習項目なし)")

    # --- 統計 ---
    print_section("統計サマリー")

    # 項目数
    item_counts = [len(r["stage2"]["learning_items"]) for r in results]
    print(f"\n  項目数:")
    print(f"    合計: {sum(item_counts)}")
    print(f"    平均: {statistics.mean(item_counts):.1f}")
    print(f"    最小/最大: {min(item_counts)}/{max(item_counts)}")

    # カテゴリ分布
    if all_items:
        cat_counter = Counter(item["category"] for item in all_items)
        print(f"\n  カテゴリ分布:")
        for cat, count in cat_counter.most_common():
            pct = count / len(all_items) * 100
            print(f"    {cat}: {count} ({pct:.0f}%)")

        # サブタグ妥当性
        valid_subtags = 0
        invalid_subtags = []
        for item in all_items:
            cat = item["category"]
            sub = item["sub_tag"]
            valid_list = SUBTAGS_BY_CATEGORY.get(cat, [])
            if not valid_list or sub in valid_list or sub == "":
                valid_subtags += 1
            else:
                invalid_subtags.append(f"{cat}/{sub} ({item['pattern']})")

        print(f"\n  サブタグ妥当性: {valid_subtags}/{len(all_items)}")
        if invalid_subtags:
            print(f"    無効なサブタグ:")
            for inv in invalid_subtags:
                print(f"      - {inv}")

        # 習得優先度分布
        priorities = [item["priority"] for item in all_items]
        priority_counter = Counter(priorities)
        print(f"\n  習得優先度:")
        for level in [5, 4, 3, 2]:
            count = priority_counter.get(level, 0)
            label = {5: "最優先", 4: "早めに", 3: "望ましい", 2: "余裕あれば"}[level]
            print(f"    {level} ({label}): {count}")

        # 再出検知
        reappearances = [item for item in all_items if item["is_reappearance"]]
        print(f"\n  再出検知: {len(reappearances)}件")
        for item in reappearances:
            print(f"    - {item['pattern']} → {item['matched_stock_item_id']}")

    # レイテンシ
    s1_latencies = [r["stage1"]["latency_s"] for r in results]
    s2_latencies = [r["stage2"]["latency_s"] for r in results]
    print(f"\n  レイテンシ:")
    print(f"    Stage 1: 平均={statistics.mean(s1_latencies):.1f}s, "
          f"中央値={statistics.median(s1_latencies):.1f}s, "
          f"最大={max(s1_latencies):.1f}s")
    print(f"    Stage 2: 平均={statistics.mean(s2_latencies):.1f}s, "
          f"中央値={statistics.median(s2_latencies):.1f}s, "
          f"最大={max(s2_latencies):.1f}s")
    total_latencies = [s1 + s2 for s1, s2 in zip(s1_latencies, s2_latencies)]
    print(f"    合計:    平均={statistics.mean(total_latencies):.1f}s, "
          f"中央値={statistics.median(total_latencies):.1f}s, "
          f"最大={max(total_latencies):.1f}s")

    # audio_type別の比較
    print_section("音声タイプ別比較")
    for audio_type in ["jp_mixed", "different_structure"]:
        type_results = [r for r in results if r["audio_type"] == audio_type]
        type_items = []
        for r in type_results:
            type_items.extend(r["stage2"]["learning_items"])

        print(f"\n  {audio_type}:")
        print(f"    ケース数: {len(type_results)}")
        print(f"    学習項目数: {len(type_items)}")
        if type_items:
            type_cats = Counter(item["category"] for item in type_items)
            print(f"    カテゴリ: {dict(type_cats.most_common())}")
            type_pri = Counter(item["priority"] for item in type_items)
            print(f"    優先度分布: {dict(sorted(type_pri.items(), reverse=True))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 評価レポート")
    parser.add_argument("--file", help="評価対象の結果ファイル（省略時は最新）")
    args = parser.parse_args()

    data = load_latest_result(args.file)
    evaluate(data)


if __name__ == "__main__":
    main()
