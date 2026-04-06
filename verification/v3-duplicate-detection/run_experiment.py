"""V3: 意味的重複検出 — 実験スクリプト."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config import DEFAULT_MODEL, RESULTS_DIR, TEST_DATA_DIR, get_api_key
from llm_client import call_llm
from models import (
    ExperimentResult,
    FeedbackOutput,
    FocusedOutput,
)
from prompts import (
    STRATEGY_A_SYSTEM,
    STRATEGY_A_USER,
    STRATEGY_B_SYSTEM,
    STRATEGY_B_USER,
    format_stock_items,
)


def load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_stock_items(size: int) -> list[dict]:
    return load_json(TEST_DATA_DIR / f"stock_items_{size}.json")


def load_test_cases() -> list[dict]:
    cases = []
    for fname in ["duplicate_pairs.json", "non_duplicate_pairs.json", "reappearance_cases.json"]:
        cases.extend(load_json(TEST_DATA_DIR / fname))
    return cases


def load_scenarios() -> dict[str, dict]:
    scenarios = load_json(TEST_DATA_DIR / "scenarios.json")
    mapping = {}
    for sc in scenarios:
        for cid in sc["case_ids"]:
            mapping[cid] = sc
    return mapping


def run_strategy_a(
    case: dict,
    scenario: dict,
    stock_items: list[dict],
    model: str,
) -> tuple[FeedbackOutput, float]:
    stock_text = format_stock_items(stock_items)
    system_prompt = STRATEGY_A_SYSTEM.format(
        cefr_level=scenario["cefr_level"],
        english_variant=scenario["english_variant"],
    )
    user_prompt = STRATEGY_A_USER.format(
        japanese_prompt=scenario["japanese_prompt"],
        model_answer=scenario["model_answer"],
        user_utterance_text=scenario["user_utterance_text"],
        passage_context=scenario["passage_context"],
        stock_items_text=stock_text,
    )

    start = time.perf_counter()
    output = call_llm(model, system_prompt, user_prompt, FeedbackOutput)
    latency_ms = (time.perf_counter() - start) * 1000
    return output, latency_ms


def run_strategy_b(
    case: dict,
    stock_items: list[dict],
    model: str,
) -> tuple[FocusedOutput, float]:
    stock_text = format_stock_items(stock_items)
    target_pattern = case["target_pattern"]
    new_patterns_text = f"1. {target_pattern}"

    start = time.perf_counter()
    output = call_llm(model, STRATEGY_B_SYSTEM, STRATEGY_B_USER.format(
        new_patterns_text=new_patterns_text,
        stock_items_text=stock_text,
    ), FocusedOutput)
    latency_ms = (time.perf_counter() - start) * 1000
    return output, latency_ms


def evaluate_result_a(
    case: dict,
    output: FeedbackOutput,
) -> tuple[str, str | None, float | None, str]:
    """Extract judgment for the target case from strategy A output."""
    target = case["target_pattern"].lower()
    case_type = case["case_type"]

    best_match = None
    for item in output.learning_items:
        if target in item.pattern.lower() or item.pattern.lower() in target:
            best_match = item
            break

    if best_match is None:
        target_words = set(target.split())
        best_overlap = 0
        for item in output.learning_items:
            item_words = set(item.pattern.lower().split())
            overlap = len(target_words & item_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = item

    if best_match is None:
        if case_type == "non_duplicate":
            return "new", None, None, "LLM did not extract this pattern (treated as new)"
        return "not_extracted", None, None, "LLM did not extract this pattern"

    if best_match.is_reappearance:
        actual = "reappearance"
    elif best_match.matched_stock_item_id:
        actual = "duplicate"
    else:
        actual = "new"

    return actual, best_match.matched_stock_item_id, best_match.confidence, best_match.reasoning


def evaluate_result_b(
    case: dict,
    output: FocusedOutput,
) -> tuple[str, str | None, float | None, str]:
    """Extract judgment from strategy B output."""
    if not output.judgments:
        return "not_extracted", None, None, "No judgments returned"

    judgment = output.judgments[0]
    if judgment.is_duplicate:
        actual = "duplicate"
    else:
        actual = "new"

    return actual, judgment.matched_stock_item_id, judgment.confidence, judgment.reasoning


def get_expected_judgment(case: dict) -> str:
    case_type = case["case_type"]
    if case_type == "duplicate":
        return "duplicate"
    elif case_type == "non_duplicate":
        return "new"
    elif case_type == "reappearance":
        return "reappearance"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="V3: duplicate detection experiment")
    parser.add_argument("--strategy", choices=["full", "focused"], default="full")
    parser.add_argument("--stock-sizes", default="10,50,100")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    get_api_key()

    stock_sizes = [int(s) for s in args.stock_sizes.split(",")]
    test_cases = load_test_cases()
    scenario_map = load_scenarios()

    all_results: list[dict] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    total = len(stock_sizes) * len(test_cases) * args.runs
    current = 0

    for stock_size in stock_sizes:
        stock_items = load_stock_items(stock_size)
        print(f"\n{'='*60}")
        print(f"Stock size: {stock_size}")
        print(f"{'='*60}")

        for case in test_cases:
            min_stock = case.get("min_stock_size", 0)
            if stock_size < min_stock:
                print(f"  SKIP {case['case_id']}: stock_size {stock_size} < min_stock_size {min_stock}")
                continue

            scenario = scenario_map.get(case["case_id"])
            if scenario is None:
                print(f"  SKIP {case['case_id']}: no scenario found")
                continue

            expected = get_expected_judgment(case)

            for run in range(1, args.runs + 1):
                current += 1
                print(f"  [{current}/{total}] {case['case_id']} (run {run}) ...", end=" ", flush=True)

                try:
                    if args.strategy == "full":
                        output, latency = run_strategy_a(case, scenario, stock_items, args.model)
                        actual, matched_id, confidence, reasoning = evaluate_result_a(case, output)
                    else:
                        output, latency = run_strategy_b(case, stock_items, args.model)
                        actual, matched_id, confidence, reasoning = evaluate_result_b(case, output)

                    # reappearance cases: strategy B returns "duplicate" for stocked items
                    if args.strategy == "focused" and case["case_type"] == "reappearance" and actual == "duplicate":
                        actual = "reappearance"

                    is_correct = actual == expected

                    result = ExperimentResult(
                        case_id=case["case_id"],
                        case_type=case["case_type"],
                        stock_size=stock_size,
                        run_number=run,
                        strategy=args.strategy,
                        expected_judgment=expected,
                        actual_judgment=actual,
                        matched_stock_id=matched_id,
                        is_correct=is_correct,
                        confidence=confidence,
                        reasoning=reasoning,
                        latency_ms=latency,
                        model=args.model,
                        timestamp=timestamp,
                    )
                    all_results.append(result.model_dump())
                    status = "OK" if is_correct else "FAIL"
                    print(f"{status} ({actual} vs {expected}) [{latency:.0f}ms]")

                except Exception as e:
                    print(f"ERROR: {e}")
                    all_results.append(
                        ExperimentResult(
                            case_id=case["case_id"],
                            case_type=case["case_type"],
                            stock_size=stock_size,
                            run_number=run,
                            strategy=args.strategy,
                            expected_judgment=expected,
                            actual_judgment="error",
                            matched_stock_id=None,
                            is_correct=False,
                            confidence=None,
                            reasoning=str(e),
                            latency_ms=0,
                            model=args.model,
                            timestamp=timestamp,
                        ).model_dump()
                    )

    # Save results
    args.output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = args.output_dir / f"results-{args.strategy}-{date_str}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved: {output_path}")
    print(f"Total: {len(all_results)} cases")

    correct = sum(1 for r in all_results if r["is_correct"])
    total_valid = len(all_results)
    if total_valid > 0:
        print(f"Accuracy: {correct}/{total_valid} ({correct/total_valid*100:.1f}%)")


if __name__ == "__main__":
    main()
