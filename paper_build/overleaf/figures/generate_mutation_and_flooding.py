#!/usr/bin/env python3
"""Generate task-aligned G-MUT and separately labeled G-VOL panels."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
MUT_SOURCE = ROOT / "figure_data/task_aligned_mutation_curve.json"
VOL_SOURCE = ROOT / "figure_data/task_aligned_mutation_volume.json"
OUTPUT = ROOT / "figures/mutation_and_flooding.pdf"

STYLES = {
    "authguard": ("AuthGuard", "#0072B2", "o", "-"),
    "opcode_xgb": ("Opcode-histogram XGBoost", "#E69F00", "s", "--"),
    "selector_model": ("Selector-LR", "#009E73", "D", "-."),
    "usenix_name_rule": ("Sensitive-name approximation", "#D55E00", "^", ":"),
    "usenix_struct_rule": ("External-call over-approximation", "#CC79A7", "v", "-"),
    "blocklist": ("Exact-hash blocklist", "#000000", "X", "--"),
}


def main() -> None:
    with MUT_SOURCE.open(encoding="utf-8") as handle:
        mutation = json.load(handle)
    with VOL_SOURCE.open(encoding="utf-8") as handle:
        volume = json.load(handle)

    plt.rcParams.update({
        "font.size": 8.5,
        "axes.labelsize": 8.5,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7.2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    })
    fig, (ax_mut, ax_vol) = plt.subplots(1, 2, figsize=(7.05, 2.65), sharey=True)

    tiers = ["M0", "M1", "M2", "M3"]
    mut_methods = [
        "authguard", "opcode_xgb", "selector_model", "usenix_name_rule",
        "usenix_struct_rule", "blocklist",
    ]
    for key in mut_methods:
        label, color, marker, linestyle = STYLES[key]
        values = [mutation[key][tier]["mean"] for tier in tiers]
        ax_mut.plot(tiers, values, color=color, marker=marker, linestyle=linestyle,
                    linewidth=1.45, markersize=4.3, markeredgecolor="black",
                    markeredgewidth=0.35, label=label)
    ax_mut.set_title("(a) G-MUT")
    ax_mut.set_xlabel("Cumulative condition")
    ax_mut.set_ylabel("Retained recall")

    fractions = ["0.0", "0.25", "0.5", "1.0", "2.0"]
    fraction_labels = ["+0%", "+25%", "+50%", "+100%", "+200%"]
    vol_methods = ["authguard", "opcode_xgb", "usenix_name_rule", "usenix_struct_rule"]
    for key in vol_methods:
        label, color, marker, linestyle = STYLES[key]
        values = [volume[key][fraction]["mean"] for fraction in fractions]
        ax_vol.plot(fraction_labels, values, color=color, marker=marker, linestyle=linestyle,
                    linewidth=1.45, markersize=4.3, markeredgecolor="black",
                    markeredgewidth=0.35, label=label)
    ax_vol.set_title("(b) G-VOL")
    ax_vol.set_xlabel("Post-STOP flooding volume")

    for ax in (ax_mut, ax_vol):
        ax.set_ylim(-0.035, 1.04)
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.grid(axis="y", color="0.88", linewidth=0.6)
    handles, labels = ax_mut.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.01),
               ncol=3, frameon=False, columnspacing=1.0, handlelength=2.3)
    fig.tight_layout(rect=(0, 0.18, 1, 1), pad=0.45, w_pad=1.1)
    fig.savefig(
        OUTPUT,
        format="pdf",
        bbox_inches="tight",
        metadata={
            "Title": "G-MUT mutation and G-VOL flooding stress tests",
            "Author": "Anonymous",
            "Subject": "Task-aligned v1 evaluation",
            "Keywords": "EIP-7702, G-MUT, G-VOL, retained recall",
            "Creator": "Anonymous reproducible figure script",
            "Producer": "Matplotlib",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
