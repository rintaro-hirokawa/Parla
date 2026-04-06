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

from config import DELAY_THRESHOLD_SEC, OUTPUTS_DIR
from delay_detection import SMOOTHING_WINDOW, _smooth
from models import ExperimentResult, FAResult


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
) -> Path:
    """1テストケースの累積偏差折れ線チャートを生成する."""
    raw_dev, smoothed_dev, computed_baseline = _compute_deviations(ref, user)
    if baseline is None:
        baseline = computed_baseline
    n = len(smoothed_dev)
    words = [ref.words[i].text for i in range(n)]
    gt_set = set(ground_truth_indices)

    fig, ax = plt.subplots(figsize=(max(14, n * 0.18), 5.5))
    x = np.arange(n)

    # ground truth 背景帯
    if gt_set:
        # 連続区間ごとに帯を描画
        sorted_gt = sorted(gt_set)
        region_start = sorted_gt[0]
        for j in range(1, len(sorted_gt)):
            if sorted_gt[j] != sorted_gt[j - 1] + 1:
                ax.axvspan(region_start - 0.5, sorted_gt[j - 1] + 0.5,
                           alpha=0.10, color="#3498db", zorder=0)
                region_start = sorted_gt[j]
        ax.axvspan(region_start - 0.5, sorted_gt[-1] + 0.5,
                   alpha=0.10, color="#3498db", zorder=0,
                   label="Ground truth")

    # 閾値超え区間の塗りつぶし
    smoothed_arr = np.array(smoothed_dev)
    above = smoothed_arr > threshold
    ax.fill_between(x, smoothed_arr, threshold,
                    where=above, alpha=0.3, color="#e74c3c",
                    interpolate=True, label="Detected delay", zorder=2)

    # 生偏差（薄い線）
    ax.plot(x, raw_dev, color="#bdc3c7", linewidth=0.8, alpha=0.6,
            label="Raw deviation", zorder=1)

    # 平滑化偏差（太い折れ線）
    ax.plot(x, smoothed_dev, color="#2c3e50", linewidth=2.0,
            label="Smoothed deviation", zorder=3)

    # 閾値ライン
    ax.axhline(y=threshold, color="#e67e22", linestyle="--", linewidth=1.0,
               label=f"Threshold ({threshold}s)", zorder=1)

    # ベースライン（ゼロ線）
    ax.axhline(y=0, color="#7f8c8d", linewidth=0.5, zorder=1)

    # X軸ラベル（間引き: 5単語おき + ground truth の端）
    show_indices = set(range(0, n, 5))
    if gt_set:
        show_indices.add(min(gt_set))
        show_indices.add(max(gt_set))
    labels = [words[i] if i in show_indices else "" for i in range(n)]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)

    # 軸
    ax.set_ylabel("Deviation from baseline (s)", fontsize=10)
    ax.set_xlabel("Word index", fontsize=10)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

    # タイトル
    title = f"{case_id}  [{pattern}]"
    if gt_set:
        title += f"  |  TP={tp}  FP={fp}  FN={fn}"
    ax.set_title(title, fontsize=12, fontweight="bold")

    # ベースライン注釈
    ax.annotate(
        f"Baseline (shadowing delay): {baseline:.3f}s",
        xy=(0.98, 0.02), xycoords="axes fraction",
        ha="right", va="bottom", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )

    # 凡例
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlim(-1, n)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  チャート保存: {output_path.name}")
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
