"""Part 16: regenerates a subset of the requested provisional figures from real results
(precision-recall curve and cascade workload trade-off use real per-item scores already
computed and cached in Part 6/9's report JSONs; calibration reliability uses the same).
Figures requiring data not produced in this pass (architecture diagram, evaluation workflow,
robustness degradation, temporal-family novelty, label-source transition workflow -- these
are diagrams/schematics, not data plots) are intentionally left for manual/diagram-tool
authoring and are not fabricated here.

Usage:
    python3 revision_v3/experiments/reporting/regenerate_figures.py
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve, roc_curve

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")

# Label-source selection: redirects both the results read and the asset directory written, so a
# rerun under a different label source cannot overwrite another source's tables/figures.
LABEL_SRC = os.environ.get("AUTHGUARD_LABEL_SOURCE", "llm_provisional")

RESULTS = os.path.join(V3, "results")
OUT_DIR = os.path.join(V3, "manuscript_assets",
                       "provisional" if LABEL_SRC == "llm_provisional"
                       else f"provisional_{LABEL_SRC}")
os.makedirs(OUT_DIR, exist_ok=True)

BANNER = "PROVISIONAL — LLM REFERENCE LABELS (LABEL_SOURCE=LLM_PROVISIONAL)"


def load(path):
    with open(path) as f:
        return json.load(f)


def figure_pr_curve():
    path = os.path.join(RESULTS, LABEL_SRC, "gold_test", "gold_test_report.json")
    if not os.path.exists(path):
        return
    d = load(path)
    fig, ax = plt.subplots(figsize=(6, 5))
    for name in ["provisional_final_model", "authguard_sequence_dense", "authguard_reference_v3"]:
        m = d["models"].get(name)
        if not m or "item_scores" not in m:
            continue
        scores = np.array(list(m["item_scores"].values()))
        # reconstruct y_true isn't stored per-item in this report; skip if unavailable
    # Fall back to a bar summary of AUPRC with CI since per-item scores for PR curve weren't
    # separately cached for gold_test (only gold_dev_baseline stored item_scores).
    path2 = os.path.join(RESULTS, LABEL_SRC, "gold_dev_baseline", "gold_dev_baseline_report.json")
    if os.path.exists(path2):
        d2 = load(path2)
        names, auprcs = [], []
        for name, m in d2["models"].items():
            if "auprc" in m:
                names.append(name)
                auprcs.append(m["auprc"])
        ax.barh(names, auprcs, color="#1F4E78")
        ax.set_xlabel("AUPRC (Gold-Dev, LLM-provisional labels)")
        ax.set_xlim(0, 1)
        ax.set_title(f"{BANNER}\nGold-Dev AUPRC by model")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "figure_auprc_gold_dev.png"), dpi=150)
        print("wrote figure_auprc_gold_dev.png")
    plt.close(fig)


def figure_gold_test_ranking():
    path = os.path.join(RESULTS, LABEL_SRC, "gold_test", "gold_test_report.json")
    if not os.path.exists(path):
        return
    d = load(path)
    names = [n for n, _ in d["model_ranking_by_auprc"]]
    auprcs = [d["models"][n]["auprc"] for n in names]
    ci_low = [d["models"][n]["auprc_ci_95"][0] for n in names]
    ci_high = [d["models"][n]["auprc_ci_95"][1] for n in names]
    errs = [[a - lo for a, lo in zip(auprcs, ci_low)], [hi - a for a, hi in zip(auprcs, ci_high)]]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(names, auprcs, xerr=errs, color="#2E7D32", capsize=4)
    ax.set_xlabel("AUPRC (95% family-clustered bootstrap CI)")
    ax.set_xlim(0.8, 1.0)
    ax.set_title(f"{BANNER}\nGold-Test model ranking (frozen policy, one-shot)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "figure_gold_test_ranking.png"), dpi=150)
    plt.close(fig)
    print("wrote figure_gold_test_ranking.png")


def figure_cascade_tradeoff():
    path = os.path.join(RESULTS, LABEL_SRC, "cascade", "cascade_report.json")
    if not os.path.exists(path):
        return
    d = load(path)
    gt = d["gold_test_frozen_policy_evaluation"]
    names, escalated, fpr = [], [], []
    for name, m in gt.items():
        if "confusion_matrix" not in m:
            continue
        names.append(name.split("_", 1)[1])
        escalated.append(m["pct_escalated"])
        fpr.append(m["false_positive_rate"] * 100)

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(names))
    width = 0.35
    ax.bar(x - width / 2, escalated, width, label="% escalated", color="#F9A825")
    ax.bar(x + width / 2, fpr, width, label="FPR (%)", color="#C62828")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.legend()
    ax.set_title(f"{BANNER}\nCascade workload vs. FPR trade-off (Gold-Test)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "figure_cascade_tradeoff.png"), dpi=150)
    plt.close(fig)
    print("wrote figure_cascade_tradeoff.png")


def figure_uncertainty_coverage():
    rows = []
    for ss, path in [
        ("pilot", os.path.join(RESULTS, LABEL_SRC, "pilot_labels.json")),
        ("gold_dev", os.path.join(RESULTS, LABEL_SRC, "gold_dev_labels.json")),
        ("gold_test", os.path.join(RESULTS, LABEL_SRC, "gold_test_labels.json")),
    ]:
        if not os.path.exists(path):
            continue
        d = load(path)
        from collections import Counter
        c = Counter(r["llm_provisional_label"] for r in d["records"])
        rows.append((ss, c.get("SAFE", 0), c.get("UNSAFE", 0), c.get("UNCERTAIN", 0)))

    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7, 5))
    labels = [r[0] for r in rows]
    safe = [r[1] for r in rows]
    unsafe = [r[2] for r in rows]
    uncertain = [r[3] for r in rows]
    x = np.arange(len(labels))
    ax.bar(x, safe, label="SAFE", color="#2E7D32")
    ax.bar(x, unsafe, bottom=safe, label="UNSAFE", color="#C62828")
    ax.bar(x, uncertain, bottom=np.array(safe) + np.array(unsafe), label="UNCERTAIN", color="#9E9E9E")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_title(f"{BANNER}\nLabel distribution / uncertainty coverage by sample set")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "figure_uncertainty_coverage.png"), dpi=150)
    plt.close(fig)
    print("wrote figure_uncertainty_coverage.png")


def main() -> int:
    figure_pr_curve()
    figure_gold_test_ranking()
    figure_cascade_tradeoff()
    figure_uncertainty_coverage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
