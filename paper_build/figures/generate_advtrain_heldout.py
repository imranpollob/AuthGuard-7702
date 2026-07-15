#!/usr/bin/env python3
"""Generate task-aligned G-ADV AuthGuard fold-mean panels."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "paper_build/data_hygiene/task_aligned_advtrain_results.json"
OUTPUT = ROOT / "paper_build/figures/advtrain_heldout.pdf"
MODELS = ["AuthGuard-M0", "AuthGuard-aug"]
LABELS = ["AuthGuard-M0", "AuthGuard-aug"]
COLORS = ["#4C78A8", "#F2CF5B"]
HATCHES = ["", "///"]


def main() -> None:
    with SOURCE.open(encoding="utf-8") as handle:
        aggregate = json.load(handle)["aggregate"]

    plt.rcParams.update({
        "font.size": 8.2,
        "axes.labelsize": 8.2,
        "axes.titlesize": 8.7,
        "xtick.labelsize": 7.8,
        "ytick.labelsize": 7.8,
        "legend.fontsize": 7.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    })
    fig, axes = plt.subplots(1, 3, figsize=(7.05, 2.45))
    width = 0.34

    def bars(ax, conditions, metric, title, ylabel=None):
        x = np.arange(len(conditions))
        for idx, (model, label, color, hatch) in enumerate(
            zip(MODELS, LABELS, COLORS, HATCHES)
        ):
            values = [aggregate[model][condition]["mean"][metric] for condition in conditions]
            xpos = x + (idx - 0.5) * width
            rects = ax.bar(xpos, values, width, color=color, edgecolor="black",
                           linewidth=0.55, hatch=hatch, label=label)
            for rect, value in zip(rects, values):
                ax.text(rect.get_x() + rect.get_width() / 2, value + 0.018,
                        f"{value:.3f}", ha="center", va="bottom", fontsize=6.5,
                        rotation=90)
        ax.set_xticks(x, conditions)
        ax.set_title(title)
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.set_ylim(0, 1.02)
        ax.grid(axis="y", color="0.88", linewidth=0.6)

    bars(axes[0], ["M0", "M3", "F200"], "AUPRC", "(a) AUPRC", "Five-fold mean")
    bars(axes[1], ["M3", "F200"], "recall", "(b) Recall")
    bars(axes[2], ["M3", "F200"], "FPR", "(c) Benign FPR")
    axes[2].set_ylim(0, 0.45)
    axes[2].set_yticks([0.0, 0.1, 0.2, 0.3, 0.4])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.005),
               ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.13, 1, 1), pad=0.45, w_pad=0.85)
    fig.savefig(
        OUTPUT,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Title": "G-ADV AuthGuard held-out evaluation",
            "Author": "Anonymous",
            "Subject": "Task-aligned v1 five-fold means",
            "Keywords": "EIP-7702, G-ADV, AUPRC, recall, FPR",
            "Creator": "Anonymous reproducible figure script",
            "Producer": "Matplotlib",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
