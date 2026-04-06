"""V7: 類題生成品質 — 実行スクリプト."""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from verification.v7_variation_quality.config import (
    FOCUS_ITEM_IDS,
    LEARNING_ITEMS,
    PHASE_D_CONSTRAINTS,
    SOURCE_FILES,
    V7Config,
)
from verification.v7_variation_quality.generate import generate_variation

SOURCE_DIR = Path(__file__).parent / "source_texts"
OUTPUT_DIR = Path(__file__).parent / "outputs"

REPS = 3  # Phase B/C の繰り返し数


def get_focus_items() -> list[dict]:
    """Phase B〜D で使用する学習項目を返す."""
    return [li for li in LEARNING_ITEMS if li["id"] in FOCUS_ITEM_IDS]


def load_source(filename: str) -> str:
    """ソーステキストを読み込む."""
    path = SOURCE_DIR / filename
    if not path.exists():
        print(f"エラー: {path} が見つかりません")
        sys.exit(1)
    return path.read_text(encoding="utf-8").strip()


def save_results(results: dict, phase: str) -> Path:
    """結果をJSONファイルに保存する."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"phase_{phase}_{timestamp}.json"
    output_path = OUTPUT_DIR / filename
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def print_variation(v: dict, index: int) -> None:
    """類題1件をコンソール出力する."""
    item = v["variation"]
    g = item["grammar"]
    print(f"  [{index}] JA: {item['ja']}")
    print(f"      EN: {item['en']}")
    print(
        f"      文法: {g['sentence_type']}/{g['polarity']}/{g['voice']}/"
        f"{g['tense_aspect']}/{g['modality']}/{g['clause_type']}/"
        f"{g['info_structure']}"
    )


# ── Phase 実行関数 ──────────────────────────────────


def run_phase_a(config: V7Config) -> dict:
    """Phase A: 異なるソース × 3回（ベースライン、全4項目）."""
    print("\n" + "=" * 60)
    print("Phase A: 異なるソース × 3回（ベースライン）")
    print("=" * 60)

    results = {"phase": "A", "description": "異なるソース、制約なし", "items": {}}

    for li in LEARNING_ITEMS:
        lid = li["id"]
        print(f"\n--- {lid}: {li['item']} ---")
        results["items"][lid] = []

        for i, src_file in enumerate(SOURCE_FILES[:3]):
            print(f"  ソース: {src_file}")
            source_text = load_source(src_file)
            result = generate_variation(li["item"], source_text, config)
            result_dict = result.model_dump()
            results["items"][lid].append(result_dict)
            print_variation(result_dict, i + 1)

    return results


def run_phase_b(config: V7Config) -> dict:
    """Phase B: 同一ソース × 3回（ストレステスト、2項目）."""
    print("\n" + "=" * 60)
    print("Phase B: 同一ソース × 3回（ストレステスト）")
    print("=" * 60)

    results = {"phase": "B", "description": "同一ソース(S1)、制約なし", "items": {}}
    source_text = load_source(SOURCE_FILES[0])

    for li in get_focus_items():
        lid = li["id"]
        print(f"\n--- {lid}: {li['item']} ---")
        results["items"][lid] = []

        for i in range(REPS):
            print(f"  生成 {i + 1}/{REPS}")
            result = generate_variation(li["item"], source_text, config)
            result_dict = result.model_dump()
            results["items"][lid].append(result_dict)
            print_variation(result_dict, i + 1)

    return results


def run_phase_c(config: V7Config, phase_b_results: dict) -> dict:
    """Phase C: 同一ソース × 3回 + 履歴あり（2項目）."""
    print("\n" + "=" * 60)
    print("Phase C: 同一ソース × 3回 + 履歴あり")
    print("=" * 60)

    results = {"phase": "C", "description": "同一ソース(S1)、履歴+文法分散指示", "items": {}}
    source_text = load_source(SOURCE_FILES[0])

    for li in get_focus_items():
        lid = li["id"]
        print(f"\n--- {lid}: {li['item']} ---")
        history = list(phase_b_results["items"].get(lid, []))
        results["items"][lid] = []

        for i in range(REPS):
            print(f"  生成 {i + 1}/{REPS} (履歴数: {len(history)})")
            result = generate_variation(
                li["item"], source_text, config, history=history
            )
            result_dict = result.model_dump()
            results["items"][lid].append(result_dict)
            print_variation(result_dict, i + 1)
            history.append(result_dict)

    return results


def run_phase_d(config: V7Config) -> dict:
    """Phase D: 構文次元の明示制約（2項目 × 3制約）."""
    print("\n" + "=" * 60)
    print("Phase D: 構文次元の明示制約")
    print("=" * 60)

    results = {"phase": "D", "description": "同一ソース(S1)、次元制約明示", "items": {}}
    source_text = load_source(SOURCE_FILES[0])

    for li in get_focus_items():
        lid = li["id"]
        print(f"\n--- {lid}: {li['item']} ---")
        results["items"][lid] = []
        constraint_sets = PHASE_D_CONSTRAINTS[lid]

        for i, constraints in enumerate(constraint_sets):
            constraint_str = ", ".join(f"{k}={v}" for k, v in constraints.items())
            print(f"  制約: {constraint_str}")
            result = generate_variation(
                li["item"], source_text, config, constraints=constraints
            )
            result_dict = result.model_dump()
            results["items"][lid].append(result_dict)
            print_variation(result_dict, i + 1)

    return results


def run_phase_e(config: V7Config) -> dict:
    """Phase E: CEFRレベル比較（L4 × 2レベル × 2回）."""
    print("\n" + "=" * 60)
    print("Phase E: CEFRレベル比較 (B1 vs B2)")
    print("=" * 60)

    results = {"phase": "E", "description": "CEFRレベル比較", "levels": {}}
    source_text = load_source(SOURCE_FILES[5])  # S6
    li = LEARNING_ITEMS[3]  # L4: take into account

    for level in ["B1", "B2"]:
        print(f"\n--- CEFR {level}: {li['item']} ---")
        level_config = V7Config(
            model=config.model,
            cefr_level=level,
            english_variant=config.english_variant,
            max_retries=config.max_retries,
        )
        results["levels"][level] = []

        for i in range(2):
            print(f"  生成 {i + 1}/2")
            result = generate_variation(li["item"], source_text, level_config)
            result_dict = result.model_dump()
            results["levels"][level].append(result_dict)
            print_variation(result_dict, i + 1)

    return results


# ── メイン ──────────────────────────────────


def main() -> None:
    """メイン実行."""
    parser = argparse.ArgumentParser(description="V7: 類題生成の品質と多様性")
    parser.add_argument(
        "--phase",
        choices=["A", "B", "C", "D", "E", "all"],
        default="all",
        help="実行するフェーズ (default: all)",
    )
    args = parser.parse_args()

    config = V7Config()
    if not config.model:
        print("エラー: config.py の model にモデル名を設定してください")
        sys.exit(1)

    print(f"モデル: {config.model}")
    print(f"CEFR: {config.cefr_level} / {config.english_variant}")

    all_results = {}
    start_time = time.time()

    if args.phase in ("A", "all"):
        all_results["A"] = run_phase_a(config)
        save_results(all_results["A"], "A")

    if args.phase in ("B", "all"):
        all_results["B"] = run_phase_b(config)
        save_results(all_results["B"], "B")

    if args.phase in ("C", "all"):
        if "B" not in all_results:
            b_files = sorted(OUTPUT_DIR.glob("phase_B_*.json"), reverse=True)
            if not b_files:
                print("エラー: Phase Bの結果が見つかりません。先にPhase Bを実行してください。")
                sys.exit(1)
            all_results["B"] = json.loads(b_files[0].read_text(encoding="utf-8"))
        all_results["C"] = run_phase_c(config, all_results["B"])
        save_results(all_results["C"], "C")

    if args.phase in ("D", "all"):
        all_results["D"] = run_phase_d(config)
        save_results(all_results["D"], "D")

    if args.phase in ("E", "all"):
        all_results["E"] = run_phase_e(config)
        save_results(all_results["E"], "E")

    elapsed = time.time() - start_time
    print(f"\n完了: {elapsed:.1f}秒")

    if args.phase == "all":
        save_results(all_results, "all")


if __name__ == "__main__":
    main()
