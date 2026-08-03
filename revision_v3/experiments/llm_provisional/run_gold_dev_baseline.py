"""Part 6: evaluates the existing frozen Phase 1/2 models, plus the source static rule,
against PROVISIONAL (LLM-generated) Gold-Dev labels. Uses each model's own already-frozen
per-checkpoint calibration/threshold (fit on the ORIGINAL primary-dataset validation folds in
Phase 1/2) -- no new threshold fitting on Gold-Dev happens here (that is Part 7 item #10,
a distinct, explicitly-labeled retraining/tuning experiment). UNCERTAIN-labeled items are
excluded from binary SAFE/UNSAFE metrics and reported separately as coverage.

Does not modify any Phase 1/2 checkpoint, result, or config file. Read-only w.r.t. those.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/llm_provisional/run_gold_dev_baseline.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Label-source selection. Defaults to "llm_provisional" so every previously-produced result is
# reproduced byte-for-byte when the variable is unset; setting AUTHGUARD_LABEL_SOURCE redirects
# BOTH the labels read and the results written, so one label source can never overwrite another.
LABEL_SRC = os.environ.get("AUTHGUARD_LABEL_SOURCE", "llm_provisional")
LABEL_SRC_BANNER = ("PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE"
                    if LABEL_SRC == "llm_provisional_opus5" else
                    "PROVISIONAL — LLM REFERENCE LABELS")

sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from evaluation import model_runtime  # noqa: E402
from evaluation.metrics_extra import binary_rule_report, expected_calibration_error, confusion_matrix, specificity_from_cm, balanced_accuracy_from_cm  # noqa: E402
from evaluation.metrics import auprc, auroc, brier, metrics_at_threshold  # noqa: E402

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", LABEL_SRC, "gold_dev_baseline")
os.makedirs(RESULTS_DIR, exist_ok=True)

CONTINUOUS_MODELS = ["authguard_sequence_dense", "authguard_reference_v3",
                      "flat_cnn_matched_16384", "flat_cnn_16384"]


def load_gold_dev():
    with open(os.path.join(HUMAN_EVAL_DIR, "gold_dev_manifest.csv"), newline="") as f:
        manifest = {r["item_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(REPO_ROOT, "revision_v3", "results", LABEL_SRC, "gold_dev_labels.json")) as f:
        labels = {r["item_id"]: r for r in json.load(f)["records"]}
    return manifest, labels


def mean_threshold(model_name: str, seeds, device) -> float:
    spec = model_runtime.MODEL_REGISTRY[model_name]
    thresholds = []
    for seed in seeds:
        for fold in range(5):
            ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed{seed}_fold{fold}.pt")
            if os.path.exists(ckpt_path):
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                thresholds.append(ckpt["threshold_5pct"])
    return float(np.mean(thresholds)) if thresholds else 0.5


def evaluate_continuous_model(model_name: str, item_ids, bytecodes, y_true, device) -> dict:
    scores_by_seed = model_runtime.score_dataset_with_ensemble(model_name, bytecodes, device=device)
    if not scores_by_seed:
        return {"error": "no checkpoints found"}
    seed_scores = np.stack(list(scores_by_seed.values()), axis=0)  # (n_seeds, n_items)
    point_scores = seed_scores.mean(axis=0)

    thr = mean_threshold(model_name, list(scores_by_seed.keys()), device)
    cm = confusion_matrix(y_true, point_scores, thr)
    at_thr = metrics_at_threshold(y_true, point_scores, thr)

    return {
        "n_evaluated": int(len(y_true)),
        "n_safe": int((y_true == 0).sum()),
        "n_unsafe": int((y_true == 1).sum()),
        "auprc": auprc(y_true, point_scores),
        "auroc": auroc(y_true, point_scores),
        "operating_threshold_source": "mean of each checkpoint's frozen threshold_5pct (fit on original Phase 1/2 validation folds, NOT re-fit on Gold-Dev)",
        "operating_threshold": thr,
        "precision": at_thr["precision"],
        "recall": at_thr["recall"],
        "specificity": specificity_from_cm(cm),
        "fpr": at_thr["observed_fpr"],
        "f1": at_thr["f1"],
        "balanced_accuracy": balanced_accuracy_from_cm(cm),
        "brier": brier(y_true, point_scores),
        "calibration_error": expected_calibration_error(y_true, point_scores),
        "confusion_matrix": cm,
        "per_seed_auprc": {str(s): auprc(y_true, sc) for s, sc in scores_by_seed.items()},
        "item_scores": {iid: float(sc) for iid, sc in zip(item_ids, point_scores)},
    }


def main() -> int:
    manifest, labels = load_gold_dev()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[gold_dev_baseline] device={device}")

    all_ids = list(labels.keys())
    label_of = {iid: labels[iid]["llm_provisional_label"] for iid in all_ids}
    n_uncertain = sum(1 for v in label_of.values() if v == "UNCERTAIN")

    binary_ids = [iid for iid in all_ids if label_of[iid] in ("SAFE", "UNSAFE")]
    y_true = np.array([1 if label_of[iid] == "UNSAFE" else 0 for iid in binary_ids])
    bytecodes = [manifest[iid]["runtime_bytecode"] for iid in binary_ids]

    report = {
        "LABEL_SOURCE": LABEL_SRC.upper(), "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
        "n_total_gold_dev_items": len(all_ids),
        "n_uncertain_excluded": n_uncertain,
        "uncertain_coverage_pct": round(100 * n_uncertain / len(all_ids), 1),
        "n_evaluated_binary": len(binary_ids),
        "models": {},
    }

    for model_name in CONTINUOUS_MODELS:
        print(f"[gold_dev_baseline] scoring {model_name} on {len(binary_ids)} binary-labeled items...")
        report["models"][model_name] = evaluate_continuous_model(model_name, binary_ids, bytecodes, y_true, device)

    # Source static rule (already-computed heuristic label from Phase 1 dataset construction,
    # exposed here as source_rule_label -- never shown to the LLM labeling stage).
    rule_preds = np.array([
        int(manifest[iid].get("source_label", 0)) for iid in binary_ids
    ])
    report["source_static_rule"] = binary_rule_report(y_true, rule_preds)
    report["source_static_rule"]["n_evaluated"] = len(binary_ids)

    out_path = os.path.join(RESULTS_DIR, "gold_dev_baseline_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote {out_path}")
    for name, m in report["models"].items():
        if "error" in m:
            print(f"  {name}: {m['error']}")
        else:
            print(f"  {name}: AUPRC={m['auprc']:.3f} AUROC={m['auroc']:.3f} "
                  f"recall={m['recall']:.3f} FPR={m['fpr']:.3f} F1={m['f1']:.3f}")
    print(f"  source_static_rule: precision={report['source_static_rule']['precision']:.3f} "
          f"recall={report['source_static_rule']['recall']:.3f}")
    print(f"  UNCERTAIN coverage: {report['uncertain_coverage_pct']}% ({n_uncertain}/{len(all_ids)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
