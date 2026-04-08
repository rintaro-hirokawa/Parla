"""V11: 録音補助CLIツール.

使い方:
    uv run python -m verification.v11_full_passage_evaluation.record
    uv run python -m verification.v11_full_passage_evaluation.record --overwrite
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

from verification.v11_full_passage_evaluation.test_cases import AUDIO_CASES, PASSAGE

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
    parser = argparse.ArgumentParser(description="V11 録音補助ツール")
    parser.add_argument("--overwrite", action="store_true", help="録音済みファイルも上書き")
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    total = len(AUDIO_CASES)
    existing = sum(
        1 for case in AUDIO_CASES
        if (AUDIO_DIR / PASSAGE.audio_filename(case.audio_type)).exists()
    )

    print(f"\n=== V11 録音ツール ===")
    print(f"パッセージ: {PASSAGE.topic} ({len(PASSAGE.sentences)}文)")
    print(f"{total}ファイル中 {existing}ファイル録音済み")
    print()

    for i, case in enumerate(AUDIO_CASES, 1):
        filename = PASSAGE.audio_filename(case.audio_type)
        filepath = AUDIO_DIR / filename

        if filepath.exists() and not args.overwrite:
            print(f"[{i}/{total}] {filename} — スキップ（録音済み）")
            continue

        print(f"\n{'=' * 70}")
        print(f"[{i}/{total}] {case.audio_type} ({case.audio_type_ja})")
        print(f"{'=' * 70}")
        print()
        print("  以下のテキストを上から順に読んでください:")
        print()
        for j, line in enumerate(case.script, 1):
            print(f"    {j}. {line}")
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
    recorded = sum(
        1 for case in AUDIO_CASES
        if (AUDIO_DIR / PASSAGE.audio_filename(case.audio_type)).exists()
    )
    print(f"{recorded}/{total} ファイル録音済み")

    if recorded == total:
        print("\n検証を実行できます:")
        print("  uv run python -m verification.v11_full_passage_evaluation.run")
    else:
        missing = [
            PASSAGE.audio_filename(case.audio_type)
            for case in AUDIO_CASES
            if not (AUDIO_DIR / PASSAGE.audio_filename(case.audio_type)).exists()
        ]
        print(f"\n未録音: {', '.join(missing)}")


if __name__ == "__main__":
    main()
