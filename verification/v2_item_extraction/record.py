"""V2: 録音補助CLIツール.

使い方:
    uv pip install sounddevice soundfile numpy
    uv run python -m verification.v2_item_extraction.record
    uv run python -m verification.v2_item_extraction.record --overwrite
"""

import argparse
import sys
import threading
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    print("録音に必要なパッケージがインストールされていません。")
    print("以下を実行してください:")
    print("  uv pip install sounddevice soundfile numpy")
    sys.exit(1)

from verification.v2_item_extraction.test_cases import SCENARIOS

AUDIO_DIR = Path(__file__).parent / "audio"
SAMPLE_RATE = 16000
CHANNELS = 1


def record_audio() -> np.ndarray:
    """Enterで録音開始、Enterで停止。録音データを返す."""
    buffer = []
    stop_event = threading.Event()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"  (警告: {status})")
        buffer.append(indata.copy())

    input("  >> Enter で録音開始...")
    print("  \U0001f534 録音中... Enter で停止")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback,
    )
    stream.start()

    def wait_for_enter():
        input()
        stop_event.set()

    t = threading.Thread(target=wait_for_enter, daemon=True)
    t.start()
    stop_event.wait()

    stream.stop()
    stream.close()

    if not buffer:
        return np.array([], dtype="int16")
    return np.concatenate(buffer)


def play_audio(filepath: Path) -> None:
    """録音したファイルを再生."""
    data, sr = sf.read(filepath, dtype="int16")
    sd.play(data, sr)
    sd.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 録音補助ツール")
    parser.add_argument("--overwrite", action="store_true", help="録音済みファイルも上書き")
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    all_cases = []
    for scenario in SCENARIOS:
        for case in scenario.audio_cases:
            filename = scenario.audio_filename(case.audio_type)
            all_cases.append((scenario, case, filename))

    existing = sum(1 for _, _, f in all_cases if (AUDIO_DIR / f).exists())
    total = len(all_cases)

    print()
    print("=" * 60)
    print("  V2 録音ツール — 学習項目抽出精度の検証用")
    print("=" * 60)
    print()
    print("  やること:")
    print("    日本語の文が表示されるので、それを英語で話してください。")
    print("    2種類の話し方で録音します:")
    print()
    print("    [日本語混じり] 英語で話そうとして、途中で詰まって")
    print("                   日本語が混ざってしまう話し方")
    print("    [言い換え]     模範解答を見ずに、自分なりの英語で")
    print("                   日本語の意味を伝える話し方")
    print()
    print(f"  録音数: {total}ファイル（{len(SCENARIOS)}文 x 2パターン）")
    print(f"  録音済: {existing}ファイル")
    print()
    print("  操作: Enter→録音開始 → Enter→録音停止 → [p]再生/[r]やり直し/Enter→次へ")
    print()

    if existing == total and not args.overwrite:
        print("  全ファイル録音済みです。--overwrite で再録音できます。")
        return

    input("  準備ができたら Enter で開始...")

    for i, (scenario, case, filename) in enumerate(all_cases, 1):
        filepath = AUDIO_DIR / filename

        if filepath.exists() and not args.overwrite:
            continue

        # セパレータ
        print()
        print("-" * 60)
        print(f"  [{i}/{total}] {case.audio_type_ja}")
        print("-" * 60)

        # 日本語プロンプト（大きく表示）
        print()
        print(f"  \u25b6 日本語: {scenario.ja_prompt}")
        print()

        # 指示（何をすればいいか）
        print(f"  \u2192 {case.instruction}")
        print()

        # 参考スクリプト（小さめに）
        if case.audio_type == "different_structure":
            print(f"  (参考。読まなくてOK: \"{case.script}\")")
        else:
            print(f"  (参考: \"{case.script}\")")
        print()

        while True:
            audio_data = record_audio()

            if len(audio_data) == 0:
                print("  録音データがありません。やり直してください。")
                continue

            duration = len(audio_data) / SAMPLE_RATE
            sf.write(str(filepath), audio_data, SAMPLE_RATE)
            print(f"  \u2705 保存: {filename} ({duration:.1f}秒)")

            while True:
                choice = input("  [r] やり直し / [p] 再生 / Enter で次へ: ").strip().lower()
                if choice == "p":
                    print("  \U0001f50a 再生中...")
                    play_audio(filepath)
                elif choice == "r":
                    break
                else:
                    break

            if choice != "r":
                break

    print()
    print("=" * 60)
    recorded = sum(1 for _, _, f in all_cases if (AUDIO_DIR / f).exists())
    print(f"  録音完了: {recorded}/{total} ファイル")
    print("=" * 60)

    if recorded == total:
        print()
        print("  次のステップ:")
        print("    uv run python -m verification.v2_item_extraction.run")
    else:
        missing_files = [f for _, _, f in all_cases if not (AUDIO_DIR / f).exists()]
        print(f"\n  未録音: {', '.join(missing_files)}")


if __name__ == "__main__":
    main()
