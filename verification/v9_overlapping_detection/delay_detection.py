"""V9: オーバーラッピング遅れ検知 — 遅れ検出ロジック.

ベースライン補正累積偏差方式:
  オーバーラッピングでは学習者は模範音声をペースメーカーとして聴きながら発話するため、
  遅れたら自己修正しようとする。偏差は局所的な山と谷のパターンになる。

  1. 各単語の生偏差（模範との絶対的なずれ）を計算
  2. ベースライン（自然なシャドーイング遅延）を median で推定
  3. ベースラインからの偏差が閾値を超える連続区間を「遅れ」として検出
"""

from __future__ import annotations

import statistics

from config import DELAY_THRESHOLD_SEC, LOSS_THRESHOLD
from models import (
    DelayDetectionResult,
    FAResult,
    HighLossWord,
    PhraseDelay,
    WordDelay,
)

SMOOTHING_WINDOW = 3


def _smooth(values: list[float], window: int = SMOOTHING_WINDOW) -> list[float]:
    """スライディング平均で平滑化する."""
    n = len(values)
    if n == 0 or window <= 1:
        return values
    smoothed = []
    half = window // 2
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def _find_delay_regions(
    smoothed: list[float],
    threshold: float,
) -> list[tuple[int, int]]:
    """閾値を超える連続区間を検出する.

    Returns:
        [(start_index, end_index), ...] — end は exclusive
    """
    regions: list[tuple[int, int]] = []
    in_region = False
    start = 0
    for i, val in enumerate(smoothed):
        if val > threshold and not in_region:
            start = i
            in_region = True
        elif val <= threshold and in_region:
            regions.append((start, i))
            in_region = False
    if in_region:
        regions.append((start, len(smoothed)))
    return regions


def detect_delays(
    reference: FAResult,
    user: FAResult,
    threshold: float = DELAY_THRESHOLD_SEC,
) -> DelayDetectionResult:
    """模範とユーザーの FA 結果を比較し、遅れ箇所を検出する."""
    ref_words = reference.words
    user_words = user.words
    n = min(len(ref_words), len(user_words))

    if n == 0:
        return DelayDetectionResult(
            word_delays=[],
            phrase_delays=[],
            delayed_phrase_count=0,
            total_phrase_count=0,
            offset_sec=0.0,
        )

    # 1. 各単語の生偏差
    raw_deviations = [
        user_words[i].start - ref_words[i].start for i in range(n)
    ]

    # 2. ベースライン = median（自然なシャドーイング遅延）
    baseline = statistics.median(raw_deviations)

    # 3. ベースラインからの偏差
    deviations = [d - baseline for d in raw_deviations]

    # 4. 平滑化
    smoothed = _smooth(deviations)

    # 5. 単語レベル結果
    word_delays: list[WordDelay] = []
    for i in range(n):
        word_delays.append(WordDelay(
            word=ref_words[i].text,
            word_index=i,
            reference_start=ref_words[i].start,
            user_start=user_words[i].start,
            delay_sec=smoothed[i],
            is_delayed=smoothed[i] > threshold,
            reference_loss=ref_words[i].loss,
            user_loss=user_words[i].loss,
        ))

    # 6. 連続区間の検出 → PhraseDelay に変換
    regions = _find_delay_regions(smoothed, threshold)
    phrase_delays: list[PhraseDelay] = []
    for start, end in regions:
        window = word_delays[start:end]
        delays_in_region = [w.delay_sec for w in window]
        phrase_text = " ".join(w.word for w in window)
        phrase_delays.append(PhraseDelay(
            phrase=phrase_text,
            word_indices=list(range(start, end)),
            avg_delay_sec=sum(delays_in_region) / len(delays_in_region),
            max_delay_sec=max(delays_in_region),
            is_delayed=True,
        ))

    # 7. 高 loss 単語の収集
    high_loss_words = [
        HighLossWord(
            word=user_words[i].text,
            word_index=i,
            loss=user_words[i].loss,
        )
        for i in range(n)
        if user_words[i].loss > LOSS_THRESHOLD
    ]

    return DelayDetectionResult(
        word_delays=word_delays,
        phrase_delays=phrase_delays,
        delayed_phrase_count=len(phrase_delays),
        total_phrase_count=len(phrase_delays),
        offset_sec=baseline,
        high_loss_words=high_loss_words,
    )


def compute_accuracy(
    detection: DelayDetectionResult,
    ground_truth_indices: list[int],
) -> tuple[int, int, int, float, float]:
    """検知精度を計算する.

    Returns:
        (true_positives, false_positives, false_negatives, precision, recall)
    """
    gt_set = set(ground_truth_indices)
    detected_set = {w.word_index for w in detection.word_delays if w.is_delayed}

    tp = len(detected_set & gt_set)
    fp = len(detected_set - gt_set)
    fn = len(gt_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    return tp, fp, fn, precision, recall
