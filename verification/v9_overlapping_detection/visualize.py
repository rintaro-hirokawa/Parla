"""V9: オーバーラッピング遅れ検知 — 可視化ツール.

ベースライン補正累積偏差の折れ線チャートを生成する。
実音声検証でもそのまま使える汎用ツール。

Usage:
    uv run python visualize.py outputs/result_XXXXXX.json
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from config import DELAY_THRESHOLD_SEC, LOSS_THRESHOLD, OUTPUTS_DIR
from delay_detection import SMOOTHING_WINDOW, _smooth
from models import ExperimentResult, FAResult, PronunciationResult


def _compute_deviations(
    ref: FAResult,
    user: FAResult,
) -> tuple[list[float], list[float], float]:
    """生偏差、平滑化偏差、ベースラインを計算する.

    Returns:
        (raw_deviations, smoothed_deviations, baseline)
    """
    n = min(len(ref.words), len(user.words))
    raw = [user.words[i].start - ref.words[i].start for i in range(n)]
    baseline = statistics.median(raw) if raw else 0.0
    deviations = [d - baseline for d in raw]
    smoothed = _smooth(deviations, SMOOTHING_WINDOW)
    return deviations, smoothed, baseline


def plot_delay_chart(
    case_id: str,
    pattern: str,
    ref: FAResult,
    user: FAResult,
    ground_truth_indices: list[int],
    threshold: float,
    output_path: Path,
    baseline: float | None = None,
    tp: int = 0,
    fp: int = 0,
    fn: int = 0,
    show: bool = False,
    loss_threshold: float = LOSS_THRESHOLD,
) -> Path:
    """1テストケースの2パネルチャートを生成する.

    上パネル: ベースライン補正累積偏差（リズム）
    下パネル: 単語ごとの FA loss（発音確信度）
    """
    raw_dev, smoothed_dev, computed_baseline = _compute_deviations(ref, user)
    if baseline is None:
        baseline = computed_baseline
    n = len(smoothed_dev)
    words = [ref.words[i].text for i in range(n)]
    losses = [user.words[i].loss for i in range(n)]
    gt_set = set(ground_truth_indices)

    fig, (ax_dev, ax_loss) = plt.subplots(
        2, 1,
        figsize=(max(14, n * 0.18), 8),
        height_ratios=[3, 1.5],
        sharex=True,
    )
    x = np.arange(n)

    # ===== 上パネル: 偏差折れ線 =====

    # ground truth 背景帯
    if gt_set:
        sorted_gt = sorted(gt_set)
        region_start = sorted_gt[0]
        for j in range(1, len(sorted_gt)):
            if sorted_gt[j] != sorted_gt[j - 1] + 1:
                ax_dev.axvspan(region_start - 0.5, sorted_gt[j - 1] + 0.5,
                               alpha=0.10, color="#3498db", zorder=0)
                region_start = sorted_gt[j]
        ax_dev.axvspan(region_start - 0.5, sorted_gt[-1] + 0.5,
                       alpha=0.10, color="#3498db", zorder=0,
                       label="Ground truth")

    # 閾値超え区間の塗りつぶし
    smoothed_arr = np.array(smoothed_dev)
    above = smoothed_arr > threshold
    ax_dev.fill_between(x, smoothed_arr, threshold,
                        where=above, alpha=0.3, color="#e74c3c",
                        interpolate=True, label="Detected delay", zorder=2)

    # 生偏差（薄い線）
    ax_dev.plot(x, raw_dev, color="#bdc3c7", linewidth=0.8, alpha=0.6,
                label="Raw deviation", zorder=1)

    # 平滑化偏差（太い折れ線）
    ax_dev.plot(x, smoothed_dev, color="#2c3e50", linewidth=2.0,
                label="Smoothed deviation", zorder=3)

    # 閾値ライン
    ax_dev.axhline(y=threshold, color="#e67e22", linestyle="--", linewidth=1.0,
                   label=f"Threshold ({threshold}s)", zorder=1)
    ax_dev.axhline(y=0, color="#7f8c8d", linewidth=0.5, zorder=1)

    ax_dev.set_ylabel("Deviation from baseline (s)", fontsize=10)
    ax_dev.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

    # タイトル
    title = f"{case_id}  [{pattern}]"
    if gt_set:
        title += f"  |  TP={tp}  FP={fp}  FN={fn}"
    high_loss_count = sum(1 for l in losses if l > loss_threshold)
    title += f"  |  High loss words: {high_loss_count}"
    ax_dev.set_title(title, fontsize=12, fontweight="bold")

    # ベースライン注釈
    ax_dev.annotate(
        f"Baseline (shadowing delay): {baseline:.3f}s",
        xy=(0.98, 0.02), xycoords="axes fraction",
        ha="right", va="bottom", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )
    ax_dev.legend(loc="upper left", fontsize=8)

    # ===== 下パネル: loss バー =====

    bar_colors = ["#e74c3c" if l > loss_threshold else "#bdc3c7" for l in losses]
    ax_loss.bar(x, losses, color=bar_colors, width=0.8, edgecolor="none")
    ax_loss.axhline(y=loss_threshold, color="#e67e22", linestyle="--",
                    linewidth=1.0, label=f"Loss threshold ({loss_threshold})")
    ax_loss.set_ylabel("FA Loss", fontsize=10)
    ax_loss.set_xlabel("Word index", fontsize=10)
    ax_loss.legend(loc="upper left", fontsize=8)

    # X軸ラベル（下パネルのみ）
    show_indices = set(range(0, n, 5))
    if gt_set:
        show_indices.add(min(gt_set))
        show_indices.add(max(gt_set))
    # 高 loss 単語もラベル表示
    for i, l in enumerate(losses):
        if l > loss_threshold:
            show_indices.add(i)
    labels = [words[i] if i in show_indices else "" for i in range(n)]
    ax_loss.set_xticks(x)
    ax_loss.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)

    ax_dev.set_xlim(-1, n)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  チャート保存: {output_path.name}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return output_path


def plot_summary(
    results: list[ExperimentResult],
    output_path: Path,
) -> Path:
    """全ケースのサマリチャートを生成する."""
    case_ids = [r.case_id for r in results]
    fa_latencies = [r.fa_user_latency_ms for r in results]
    total_latencies = [r.total_latency_ms for r in results]
    n_delayed = [r.delayed_phrase_count for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    y_pos = np.arange(len(case_ids))

    # 1) FA レイテンシ
    ax = axes[0]
    bars = ax.barh(y_pos, fa_latencies, color="#3498db", height=0.6)
    ax.axvline(x=3000, color="#e74c3c", linestyle="--", label="Pass: 3000ms")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(case_ids, fontsize=8)
    ax.set_xlabel("FA Latency (ms)")
    ax.set_title("FA API Latency", fontweight="bold")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, fa_latencies):
        ax.text(bar.get_width() + 30, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}", va="center", fontsize=7)

    # 2) 全体レイテンシ
    ax = axes[1]
    bars = ax.barh(y_pos, total_latencies, color="#2ecc71", height=0.6)
    ax.axvline(x=8000, color="#e74c3c", linestyle="--", label="Pass: 8000ms")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(case_ids, fontsize=8)
    ax.set_xlabel("Total Latency (ms)")
    ax.set_title("Total Latency (FA + LLM)", fontweight="bold")
    ax.legend(fontsize=8)
    for bar, val in zip(bars, total_latencies):
        ax.text(bar.get_width() + 30, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}", va="center", fontsize=7)

    # 3) 検出された遅れ区間数
    ax = axes[2]
    bar_colors = ["#e74c3c" if d > 0 else "#3498db" for d in n_delayed]
    bars = ax.barh(y_pos, n_delayed, color=bar_colors, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(case_ids, fontsize=8)
    ax.set_xlabel("Delay Regions")
    ax.set_title("Detected Delay Regions", fontweight="bold")
    for bar, val in zip(bars, n_delayed):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val}", va="center", fontsize=7)

    fig.suptitle("V9 Experiment Summary", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  サマリチャート保存: {output_path.name}")
    return output_path


def plot_pronunciation_chart(
    case_id: str,
    pron_result: PronunciationResult,
    output_path: Path,
    show: bool = False,
    exclude_insertions: bool = True,
) -> Path:
    """Azure Pronunciation Assessment の結果チャートを生成する.

    上パネル: 単語ごとの AccuracyScore バー（色分け）
    下パネル: ErrorType マーカー

    Args:
        exclude_insertions: True の場合、Insertion（リファレンスにない余分な単語）を
            チャートから除外する。リファレンス単語ベースの表示になる。
    """
    if exclude_insertions:
        words = [w for w in pron_result.words if w.error_type != "Insertion"]
    else:
        words = pron_result.words
    n = len(words)
    if n == 0:
        print("  WARNING: No words to plot")
        return output_path

    fig, (ax_acc, ax_err) = plt.subplots(
        2, 1,
        figsize=(max(14, n * 0.2), 7),
        height_ratios=[3, 1],
        sharex=True,
    )
    x = np.arange(n)

    # === 上パネル: AccuracyScore バー ===
    scores = [w.accuracy_score for w in words]
    bar_colors = []
    for s, w in zip(scores, words):
        if w.error_type == "Omission":
            bar_colors.append("#95a5a6")  # 灰（発音されなかった）
        elif s >= 80:
            bar_colors.append("#2ecc71")  # 緑
        elif s >= 60:
            bar_colors.append("#f39c12")  # オレンジ
        else:
            bar_colors.append("#e74c3c")  # 赤

    ax_acc.bar(x, scores, color=bar_colors, width=0.8, edgecolor="none")
    ax_acc.axhline(y=60, color="#e67e22", linestyle="--", linewidth=1.0,
                   alpha=0.7, label="Mispronunciation threshold (60)")
    ax_acc.set_ylabel("Accuracy Score", fontsize=10)
    ax_acc.set_ylim(0, 105)

    # スコアサマリをタイトルに
    ps = pron_result
    title = (f"{case_id}  |  PronScore: {ps.pronunciation_score:.0f}  "
             f"Accuracy: {ps.accuracy_score:.0f}  Fluency: {ps.fluency_score:.0f}  "
             f"Completeness: {ps.completeness_score:.0f}  Prosody: {ps.prosody_score:.0f}")
    ax_acc.set_title(title, fontsize=11, fontweight="bold")
    ax_acc.legend(loc="lower left", fontsize=8)

    # === 下パネル: ErrorType マーカー ===
    error_colors = {
        "None": "#2ecc71",
        "Mispronunciation": "#e74c3c",
        "Omission": "#95a5a6",
        "Insertion": "#9b59b6",
    }
    error_markers = {
        "None": "o",
        "Mispronunciation": "X",
        "Omission": "s",
        "Insertion": "D",
    }
    error_types_to_show = ("None", "Mispronunciation", "Omission")
    if not exclude_insertions:
        error_types_to_show = ("None", "Mispronunciation", "Omission", "Insertion")
    for error_type in error_types_to_show:
        indices = [i for i, w in enumerate(words) if w.error_type == error_type]
        if indices:
            ax_err.scatter(
                indices, [0] * len(indices),
                c=error_colors.get(error_type, "#bdc3c7"),
                marker=error_markers.get(error_type, "o"),
                s=60, label=error_type, zorder=3,
            )
    ax_err.set_ylim(-0.5, 0.5)
    ax_err.set_yticks([])
    ax_err.set_xlabel("Word index", fontsize=10)
    ax_err.legend(loc="upper left", fontsize=8, ncol=4)

    # X軸ラベル
    # 低スコア/エラー単語 + 5単語おきにラベル表示
    show_indices = set(range(0, n, 5))
    for i, w in enumerate(words):
        if w.accuracy_score < 60 or w.error_type != "None":
            show_indices.add(i)
    labels = [words[i].word if i in show_indices else "" for i in range(n)]
    ax_err.set_xticks(x)
    ax_err.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)

    ax_acc.set_xlim(-1, n)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  発音評価チャート保存: {output_path.name}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return output_path


def plot_combined_chart(
    case_id: str,
    pron_result: PronunciationResult,
    ref_timestamps: FAResult,
    output_path: Path,
    threshold: float = DELAY_THRESHOLD_SEC,
    show: bool = False,
    exclude_insertions: bool = True,
    baseline_correction: bool = False,
) -> Path:
    """発音評価 + タイミング偏差の3パネル統合チャートを生成する.

    上パネル: タイミング偏差折れ線
    中パネル: AccuracyScore バー
    下パネル: ErrorType マーカー

    Args:
        baseline_correction: True でベースライン（median）補正を適用。
            オーバーラッピングでは False（同時発話がゴール）。
            シャドーイングでは True（一定の遅延は正常）。
    """
    if exclude_insertions:
        words = [w for w in pron_result.words if w.error_type != "Insertion"]
    else:
        words = list(pron_result.words)
    n = len(words)
    if n == 0:
        print("  WARNING: No words to plot")
        return output_path

    ref_words = ref_timestamps.words
    n_ref = len(ref_words)

    fig, (ax_dev, ax_acc, ax_err) = plt.subplots(
        3, 1,
        figsize=(max(14, n * 0.2), 10),
        height_ratios=[2.5, 2, 0.8],
        sharex=True,
    )
    x = np.arange(n)

    # === 上パネル: タイミング偏差 ===
    # Omission/Insertion でない単語のみ偏差を計算
    # リファレンス単語とのマッチングが必要
    raw_deviations = []
    ref_idx = 0
    for w in words:
        if w.offset_sec >= 0 and w.error_type not in ("Omission", "Insertion") and ref_idx < n_ref:
            # リファレンス側で同じ単語を探す
            while ref_idx < n_ref and ref_words[ref_idx].text.lower().strip(".,!?;:") != w.word.lower().strip(".,!?;:"):
                ref_idx += 1
            if ref_idx < n_ref:
                raw_deviations.append(w.offset_sec - ref_words[ref_idx].start)
                ref_idx += 1
            else:
                raw_deviations.append(None)
        else:
            raw_deviations.append(None)

    # ベースライン計算（None を除外）
    valid_devs = [d for d in raw_deviations if d is not None]
    if valid_devs:
        if baseline_correction:
            import statistics
            baseline = statistics.median(valid_devs)
        else:
            baseline = 0.0
        deviations = [(d - baseline if d is not None else None) for d in raw_deviations]
        smoothed = []
        for i in range(n):
            window = [deviations[j] for j in range(max(0, i-1), min(n, i+2)) if deviations[j] is not None]
            smoothed.append(sum(window) / len(window) if window else None)

        dev_plot = [d if d is not None else float('nan') for d in deviations]
        smooth_plot = [d if d is not None else float('nan') for d in smoothed]

        ax_dev.plot(x, dev_plot, color="#bdc3c7", linewidth=0.8, alpha=0.6, label="Raw deviation")
        ax_dev.plot(x, smooth_plot, color="#2c3e50", linewidth=2.0, label="Smoothed deviation")

        smooth_arr = np.array([d if d is not None else 0 for d in smoothed])
        above = smooth_arr > threshold
        ax_dev.fill_between(x, smooth_arr, threshold, where=above,
                            alpha=0.3, color="#e74c3c", interpolate=True, label="Detected delay")

        ax_dev.axhline(y=threshold, color="#e67e22", linestyle="--", linewidth=1.0,
                       label=f"Threshold ({threshold}s)")
        ax_dev.axhline(y=0, color="#7f8c8d", linewidth=0.5)

        mode_label = "Baseline corrected (shadowing)" if baseline_correction else "Raw (overlapping)"
        annotation = f"{mode_label}"
        if baseline_correction:
            annotation += f"  |  Baseline: {baseline:.3f}s"
        ax_dev.annotate(annotation, xy=(0.98, 0.02), xycoords="axes fraction",
                        ha="right", va="bottom", fontsize=8,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
    else:
        ax_dev.text(0.5, 0.5, "No timing data available", ha="center", va="center",
                    transform=ax_dev.transAxes, fontsize=12, color="#7f8c8d")

    ax_dev.set_ylabel("Timing deviation (s)", fontsize=9)
    ax_dev.legend(loc="upper left", fontsize=7)

    ps = pron_result
    title = (f"{case_id}  |  PronScore: {ps.pronunciation_score:.0f}  "
             f"Accuracy: {ps.accuracy_score:.0f}  Fluency: {ps.fluency_score:.0f}  "
             f"Completeness: {ps.completeness_score:.0f}  Prosody: {ps.prosody_score:.0f}")
    ax_dev.set_title(title, fontsize=11, fontweight="bold")

    # === 中パネル: AccuracyScore バー ===
    scores = [w.accuracy_score for w in words]
    bar_colors = []
    for s, w in zip(scores, words):
        if w.error_type == "Omission":
            bar_colors.append("#95a5a6")
        elif s >= 80:
            bar_colors.append("#2ecc71")
        elif s >= 60:
            bar_colors.append("#f39c12")
        else:
            bar_colors.append("#e74c3c")

    ax_acc.bar(x, scores, color=bar_colors, width=0.8, edgecolor="none")
    ax_acc.axhline(y=60, color="#e67e22", linestyle="--", linewidth=1.0, alpha=0.7,
                   label="Mispronunciation threshold (60)")
    ax_acc.set_ylabel("Accuracy Score", fontsize=9)
    ax_acc.set_ylim(0, 105)
    ax_acc.legend(loc="lower left", fontsize=7)

    # === 下パネル: ErrorType マーカー ===
    error_colors = {"None": "#2ecc71", "Mispronunciation": "#e74c3c",
                    "Omission": "#95a5a6", "Insertion": "#9b59b6"}
    error_markers = {"None": "o", "Mispronunciation": "X", "Omission": "s", "Insertion": "D"}
    types_to_show = ("None", "Mispronunciation", "Omission")
    if not exclude_insertions:
        types_to_show = ("None", "Mispronunciation", "Omission", "Insertion")
    for et in types_to_show:
        indices = [i for i, w in enumerate(words) if w.error_type == et]
        if indices:
            ax_err.scatter(indices, [0] * len(indices),
                           c=error_colors.get(et, "#bdc3c7"),
                           marker=error_markers.get(et, "o"),
                           s=60, label=et, zorder=3)
    ax_err.set_ylim(-0.5, 0.5)
    ax_err.set_yticks([])
    ax_err.set_xlabel("Word index", fontsize=9)
    ax_err.legend(loc="upper left", fontsize=7, ncol=4)

    # X軸ラベル
    show_indices = set(range(0, n, 5))
    for i, w in enumerate(words):
        if w.accuracy_score < 60 or w.error_type != "None":
            show_indices.add(i)
    labels = [words[i].word if i in show_indices else "" for i in range(n)]
    ax_err.set_xticks(x)
    ax_err.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)

    ax_dev.set_xlim(-1, n)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  統合チャート保存: {output_path.name}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return output_path


def generate_all_charts(result_json: Path, output_dir: Path | None = None) -> list[Path]:
    """結果JSONから全チャートを生成する."""
    with open(result_json, encoding="utf-8") as f:
        data = json.load(f)

    results = [ExperimentResult.model_validate(r) for r in data["results"]]
    fa_data = data.get("fa_data", {})

    if output_dir is None:
        output_dir = OUTPUTS_DIR / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    threshold = DELAY_THRESHOLD_SEC

    print("\n=== チャート生成 ===")

    for result in results:
        case_fa = fa_data.get(result.case_id)
        if case_fa is None:
            print(f"  スキップ（FA データなし）: {result.case_id}")
            continue

        ref = FAResult.model_validate(case_fa["reference"])
        user = FAResult.model_validate(case_fa["user"])
        gt_indices = case_fa.get("ground_truth_indices", [])

        chart_path = output_dir / f"{result.case_id}.png"
        plot_delay_chart(
            case_id=result.case_id,
            pattern=result.pattern,
            ref=ref,
            user=user,
            ground_truth_indices=gt_indices,
            threshold=threshold,
            output_path=chart_path,
            tp=result.true_positives,
            fp=result.false_positives,
            fn=result.false_negatives,
        )
        generated.append(chart_path)

    summary_path = output_dir / "summary.png"
    plot_summary(results, summary_path)
    generated.append(summary_path)

    print(f"\n合計 {len(generated)} 枚のチャートを生成")
    return generated


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize.py <result_json_path> [output_dir]")
        sys.exit(1)

    result_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    generate_all_charts(result_path, out_dir)
