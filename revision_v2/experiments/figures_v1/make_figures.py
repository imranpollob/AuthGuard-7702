#!/usr/bin/env python3
"""Publication figures for the TPS 2026 manuscript.

Three figures, each carrying a claim the tables state numerically:
  fig_clean_vs_asr   the thesis: clean performance does not predict adversarial robustness
  fig_attack_strength the methodological finding: model separation depends on attack strength
  fig_attention_dilution the mechanism: attention resists dilution that mean pooling cannot

Print constraints drive the styling. IEEE two-column figures are frequently read in
greyscale, so every series carries a distinct marker and dash pattern and identity is
never encoded by colour alone. Palette slots are the first three of the validated
categorical set, which clears all-pairs CVD and normal-vision separation.
"""
from __future__ import annotations

import argparse
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = os.path.join(RV2, "results")
OUT = os.path.join(RV2, "paper_final")

# Validated categorical slots 1-3 (all-pairs CVD dE 9.2, normal-vision 24.0).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#8a8a85"
GRID = "#dcdcd8"

plt.rcParams.update({
    "pdf.fonttype": 42,      # embed as Type 42/TrueType, not Type 3 (journal requirement)
    "ps.fonttype": 42,
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "axes.edgecolor": MUTED,
    "axes.linewidth": 0.5,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "text.color": INK,
    "axes.labelcolor": INK,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})


def style_axes(ax, ygrid=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)


def load_attacks():
    files = sorted(glob.glob(os.path.join(
        RESULTS, "adaptive_attacks_v2", "attack_per_row_seed*.csv.gz")))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def asr(frame, target, method):
    g = frame[(frame.target_model == target) & (frame.method == method)]
    eligible = g[g.clean_detected]
    return float(eligible.attack_success.mean()) if len(eligible) else np.nan


def clean_detection(frame, target):
    g = frame[frame.target_model == target].drop_duplicates(["seed", "sid"])
    return float(g.clean_detected.mean())


# --------------------------------------------------------------- figure 1
def fig_clean_vs_asr(frame, path):
    """Clean detection beside best-attack ASR, one row per model.

    A scatter is the natural form for "does clean predict robustness", but with ten
    models carrying long names the labels collide at column width. A dumbbell keeps both
    quantities and the comparison while staying legible: rows are sorted by robustness,
    and the clean markers visibly fail to follow that order.
    """
    labels = {
        "chunk_attention_16384": "Chunk attention 16K (ablation)",
        "authguard_seq_aug": "AuthGuard-Seq + aug. training",
        "authguard_seq": "AuthGuard-Seq",
        "emulator_logreg": "15-feature emulator",
        "flat_control_16384": "Flat control 16K (ablation)",
        "hist_ngram_xgb_aug": "Hist.+4-gram XGBoost + aug.",
        "flat_cnn_aug": "Flat CNN + aug. training",
        "flat_cnn": "Flat CNN",
        "chunk_mean_16384": "Chunk mean 16K (ablation)",
        "hist_ngram_xgb": "Hist.+4-gram XGBoost",
    }
    attention = {"authguard_seq", "chunk_attention_16384", "authguard_seq_aug"}
    rows = []
    for t in labels:
        if t not in set(frame.target_model):
            continue
        values = [asr(frame, t, m) for m in ("F200", "fixed_oracle_best",
                                             "random_search", "beam_search")]
        values = [v for v in values if not np.isnan(v)]
        rows.append((t, clean_detection(frame, t), max(values)))
    rows.sort(key=lambda r: r[2], reverse=True)  # most robust at top

    fig, ax = plt.subplots(figsize=(6.9, 2.9))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)
    for i, (t, clean, worst) in enumerate(rows):
        ax.plot([clean, worst], [i, i], color=GRID, linewidth=1.0, zorder=1,
                solid_capstyle="round")
        ax.scatter(clean, i, s=26, facecolor="white", edgecolor=AQUA, marker="o",
                   linewidth=1.0, zorder=3)
        ax.scatter(worst, i, s=26,
                   facecolor=BLUE if t in attention else "white",
                   edgecolor=BLUE if t in attention else ORANGE,
                   marker="D" if t in attention else "s", linewidth=1.0, zorder=3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([labels[t] for t, _, _ in rows], fontsize=6)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_xlabel("Rate")
    ax.scatter([], [], s=26, facecolor="white", edgecolor=AQUA, marker="o",
               linewidth=1.0, label="clean detection @ 5% FPR")
    ax.scatter([], [], s=26, facecolor=BLUE, edgecolor=BLUE, marker="D",
               linewidth=1.0, label="attack success (attention)")
    ax.scatter([], [], s=26, facecolor="white", edgecolor=ORANGE, marker="s",
               linewidth=1.0, label="attack success (other)")
    ax.legend(frameon=False, bbox_to_anchor=(0, 1.01, 1, 0.12), loc="lower left",
              ncol=3, handletextpad=0.4, borderpad=0.2, columnspacing=1.4)
    fig.savefig(path)
    plt.close(fig)
    print(f"  wrote {path}")


# --------------------------------------------------------------- figure 2
def fig_attack_strength(frame, path):
    """ASR against attack strength. The claim: separation depends on the instrument."""
    order = ["F200", "fixed_oracle_best", "beam_search", "random_search"]
    ticks = ["Fixed\nFlood-200%", "Best of 7\nfixed", "Beam\n64 queries",
             "Random\n64 queries"]
    series = [
        ("authguard_seq", "AuthGuard-Seq", BLUE, "o", "-"),
        ("emulator_logreg", "15-feature emulator", ORANGE, "s", "--"),
        ("flat_cnn", "Flat CNN", AQUA, "^", ":"),
    ]
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    style_axes(ax)
    x = np.arange(len(order))
    for target, label, colour, marker, dash in series:
        if target not in set(frame.target_model):
            continue
        ys = [asr(frame, target, m) for m in order]
        ax.plot(x, ys, color=colour, linewidth=1.1, linestyle=dash, marker=marker,
                markersize=3.4, markerfacecolor="white", markeredgewidth=0.9,
                markeredgecolor=colour, label=label, zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(ticks)
    ax.set_ylabel("Attack success rate")
    ax.set_xlabel("Attacker strength $\\rightarrow$")
    ax.set_ylim(-0.03, 1.05)
    ax.legend(frameon=False, loc="center left", handletextpad=0.5, borderpad=0.2)
    fig.savefig(path)
    plt.close(fig)
    print(f"  wrote {path}")


# --------------------------------------------------------------- figure 3
def fig_attention_dilution(path):
    """Attention mass on appended chunks vs the uniform-weighting baseline."""
    summary = pd.read_csv(os.path.join(
        RESULTS, "attention_dilution_v1", "attention_dilution_summary_all_folds.csv"))
    x = summary.flood_fraction.to_numpy() * 100
    measured = summary.attn_on_appended.to_numpy()
    baseline = summary.meanpool.to_numpy()

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    style_axes(ax)
    ax.fill_between(x, measured, baseline, color=BLUE, alpha=0.12, zorder=1,
                    label="dilution resisted")
    ax.plot(x, baseline, color=ORANGE, linewidth=1.1, linestyle="--", marker="s",
            markersize=3.4, markerfacecolor="white", markeredgewidth=0.9,
            markeredgecolor=ORANGE, label="uniform chunk weighting", zorder=3)
    ax.plot(x, measured, color=BLUE, linewidth=1.2, marker="o", markersize=3.4,
            markerfacecolor="white", markeredgewidth=0.9, markeredgecolor=BLUE,
            label="learned chunk attention", zorder=4)
    ax.annotate(f"{baseline[-1] - measured[-1]:.2f}", (x[-1], (baseline[-1] + measured[-1]) / 2),
                textcoords="offset points", xytext=(-26, -2), fontsize=6, color=BLUE)
    ax.set_xlabel("Appended donor bytes (% of original)")
    ax.set_ylabel("Aggregation mass on appended chunks")
    ax.set_xticks(x)
    ax.set_ylim(-0.03, 0.72)
    ax.legend(frameon=False, loc="upper left", handletextpad=0.5, borderpad=0.2)
    fig.savefig(path)
    plt.close(fig)
    print(f"  wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    wanted = set(args.only) if args.only else None

    if wanted is None or "dilution" in wanted:
        fig_attention_dilution(os.path.join(OUT, "fig-attention-dilution.pdf"))
    if wanted is None or "attack" in wanted:
        frame = load_attacks()
        fig_clean_vs_asr(frame, os.path.join(OUT, "fig-clean-vs-asr.pdf"))
        fig_attack_strength(frame, os.path.join(OUT, "fig-attack-strength.pdf"))


if __name__ == "__main__":
    main()
