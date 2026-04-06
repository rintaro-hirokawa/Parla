"""V9: オーバーラッピング遅れ検知 — テストケース定義.

リアルなオーバーラッピングのパターンを TTS 速度操作でシミュレートする。
オーバーラッピングでは模範音声がペースメーカーとして機能するため、
学習者は遅れに気づいて自己修正しようとする。
テストケースはこの前提に基づいて設計している。

パターン:
  sync          — 正常に追従。遅れなし
  stumble       — 特定フレーズで詰まり、直後に巻き返す（鋭い山 + 回復）
  no_linking    — 連結不可。各文を個別速度で遅めに、文間で再同期（のこぎり歯）
  gradual       — 構文の複雑な箇所で数語にわたってじわじわ遅れ、その後回復
  different_voice — 声質差の影響確認
"""

from __future__ import annotations

import json

from config import (
    DEFAULT_SPEED,
    DIFFERENT_VOICE_ID,
    SIMULATED_VOICE_ID,
    V1_OUTPUTS_DIR,
)
from models import DelayedSegment, TestCase


def load_v1_passages(max_files: int = 1) -> list[dict]:
    """V1出力JSONからパッセージ情報を読み込む."""
    output_files = sorted(V1_OUTPUTS_DIR.glob("result_*.json"))
    if not output_files:
        raise FileNotFoundError(f"V1出力が見つかりません: {V1_OUTPUTS_DIR}")

    passages = []
    for fpath in output_files[:max_files]:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        for p in data["result"]["passages"]:
            sentences = p["sentences"]
            en_sentences = [s["en"] for s in sentences]
            full_text = " ".join(en_sentences)

            # 文境界の単語インデックスを記録（のこぎり歯パターン用）
            word_offset = 0
            sentence_boundaries: list[tuple[int, int]] = []
            for s_text in en_sentences:
                word_count = len(s_text.split())
                sentence_boundaries.append((word_offset, word_offset + word_count))
                word_offset += word_count

            passages.append({
                "topic": p["topic"],
                "full_text": full_text,
                "word_count": word_offset,
                "sentences": en_sentences,
                "sentence_boundaries": sentence_boundaries,
            })
    return passages


def build_test_cases(num_passages: int = 1) -> list[TestCase]:
    """全テストケースを構築する."""
    passages = load_v1_passages(max_files=1)
    if not passages:
        raise ValueError("パッセージが見つかりません")

    cases: list[TestCase] = []

    for i, passage in enumerate(passages[:num_passages]):
        text = passage["full_text"]
        words = text.split()
        n_words = len(words)
        boundaries = passage["sentence_boundaries"]
        pid = f"p{i + 1}"

        # --- 1) sync: 同速度・別Voice で正常追従 ---
        cases.append(TestCase(
            case_id=f"{pid}_sync",
            passage_text=text,
            pattern="sync",
            speed=DEFAULT_SPEED,
            voice_id=SIMULATED_VOICE_ID,
            delayed_segments=[],
            delayed_word_indices=[],
        ))

        # --- 2) stumble: 特定フレーズで詰まり + 直後に巻き返し ---
        # パッセージ中盤の1フレーズ(5語)を遅くし、直後の3語を速くする
        mid = n_words // 2
        stumble_start = mid
        stumble_end = min(mid + 5, n_words)
        recovery_end = min(stumble_end + 3, n_words)
        stumble_gt = list(range(stumble_start, stumble_end))

        stumble_segments = [
            DelayedSegment(start_word=stumble_start, end_word=stumble_end, speed=0.7),
            DelayedSegment(start_word=stumble_end, end_word=recovery_end, speed=1.2),
        ]
        cases.append(TestCase(
            case_id=f"{pid}_stumble",
            passage_text=text,
            pattern="stumble",
            speed=DEFAULT_SPEED,
            voice_id=SIMULATED_VOICE_ID,
            delayed_segments=stumble_segments,
            delayed_word_indices=stumble_gt,
        ))

        # --- 3) no_linking: 各文を少し遅く、文間で再同期 ---
        # 各文を speed=0.92 で生成（各単語間に微小なギャップが蓄積）
        # 文間のギャップで再同期を模擬するため、文ごとに個別TTS
        # → pydub結合時に文間ポーズを短くすることで「追いつこうとした」を再現
        #
        # ground truth: 各文の後半（遅延が蓄積する箇所）
        no_linking_segments: list[DelayedSegment] = []
        no_linking_gt: list[int] = []
        for sent_start, sent_end in boundaries:
            sent_len = sent_end - sent_start
            no_linking_segments.append(
                DelayedSegment(start_word=sent_start, end_word=sent_end, speed=0.92)
            )
            # 各文の後半を ground truth とする（遅延が蓄積する箇所）
            gt_start = sent_start + sent_len // 2
            no_linking_gt.extend(range(gt_start, sent_end))

        cases.append(TestCase(
            case_id=f"{pid}_no_linking",
            passage_text=text,
            pattern="no_linking",
            speed=DEFAULT_SPEED,  # 文間は通常速度（再同期）
            voice_id=SIMULATED_VOICE_ID,
            delayed_segments=no_linking_segments,
            delayed_word_indices=no_linking_gt,
        ))

        # --- 4) gradual: 構文が複雑な箇所で数語にわたってじわじわ遅れ ---
        # パッセージの 1/3 付近の8語をわずかに遅くする（0.88）
        # 局所デルタ方式では各語の変化が小さくて検出できないが、
        # 累積偏差方式では検出できるはず
        grad_start = n_words // 3
        grad_end = min(grad_start + 8, n_words)
        grad_gt = list(range(grad_start, grad_end))

        gradual_segments = [
            DelayedSegment(start_word=grad_start, end_word=grad_end, speed=0.88),
        ]
        cases.append(TestCase(
            case_id=f"{pid}_gradual",
            passage_text=text,
            pattern="gradual",
            speed=DEFAULT_SPEED,
            voice_id=SIMULATED_VOICE_ID,
            delayed_segments=gradual_segments,
            delayed_word_indices=grad_gt,
        ))

        # --- 5) different_voice: 声質差の影響確認 ---
        cases.append(TestCase(
            case_id=f"{pid}_different_voice",
            passage_text=text,
            pattern="different_voice",
            speed=DEFAULT_SPEED,
            voice_id=DIFFERENT_VOICE_ID,
            delayed_segments=[],
            delayed_word_indices=[],
        ))

    return cases


if __name__ == "__main__":
    test_cases = build_test_cases()
    print(f"テストケース数: {len(test_cases)}\n")
    for tc in test_cases:
        words = tc.passage_text.split()
        print(f"  {tc.case_id}: pattern={tc.pattern}, words={len(words)}, "
              f"delayed_gt={len(tc.delayed_word_indices)}, "
              f"segments={len(tc.delayed_segments)}")
