"""V2: 全シナリオ実行 + JSON出力.

使い方:
    uv run python -m verification.v2_item_extraction.run
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from verification.v2_item_extraction.config import V2Config
from verification.v2_item_extraction.generate import analyze
from verification.v2_item_extraction.test_cases import SCENARIOS, STOCK_ITEMS

AUDIO_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR = Path(__file__).parent / "outputs"


def main() -> None:
    config = V2Config()

    if not config.stage1_model or not config.stage2_model:
        print("エラー: config.py の stage1_model / stage2_model を設定してください。")
        print('例: stage1_model = "gemini/gemini-3.1-pro-preview"')
        sys.exit(1)

    # 録音ファイルの存在チェック
    missing = []
    for scenario in SCENARIOS:
        for case in scenario.audio_cases:
            audio_path = AUDIO_DIR / scenario.audio_filename(case.audio_type)
            if not audio_path.exists():
                missing.append(str(audio_path.name))

    if missing:
        print(f"エラー: 以下の音声ファイルが見つかりません: {', '.join(missing)}")
        print("先に録音を実行してください: uv run python -m verification.v2_item_extraction.record")
        sys.exit(1)

    results = []
    total = sum(len(s.audio_cases) for s in SCENARIOS)
    current = 0

    for scenario in SCENARIOS:
        for case in scenario.audio_cases:
            current += 1
            audio_path = AUDIO_DIR / scenario.audio_filename(case.audio_type)

            print(f"\n[{current}/{total}] {scenario.id} - {case.audio_type}")
            print(f"  日本語: {scenario.ja_prompt}")

            try:
                result = analyze(
                    audio_path=audio_path,
                    ja_prompt=scenario.ja_prompt,
                    stock_items=STOCK_ITEMS,
                    config=config,
                )

                results.append({
                    "scenario_id": scenario.id,
                    "audio_type": case.audio_type,
                    "ja_prompt": scenario.ja_prompt,
                    "model_en": scenario.model_en,
                    "stage1": {
                        "user_utterance": result.stage1.transcription.user_utterance,
                        "latency_s": round(result.stage1.latency_seconds, 2),
                    },
                    "stage2": {
                        "model_answer": result.stage2.feedback.model_answer,
                        "is_acceptable": result.stage2.feedback.is_acceptable,
                        "learning_items": [
                            item.model_dump() for item in result.stage2.feedback.learning_items
                        ],
                        "latency_s": round(result.stage2.latency_seconds, 2),
                    },
                })

            except Exception as e:
                print(f"  エラー: {e}")
                results.append({
                    "scenario_id": scenario.id,
                    "audio_type": case.audio_type,
                    "ja_prompt": scenario.ja_prompt,
                    "model_en": scenario.model_en,
                    "error": str(e),
                })

    # 結果を保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"result_{timestamp}.json"

    output = {
        "config": {
            "stage1_model": config.stage1_model,
            "stage2_model": config.stage2_model,
            "cefr_level": config.cefr_level,
            "english_variant": config.english_variant,
        },
        "stock_items": STOCK_ITEMS,
        "results": results,
    }

    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完了 ===")
    print(f"結果: {output_path}")
    print(f"成功: {sum(1 for r in results if 'error' not in r)}/{len(results)}")


if __name__ == "__main__":
    main()
