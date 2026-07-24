#!/usr/bin/env python3
"""Render reviewer-facing Markdown and LaTeX tables from verified v3 outputs."""
from __future__ import annotations

import argparse
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_OUTPUT = os.path.join(RV2, "results", "long_context_ablation_v3")

LABELS = {
    "flat_control_2048": "Flat control (2K)",
    "flat_control_16384": "Flat control (16K)",
    "chunk_attention_control_2048": "Chunk attention (2K)",
    "chunk_mean_control_16384": "Chunk mean (16K)",
    "chunk_attention_control_16384": "Chunk attention (16K)",
    "authguard_reference_16384": "Legacy AuthGuard reference (16K)",
}
ORDER = list(LABELS)


def fmt_mean_sd(mean, sd):
    return f"{mean:.3f} $\\pm$ {sd:.3f}"


def render(output_dir: str):
    summary = pd.read_csv(os.path.join(output_dir, "summary.csv"))
    complexity = (
        pd.read_csv(os.path.join(output_dir, "complexity.csv"))
        .drop_duplicates("model")
        .set_index("model")
    )
    # Use the fold-stratified analysis that mirrors the manuscript's
    # fold-mean -> seed-mean reporting hierarchy.  The earlier pooled-family
    # file is retained only as a historical diagnostic.
    bootstrap_path = os.path.join(output_dir, "fold_clustered_contrasts.csv")
    bootstrap = pd.read_csv(bootstrap_path) if os.path.exists(bootstrap_path) else None
    if bootstrap is not None:
        bootstrap = bootstrap[bootstrap["metric"] == "AUPRC"].copy()

    markdown = [
        "# AuthGuard-7702 v3 paper result packet",
        "",
        "All transformed results below use the declared per-model cap before scoring.",
        "",
        "| Model | Budget | Parameters | Clean AUPRC | F200 AUPRC | F200 Recall@5% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    latex_rows = []
    for model in ORDER:
        clean = summary[
            (summary["model"] == model) & (summary["condition"] == "M0")
        ].iloc[0]
        flood = summary[
            (summary["model"] == model) & (summary["condition"] == "F200")
        ].iloc[0]
        budget = int(complexity.loc[model, "token_budget"])
        params = int(complexity.loc[model, "trainable_params"])
        markdown.append(
            f"| {LABELS[model]} | {budget:,} | {params:,} | "
            f"{clean['AUPRC_mean']:.3f} +/- {clean['AUPRC_sd']:.3f} | "
            f"{flood['AUPRC_mean']:.3f} +/- {flood['AUPRC_sd']:.3f} | "
            f"{flood['Recall_05_mean']:.3f} +/- {flood['Recall_05_sd']:.3f} |"
        )
        latex_rows.append(
            f"{LABELS[model]} & {budget:,} & {params:,} & "
            f"{fmt_mean_sd(clean['AUPRC_mean'], clean['AUPRC_sd'])} & "
            f"{fmt_mean_sd(flood['AUPRC_mean'], flood['AUPRC_sd'])} & "
            f"{fmt_mean_sd(flood['Recall_05_mean'], flood['Recall_05_sd'])} \\\\"
        )

    contrast_rows = []
    if bootstrap is not None:
        markdown.extend([
            "",
            "## Predeclared mechanism contrasts",
            "",
            "| Mechanism | Condition | Delta AUPRC | Family-bootstrap 95% CI | Decision |",
            "|---|---|---:|---:|---|",
        ])
        for row in bootstrap.to_dict("records"):
            if row["ci95_low"] > 0:
                decision = "SUPPORTED"
            elif row["ci95_high"] < 0:
                decision = "NOT SUPPORTED"
            else:
                decision = "INCONCLUSIVE"
            markdown.append(
                f"| {row['contrast']} | {row['condition']} | "
            f"{row['delta']:+.4f} | "
                f"[{row['ci95_low']:+.4f}, {row['ci95_high']:+.4f}] | "
                f"{decision} |"
            )
            contrast_rows.append(
                f"{row['contrast'].title()} & {row['condition']} & "
                f"{row['delta']:+.4f} & "
                f"[{row['ci95_low']:+.4f}, {row['ci95_high']:+.4f}] & "
                f"{decision} \\\\"
            )

    length_path = os.path.join(output_dir, "length_stratified_summary.csv")
    if os.path.exists(length_path):
        length = pd.read_csv(length_path)
        length = length[length["condition"] == "M0"]
        markdown.extend([
            "",
            "## Predeclared clean length diagnostic",
            "",
            "| Model | Source <=2,048 AUPRC | Source >2,048 AUPRC |",
            "|---|---:|---:|",
        ])
        for model in (
            "flat_control_16384",
            "chunk_mean_control_16384",
            "chunk_attention_control_16384",
            "authguard_reference_16384",
        ):
            short = length[
                (length["model"] == model)
                & (length["length_stratum"] == "source_le_2048")
            ]
            long = length[
                (length["model"] == model)
                & (length["length_stratum"] == "source_gt_2048")
            ]
            if short.empty or long.empty:
                continue
            markdown.append(
                f"| {LABELS[model]} | "
                f"{short.iloc[0]['AUPRC_mean']:.3f} +/- "
                f"{short.iloc[0]['AUPRC_sd']:.3f} | "
                f"{long.iloc[0]['AUPRC_mean']:.3f} +/- "
                f"{long.iloc[0]['AUPRC_sd']:.3f} |"
            )

    markdown.extend([
        "",
        "The fold-stratified controlled contrasts, not the standalone legacy AuthGuard",
        "reference row, determine the mechanism claims. Fold results and per-row",
        "predictions remain in the source CSV artifacts.",
        "",
    ])
    with open(os.path.join(output_dir, "PAPER_RESULT_PACKET.md"), "w",
              encoding="utf-8") as handle:
        handle.write("\n".join(markdown))

    latex = [
        "% Generated from long_context_ablation_v3; do not edit numerical values by hand.",
        "\\begin{table*}[t]",
        "\\centering",
        "\\caption{Parameter-controlled long-context evaluation. Values are mean $\\pm$ "
        "standard deviation across three seed-level five-fold means.}",
        "\\label{tab:long-context-v3}",
        "\\begin{tabular}{lrrccc}",
        "\\toprule",
        "Model & Budget & Parameters & Clean AUPRC & F200 AUPRC & F200 R@5\\% \\\\",
        "\\midrule",
        *latex_rows,
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table*}",
    ]
    if contrast_rows:
        latex.extend([
            "",
            "\\begin{table}[t]",
            "\\centering",
            "\\caption{Predeclared paired mechanism contrasts with fold-stratified, "
            "family-clustered bootstrap intervals.}",
            "\\label{tab:long-context-contrasts-v3}",
            "\\begin{tabular}{llrrl}",
            "\\toprule",
            "Mechanism & Condition & $\\Delta$AUPRC & 95\\% CI & Decision \\\\",
            "\\midrule",
            *contrast_rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ])
    with open(os.path.join(output_dir, "paper_tables_v3.tex"), "w",
              encoding="utf-8") as handle:
        handle.write("\n".join(latex) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(os.path.abspath(args.output_dir))
    print(f"PAPER_PACKET_RENDERED output={os.path.abspath(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
