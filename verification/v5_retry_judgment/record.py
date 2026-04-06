"""V5: 録音補助CLIツール.

使い方:
    uv pip install sounddevice soundfile
    uv run python -m verification.v5_retry_judgment.record
    uv run python -m verification.v5_retry_judgment.record --overwrite
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

from verification.v5_retry_judgment.test_cases import SCENARIOS

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

    input("  Enter で録音開始...")
    print("  \U0001f534 録音中... Enter で停止")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback,
    )
    stream.start()

    # 別スレッドでEnter待ち
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
    parser = argparse.ArgumentParser(description="V5 録音補助ツール")
    parser.add_argument("--overwrite", action="store_true", help="録音済みファイルも上書き")
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # 全ケースをフラットに列挙
    all_cases = []
    for scenario in SCENARIOS:
        for case in scenario.audio_cases:
            filename = scenario.audio_filename(case.audio_type)
            all_cases.append((scenario, case, filename))

    existing = sum(1 for _, _, f in all_cases if (AUDIO_DIR / f).exists())
    total = len(all_cases)

    print(f"\n=== V5 録音ツール ===")
    print(f"{total}ファイル中 {existing}ファイル録音済み\n")

    for i, (scenario, case, filename) in enumerate(all_cases, 1):
        filepath = AUDIO_DIR / filename

        if filepath.exists() and not args.overwrite:
            print(f"[{i}/{total}] {filename} — スキップ（録音済み）")
            continue

        print(f"\n[{i}/{total}] {scenario.id} - {case.audio_type} ({case.audio_type_ja})")
        print(f"  学習項目: {scenario.learning_item}")
        print(f"  日本語:   {scenario.ja_prompt}")
        print(f"  模範解答: {scenario.reference_answer}")
        print(f"  ---")
        print(f"  話す内容: \"{case.script}\"")
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

    print(f"\n=== 録音完了 ===")
    recorded = sum(1 for _, _, f in all_cases if (AUDIO_DIR / f).exists())
    print(f"{recorded}/{total} ファイル録音済み")

    if recorded == total:
        print("\n検証を実行できます:")
        print("  uv run python -m verification.v5_retry_judgment.run")
    else:
        missing = [f for _, _, f in all_cases if not (AUDIO_DIR / f).exists()]
        print(f"\n未録音: {', '.join(missing)}")


if __name__ == "__main__":
    main()
