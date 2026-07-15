#!/usr/bin/env python3
"""Generate the task-aligned G-DET family-vs-random AUPRC figure."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "figure_data/task_aligned_detection_results.json"
OUTPUT = ROOT / "figures/random_vs_family.pdf"

METHODS = [
    ("blocklist", "Exact-hash blocklist"),
    ("selector_model", "Selector-LR"),
    ("opcode_rf", "Opcode-histogram RF"),
    ("opcode_xgb", "Opcode-histogram XGBoost"),
    ("authguard", "AuthGuard"),
]


def main() -> None:
    with SOURCE.open(encoding="utf-8") as handle:
        task = json.load(handle)["primary_mal_vs_cleared"]

    family = [task["leave_family_out"][key]["mean"]["AUPRC"] for key, _ in METHODS]
    random = [task["random_split"][key]["mean"]["AUPRC"] for key, _ in METHODS]

    plt.rcParams.update({
        "font.size": 8.5,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(3.45, 2.55))
    ypos = list(range(len(METHODS)))
    for y, fval, rval in zip(ypos, family, random):
        ax.plot([fval, rval], [y, y], color="0.62", linewidth=1.1, zorder=1)
    ax.scatter(family, ypos, s=28, marker="o", facecolor="#0072B2", edgecolor="black",
               linewidth=0.45, label="Family-grouped", zorder=3)
    ax.scatter(random, ypos, s=30, marker="s", facecolor="white", edgecolor="#D55E00",
               linewidth=1.1, label="Seeded random diagnostic", zorder=3)
    for y, fval, rval in zip(ypos, family, random):
        ax.text(fval - 0.010, y + 0.19, f"{fval:.3f}", ha="right", va="center", fontsize=7)
        ax.text(rval + 0.010, y + 0.19, f"{rval:.3f}", ha="left", va="center", fontsize=7)

    ax.set_yticks(ypos, [label for _, label in METHODS])
    ax.set_xlim(0.27, 1.03)
    ax.set_xlabel("AUPRC")
    ax.grid(axis="x", color="0.88", linewidth=0.6)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2,
              frameon=False, handletextpad=0.5, columnspacing=0.8)
    fig.tight_layout(rect=(0, 0.12, 1, 1), pad=0.35)
    fig.savefig(
        OUTPUT,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Title": "G-DET random versus family-grouped AUPRC",
            "Author": "Anonymous",
            "Subject": "Task-aligned v1 evaluation",
            "Keywords": "EIP-7702, G-DET, AUPRC",
            "Creator": "Anonymous reproducible figure script",
            "Producer": "Matplotlib",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
