"""V11: 結果集計・定性レビュー表示."""

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "outputs"


def load_latest_result() -> dict:
    """最新の結果ファイルを読み込む."""
    files = sorted(OUTPUT_DIR.glob("result_*.json"))
    if not files:
        print("エラー: outputs/ に結果ファイルがありません。")
        print("先に実行してください: uv run python -m verification.v11_full_passage_evaluation.run")
        sys.exit(1)
    path = files[-1]
    print(f"読み込み: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def print_detail(data: dict) -> None:
    """各テストケースの詳細を表示."""
    print(f"\n{'=' * 80}")
    print(f"設定: {data['config']}")
    print(f"パッセージ: {data['passage']['topic']} ({data['passage']['num_sentences']}文)")
    print(f"\n--- 定量メトリクス ---")
    m = data["metrics"]
    print(f"  正答率:          {m['accuracy']:.1f}%")
    print(f"  レイテンシ中央値: {m['stream_latency_median']:.2f}s")
    print(f"  レイテンシ最大:  {m['stream_latency_max']:.2f}s")
    print(f"  判定: {'PASS' if m['pass'] else 'FAIL'}")

    for r in data["results"]:
        print(f"\n{'=' * 60}")
        expected = "PASS" if r["expected_pass"] else "FAIL"
        got = "PASS" if r["median_passed"] else "FAIL"
        match_mark = "\u2705" if r["expected_pass"] == r["median_passed"] else "\u274c"
        print(f"{match_mark} {r['audio_type']} ({r['audio_type_ja']})")
        print(f"  期待: {expected} / 実際: {got}")
        print(f"  ストリームレイテンシ: {r['median_stream_latency']:.2f}s")
        print(f"  CompletenessScore: {r['median_completeness']:.1f}%")

        # 最初の run の詳細
        run = r["all_runs"][0]
        eval_data = run["evaluation"]

        print(f"\n  --- Azure 認識テキスト ---")
        print(f"    {eval_data['azure']['recognized_text'][:200]}...")

        print(f"\n  --- 文ごとの添削結果 ---")
        for s in eval_data["sentences"]:
            status_icon = {
                "correct": "\u2705", "paraphrase": "\U0001f4dd", "error": "\u274c"
            }.get(s["status"], "?")
            print(f"    {status_icon} [{s['index']}] {s['status']} (similarity={s['similarity']:.2f})")
            print(f"       ユーザー: {s['user_text']}")
            print(f"       模範:     {s['model_text']}")
            if s["diff_segments"]:
                for d in s["diff_segments"]:
                    print(f"       \u2192 \"{d['user_part']}\" → \"{d['model_part']}\" ({d['note']})")


def main() -> None:
    data = load_latest_result()
    print_detail(data)


if __name__ == "__main__":
    main()
