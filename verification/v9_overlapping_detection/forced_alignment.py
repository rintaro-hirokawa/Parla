"""V9: オーバーラッピング遅れ検知 — Forced Alignment API ラッパー."""

from __future__ import annotations

import time
from pathlib import Path

from elevenlabs import ElevenLabs

from config import get_elevenlabs_api_key
from models import FAResult, FAWord


def _get_client() -> ElevenLabs:
    return ElevenLabs(api_key=get_elevenlabs_api_key())


def run_forced_alignment(audio_path: Path, text: str) -> tuple[FAResult, float]:
    """Forced Alignment API を呼び出す.

    Returns:
        (FAResult, latency_ms)
    """
    client = _get_client()

    start = time.perf_counter()
    with open(audio_path, "rb") as f:
        response = client.forced_alignment.create(file=f, text=text)
    latency_ms = (time.perf_counter() - start) * 1000

    # FA API は単語間の空白/無音区間も別エントリとして返すのでフィルタリング
    result = FAResult(
        words=[
            FAWord(text=w.text, start=w.start, end=w.end, loss=w.loss)
            for w in response.words
            if w.text.strip()
        ],
        loss=response.loss,
    )
    return result, latency_ms


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python forced_alignment.py <audio_path> <text>")
        sys.exit(1)

    audio = Path(sys.argv[1])
    txt = sys.argv[2]
    fa_result, lat = run_forced_alignment(audio, txt)
    print(f"レイテンシ: {lat:.0f}ms")
    print(f"全体loss: {fa_result.loss:.4f}")
    print(f"単語数: {len(fa_result.words)}")
    for w in fa_result.words[:10]:
        print(f"  {w.text:20s} {w.start:6.2f}-{w.end:6.2f}  loss={w.loss:.4f}")
    if len(fa_result.words) > 10:
        print(f"  ... 他 {len(fa_result.words) - 10} 単語")
