"""V7: 自動評価スクリプト."""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from verification.v7_variation_quality.config import LEARNING_ITEMS

OUTPUT_DIR = Path(__file__).parent / "outputs"

GRAMMAR_DIMENSIONS = [
    "sentence_type",
    "polarity",
    "voice",
    "tense_aspect",
    "modality",
    "clause_type",
    "info_structure",
]


def load_latest_results(phase: str) -> dict | None:
    """指定Phaseの最新結果を読み込む."""
    files = sorted(OUTPUT_DIR.glob(f"phase_{phase}_*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def check_learning_item_presence(variations: list[dict], pattern: str) -> dict:
    """学習項目が英文に含まれているか正規表現でチェック."""
    total = len(variations)
    found = sum(1 for v in variations if re.search(pattern, v["variation"]["en"]))
    return {"total": total, "found": found, "rate": found / total if total else 0}


def compute_grammar_distribution(variations: list[dict]) -> dict:
    """7次元の文法構造の分布を算出."""
    dist = {dim: Counter() for dim in GRAMMAR_DIMENSIONS}
    for v in variations:
        g = v["variation"]["grammar"]
        for dim in GRAMMAR_DIMENSIONS:
            dist[dim][g[dim]] += 1
    return {dim: dict(counter) for dim, counter in dist.items()}


def compute_entropy(counter: dict[str, int]) -> float:
    """シャノンエントロピーを算出."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def compute_max_entropy(n_values: int) -> float:
    """一様分布のエントロピー（上限）."""
    if n_values <= 1:
        return 0.0
    return math.log2(n_values)


def compute_ttr(variations: list[dict]) -> float:
    """Type-Token Ratio (語彙多様性)."""
    all_words = []
    for v in variations:
        words = re.findall(r"[a-zA-Z']+", v["variation"]["en"].lower())
        all_words.extend(words)
    if not all_words:
        return 0.0
    return len(set(all_words)) / len(all_words)


def compute_word_stats(variations: list[dict]) -> dict:
    """文長統計."""
    lengths = []
    for v in variations:
        words = re.findall(r"[a-zA-Z']+", v["variation"]["en"])
        lengths.append(len(words))
    if not lengths:
        return {"min": 0, "max": 0, "mean": 0}
    return {
        "min": min(lengths),
        "max": max(lengths),
        "mean": sum(lengths) / len(lengths),
    }


def evaluate_phase(results: dict, phase_label: str) -> dict:
    """1つのPhaseの結果を評価する."""
    print(f"\n{'=' * 60}")
    print(f"Phase {phase_label}: {results.get('description', '')}")
    print(f"{'=' * 60}")

    phase_eval = {}

    # Phase Eは構造が異なる
    if results.get("phase") == "E":
        for level, variations in results["levels"].items():
            li = LEARNING_ITEMS[3]  # L4
            print(f"\n  CEFR {level}: {li['item']}")
            presence = check_learning_item_presence(variations, li["pattern"])
            print(f"    学習項目出現率: {presence['rate']:.0%} ({presence['found']}/{presence['total']})")
            word_stats = compute_word_stats(variations)
            print(f"    文長: min={word_stats['min']}, max={word_stats['max']}, mean={word_stats['mean']:.1f}")
            phase_eval[level] = {
                "presence": presence,
                "word_stats": word_stats,
            }
        return phase_eval

    for li in LEARNING_ITEMS:
        lid = li["id"]
        variations = results["items"].get(lid, [])
        if not variations:
            continue

        print(f"\n  --- {lid}: {li['item']} ({len(variations)}件) ---")

        # 1. 学習項目出現チェック
        presence = check_learning_item_presence(variations, li["pattern"])
        print(f"    学習項目出現率: {presence['rate']:.0%} ({presence['found']}/{presence['total']})")

        # 2. 文法構造の分布
        dist = compute_grammar_distribution(variations)
        print("    文法構造の分布:")
        dim_evals = {}
        for dim in GRAMMAR_DIMENSIONS:
            counter = dist[dim]
            entropy = compute_entropy(counter)
            unique = len(counter)
            max_ent = compute_max_entropy(unique)
            top = sorted(counter.items(), key=lambda x: -x[1])
            top_str = ", ".join(f"{k}:{v}" for k, v in top[:3])
            print(f"      {dim:20s}: {unique}種 (H={entropy:.2f}) [{top_str}]")
            dim_evals[dim] = {
                "distribution": counter,
                "unique_values": unique,
                "entropy": entropy,
                "max_entropy": max_ent,
            }

        # 3. 語彙多様性
        ttr = compute_ttr(variations)
        print(f"    語彙多様性 (TTR): {ttr:.2f}")

        # 4. 文長統計
        word_stats = compute_word_stats(variations)
        print(f"    文長: min={word_stats['min']}, max={word_stats['max']}, mean={word_stats['mean']:.1f}")

        phase_eval[lid] = {
            "presence": presence,
            "grammar_dimensions": dim_evals,
            "ttr": ttr,
            "word_stats": word_stats,
        }

    return phase_eval


def compare_phases(eval_a: dict, eval_b: dict, label_a: str, label_b: str) -> None:
    """2つのPhaseの評価結果を比較する."""
    print(f"\n{'=' * 60}")
    print(f"比較: Phase {label_a} vs Phase {label_b}")
    print(f"{'=' * 60}")

    for li in LEARNING_ITEMS:
        lid = li["id"]
        a = eval_a.get(lid)
        b = eval_b.get(lid)
        if not a or not b:
            continue

        print(f"\n  --- {lid}: {li['item']} ---")

        # 学習項目出現率の比較
        rate_a = a["presence"]["rate"]
        rate_b = b["presence"]["rate"]
        print(f"    出現率: {label_a}={rate_a:.0%} → {label_b}={rate_b:.0%}")

        # 文法構造の比較（次元別）
        print("    文法分散 (ユニーク値数):")
        for dim in GRAMMAR_DIMENSIONS:
            ua = a["grammar_dimensions"][dim]["unique_values"]
            ub = b["grammar_dimensions"][dim]["unique_values"]
            ha = a["grammar_dimensions"][dim]["entropy"]
            hb = b["grammar_dimensions"][dim]["entropy"]
            diff = "↑" if hb > ha else "↓" if hb < ha else "="
            print(f"      {dim:20s}: {ua}→{ub} (H: {ha:.2f}→{hb:.2f}) {diff}")

        # TTRの比較
        print(f"    TTR: {a['ttr']:.2f} → {b['ttr']:.2f}")


def summarize(all_evals: dict) -> None:
    """全体サマリーを出力."""
    print(f"\n{'=' * 60}")
    print("全体サマリー")
    print(f"{'=' * 60}")

    # 合格基準チェック
    print("\n  合格基準チェック:")

    for phase_label, phase_eval in all_evals.items():
        if phase_label == "E":
            continue
        print(f"\n    Phase {phase_label}:")
        for li in LEARNING_ITEMS:
            lid = li["id"]
            ev = phase_eval.get(lid)
            if not ev:
                continue

            presence_ok = ev["presence"]["rate"] >= 0.9
            grammar_ok = all(
                ev["grammar_dimensions"][dim]["unique_values"] >= 2
                for dim in GRAMMAR_DIMENSIONS
            )
            print(
                f"      {lid}: 出現率={ev['presence']['rate']:.0%} "
                f"{'PASS' if presence_ok else 'FAIL'} | "
                f"文法分散={'PASS' if grammar_ok else 'FAIL'}"
            )


def main() -> None:
    """メイン評価実行."""
    all_evals = {}

    for phase in ["A", "B", "C", "D", "E"]:
        results = load_latest_results(phase)
        if results:
            all_evals[phase] = evaluate_phase(results, phase)
        else:
            print(f"\nPhase {phase}: 結果なし（スキップ）")

    # Phase間比較
    if "A" in all_evals and "B" in all_evals:
        compare_phases(all_evals["A"], all_evals["B"], "A", "B")

    if "B" in all_evals and "C" in all_evals:
        compare_phases(all_evals["B"], all_evals["C"], "B", "C")

    if "B" in all_evals and "D" in all_evals:
        compare_phases(all_evals["B"], all_evals["D"], "B", "D")

    # 全体サマリー
    summarize(all_evals)

    # 評価結果をJSON保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    eval_path = OUTPUT_DIR / "evaluation_report.json"
    eval_path.write_text(
        json.dumps(all_evals, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n評価レポート保存先: {eval_path}")


if __name__ == "__main__":
    main()
