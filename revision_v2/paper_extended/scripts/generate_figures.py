#!/usr/bin/env python3
"""Generate manuscript charts from frozen, report-approved aggregate values."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def robustness():
    conditions = ["Clean M0", "F200", "M3+F200"]
    sequence_ap = np.array([0.930901, 0.910381, 0.910192])
    baseline_ap = np.array([0.827590, 0.576507, 0.563251])
    sequence_recall = np.array([0.828153, 0.723546, 0.718894])
    baseline_recall = np.array([0.582230, 0.171379, 0.178797])
    x = np.arange(len(conditions))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.55), sharey=True)
    for ax, seq, base, title in (
        (axes[0], sequence_ap, baseline_ap, "AUPRC"),
        (axes[1], sequence_recall, baseline_recall, "Recall at 5% policy"),
    ):
        ax.bar(x - width / 2, seq, width, color="#2c6fbb", label="AuthGuard-Seq")
        ax.bar(x + width / 2, base, width, color="#b8b8b8", edgecolor="#555555",
               label="Hist.+4-gram XGB")
        ax.set_xticks(x, conditions)
        ax.set_ylim(0, 1.02)
        ax.set_title(title)
        ax.grid(axis="y", color="#dddddd", linewidth=0.6)
        ax.set_axisbelow(True)
        for xpos, value in zip(x - width / 2, seq):
            ax.text(xpos, value + 0.018, f"{value:.3f}", ha="center", va="bottom", fontsize=7)
        for xpos, value in zip(x + width / 2, base):
            ax.text(xpos, value + 0.018, f"{value:.3f}", ha="center", va="bottom", fontsize=7)
    axes[0].set_ylabel("Mean across three seeds")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, -0.03))
    fig.subplots_adjust(bottom=0.24, wspace=0.12)
    save(fig, "clean_and_transformed_performance.pdf")


def model_selection():
    labels = [
        "Sequence only", "Fusion + source balance", "Fusion + consistency",
        "Fusion + multi-task", "Fusion, no auxiliary", "N-gram only", "Dense only",
    ]
    values = [0.948218, 0.906299, 0.888956, 0.864401, 0.856839, 0.834979, 0.705103]
    y = np.arange(len(labels))
    colors = ["#2c6fbb"] + ["#b8b8b8"] * (len(labels) - 1)
    fig, ax = plt.subplots(figsize=(3.48, 2.55))
    ax.barh(y, values, color=colors, edgecolor="#555555", linewidth=0.4)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0.65, 0.97)
    ax.set_xlabel("Mean validation AUPRC (seed 7702)")
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)
    for ypos, value in zip(y, values):
        ax.text(value + 0.004, ypos, f"{value:.3f}", va="center", fontsize=7)
    save(fig, "validation_model_selection.pdf")


if __name__ == "__main__":
    robustness()
    model_selection()

