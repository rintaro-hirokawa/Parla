"""V1: パッセージ生成品質 — 実行スクリプト."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from verification.v1_passage_generation.config import V1Config
from verification.v1_passage_generation.generate import generate_passages

SOURCE_DIR = Path(__file__).parent / "source_texts"
OUTPUT_DIR = Path(__file__).parent / "outputs"


def load_source_text(filename: str = "sample_01.txt") -> str:
    """ソーステキストを読み込む."""
    path = SOURCE_DIR / filename
    if not path.exists():
        print(f"エラー: {path} が見つかりません")
        sys.exit(1)
    return path.read_text(encoding="utf-8").strip()


def save_output(result_dict: dict, config: V1Config) -> Path:
    """結果をJSONファイルに保存する."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"result_{timestamp}.json"
    output_path = OUTPUT_DIR / filename

    output = {
        "config": {
            "model": config.model,
            "cefr_level": config.cefr_level,
            "english_variant": config.english_variant,
            "passage_type": config.passage_type,
        },
        "result": result_dict,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def print_result(result_dict: dict) -> None:
    """結果を人間が読みやすい形式でコンソール出力する."""
    print(f"\n{'=' * 60}")
    print(f"ソース要約: {result_dict['source_summary']}")
    print(f"パッセージ数: {len(result_dict['passages'])}")
    print(f"{'=' * 60}")

    for passage in result_dict["passages"]:
        print(f"\n--- Passage {passage['passage_index']}: {passage['topic']} ---")
        print(f"タイプ: {passage['passage_type']}")

        word_count = 0
        for i, sentence in enumerate(passage["sentences"], 1):
            words = len(sentence["en"].split())
            word_count += words
            print(f"\n  [{i}] JA: {sentence['ja']}")
            print(f"      EN: {sentence['en']} ({words}語)")
            print(f"      H1: {sentence['hints']['hint1']}")
            print(f"      H2: {sentence['hints']['hint2']}")

        print(f"\n  合計: {len(passage['sentences'])}文, {word_count}語")


def main() -> None:
    """メイン実行."""
    config = V1Config()

    if not config.model:
        print("エラー: config.py の model にモデル名を設定してください")
        sys.exit(1)

    print(f"モデル: {config.model}")
    print(f"CEFR: {config.cefr_level} / {config.english_variant} / {config.passage_type}")

    source_text = load_source_text()
    print(f"ソーステキスト: {len(source_text)}文字")

    result = generate_passages(source_text, config)
    result_dict = result.model_dump()

    print_result(result_dict)

    output_path = save_output(result_dict, config)
    print(f"\n結果保存先: {output_path}")


if __name__ == "__main__":
    main()
