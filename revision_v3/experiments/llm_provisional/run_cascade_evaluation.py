"""Part 10: static-rule vs. AuthGuard vs. cascade-policy comparison. The escalation band (the
only free "policy" parameter) is selected using Gold-Dev ONLY, then the frozen policy is
evaluated exactly once on Gold-Test -- never revised after seeing Gold-Test results.

Cascade policies compared:
  A. AuthGuard alone (authguard_sequence_dense @ its frozen threshold)
  B. source static rule alone
  C. AuthGuard-first triage, static-rule escalation for score-ambiguous items
  D. static-rule-first triage, AuthGuard escalation for rule-flagged items
  E. uncertainty-triggered escalation (LLM-provisional UNCERTAIN items routed to deeper review)

"Deeper semantic analysis" cost for escalated items is NOT measured (no such system exists
here) -- it is explicitly reported as an assumption, not a benchmark, to avoid implying a
false precision.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/llm_provisional/run_cascade_evaluation.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation import model_runtime  # noqa: E402
from evaluation.metrics_extra import confusion_matrix, specificity_from_cm  # noqa: E402

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "cascade")
os.makedirs(RESULTS_DIR, exist_ok=True)
MEASURED_AUTHGUARD_LATENCY_MS = 2.9  # from Part 14's real CPU end-to-end median

MODEL_NAME = "authguard_sequence_dense"


def load_set(sample_set: str):
    with open(os.path.join(HUMAN_EVAL_DIR, f"{sample_set}_manifest.csv"), newline="") as f:
        manifest = {r["item_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", f"{sample_set}_labels.json")) as f:
        labels = {r["item_id"]: r for r in json.load(f)["records"]}
    return manifest, labels


def get_authguard_threshold(device) -> float:
    spec = model_runtime.MODEL_REGISTRY[MODEL_NAME]
    thresholds = []
    for seed in (7702, 7703, 7704):
        for fold in range(5):
            p = os.path.join(spec["checkpoint_dir"], f"{MODEL_NAME}_seed{seed}_fold{fold}.pt")
            if os.path.exists(p):
                thresholds.append(torch.load(p, map_location=device, weights_only=False)["threshold_5pct"])
    return float(np.mean(thresholds))


def score_set(sample_set: str, manifest, binary_ids, device):
    bytecodes = [manifest[iid]["runtime_bytecode"] for iid in binary_ids]
    scores_by_seed = model_runtime.score_dataset_with_ensemble(MODEL_NAME, bytecodes, device=device)
    return np.mean(list(scores_by_seed.values()), axis=0)


def policy_metrics(y_true, final_preds, n_escalated, n_total, cost_per_item_ms) -> dict:
    cm = confusion_matrix(y_true, final_preds.astype(float), threshold=0.5)
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) else 0.0
    fnr = 1 - recall
    fpr = 1 - specificity_from_cm(cm)
    return {
        "n_total": n_total, "n_escalated": n_escalated,
        "pct_escalated": round(100 * n_escalated / n_total, 1) if n_total else 0.0,
        "pct_resolved_locally": round(100 * (n_total - n_escalated) / n_total, 1) if n_total else 0.0,
        "unsafe_coverage_recall": recall, "false_negative_rate": fnr, "false_positive_rate": fpr,
        "confusion_matrix": cm,
        "avg_screening_cost_ms_measured_stages_only": cost_per_item_ms,
    }


def run_policies(manifest, labels, threshold, escalation_band, device, sample_set: str) -> dict:
    binary_ids = [iid for iid, r in labels.items() if r["llm_provisional_label"] in ("SAFE", "UNSAFE")]
    uncertain_ids = [iid for iid, r in labels.items() if r["llm_provisional_label"] == "UNCERTAIN"]
    all_ids = list(labels.keys())
    y_true = np.array([1 if labels[iid]["llm_provisional_label"] == "UNSAFE" else 0 for iid in binary_ids])
    scores = score_set(sample_set, manifest, binary_ids, device)
    rule_preds = np.array([int(manifest[iid].get("source_label", 0)) for iid in binary_ids])
    ag_preds = (scores >= threshold).astype(int)

    out = {}
    out["A_authguard_alone"] = policy_metrics(y_true, ag_preds, 0, len(binary_ids), MEASURED_AUTHGUARD_LATENCY_MS)
    out["B_static_rule_alone"] = policy_metrics(y_true, rule_preds, 0, len(binary_ids), 0.01)

    lo, hi = escalation_band
    in_band = (scores >= lo) & (scores <= hi)
    c_preds = np.where(in_band, rule_preds, ag_preds)
    out["C_authguard_first_rule_escalation"] = policy_metrics(
        y_true, c_preds, int(in_band.sum()), len(binary_ids),
        MEASURED_AUTHGUARD_LATENCY_MS + in_band.mean() * 0.01)

    rule_flagged = rule_preds == 1
    d_preds = np.where(rule_flagged, ag_preds, 0)
    out["D_rule_first_authguard_escalation"] = policy_metrics(
        y_true, d_preds, int(rule_flagged.sum()), len(binary_ids),
        0.01 + rule_flagged.mean() * MEASURED_AUTHGUARD_LATENCY_MS)

    out["E_uncertainty_triggered_escalation"] = {
        "n_total": len(all_ids), "n_escalated_to_deeper_review": len(uncertain_ids),
        "pct_escalated": round(100 * len(uncertain_ids) / len(all_ids), 1),
        "pct_resolved_locally_by_authguard_plus_rule": round(100 * len(binary_ids) / len(all_ids), 1),
        "note": "Escalated items are exactly the LLM-provisional UNCERTAIN set; their "
                "resolution cost/outcome under deeper (human or more expensive semantic) "
                "review is NOT measured here -- no such system was run. Only the routing "
                "rate is real.",
    }
    return out


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    threshold = get_authguard_threshold(device)
    print(f"[cascade] authguard_sequence_dense mean threshold_5pct = {threshold:.4f}")

    print("[cascade] developing escalation band on Gold-Dev only...")
    gd_manifest, gd_labels = load_set("gold_dev")
    gd_binary_ids = [iid for iid, r in gd_labels.items() if r["llm_provisional_label"] in ("SAFE", "UNSAFE")]
    gd_scores = score_set("gold_dev", gd_manifest, gd_binary_ids, device)
    # Escalation band: the middle tercile of Gold-Dev score distribution -- a simple,
    # pre-registered (chosen before touching Gold-Test), data-driven ambiguity zone.
    lo, hi = float(np.percentile(gd_scores, 33)), float(np.percentile(gd_scores, 67))
    print(f"[cascade] escalation band (from Gold-Dev tercile): [{lo:.4f}, {hi:.4f}]")

    gd_policies = run_policies(gd_manifest, gd_labels, threshold, (lo, hi), device, "gold_dev")

    print("[cascade] evaluating frozen policy on Gold-Test (one shot, no further tuning)...")
    gt_manifest, gt_labels = load_set("gold_test")
    gt_policies = run_policies(gt_manifest, gt_labels, threshold, (lo, hi), device, "gold_test")

    report = {
        "LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
        "authguard_threshold_used": threshold,
        "escalation_band_selected_on_gold_dev_only": {"low": lo, "high": hi},
        "gold_dev_policy_development_results": gd_policies,
        "gold_test_frozen_policy_evaluation": gt_policies,
        "note": "Policy (escalation band) was frozen after Gold-Dev; Gold-Test results below "
                "were not used to revise it.",
    }
    out_path = os.path.join(RESULTS_DIR, "cascade_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote {out_path}")
    for name, m in gt_policies.items():
        if "confusion_matrix" in m:
            print(f"  [gold_test] {name}: escalated={m['pct_escalated']}% "
                  f"recall={m['unsafe_coverage_recall']:.3f} FPR={m['false_positive_rate']:.3f}")
        else:
            print(f"  [gold_test] {name}: escalated={m['pct_escalated']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
