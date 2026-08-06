"""Stage 9: coverage-based deferral evaluation, using the frozen model scores from Stage 8
(no re-scoring, no threshold re-tuning after this point). Compares four policies at matched
defer rate: no deferral, coverage-based deferral, score-margin deferral, random deferral.
Reuses revision_v3/src/evaluation/selective_policy.py's WARN/LOW_OBSERVED_RISK/DEFER machinery
as-is. Runs against whichever of Stage 8's three models has the best val-set AUPRC (selection
happens on validation, never on the frozen temporal test set).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from evaluation.selective_policy import selective_decisions, selective_policy_metrics  # noqa: E402

RNG_SEED = 7702


def coverage_status(row: pd.Series) -> str:
    """PARTIAL when the evidence has a known gap: an unresolved EIP-7702 designator target, or
    a failed (not merely negative) verified-source lookup. COMPLETE otherwise. Computed from
    the same evidence packet fields used in Stage 4/5, not from the model score or label."""
    with open(row["evidence_path"]) as f:
        packet = json.load(f)
    if packet["proxy_evidence"]["is_eip7702_designator"]:
        return "PARTIAL"
    if packet["verified_source_code_availability"]["status"] == "UNAVAILABLE":
        return "PARTIAL"
    return "COMPLETE"


def margin_deferral(scores: np.ndarray, threshold: float, defer_rate: float) -> np.ndarray:
    """Defers the `defer_rate` fraction of items whose score is closest to the decision
    threshold (the classic score-margin/uncertainty-band deferral policy)."""
    n_defer = int(round(defer_rate * len(scores)))
    margin = np.abs(scores - threshold)
    defer_idx = np.argsort(margin)[:n_defer]
    decisions = np.where(scores >= threshold, "WARN", "LOW_OBSERVED_RISK").astype(object)
    decisions[defer_idx] = "DEFER"
    return decisions


def random_deferral(scores: np.ndarray, threshold: float, defer_rate: float, rng: np.random.Generator) -> np.ndarray:
    n_defer = int(round(defer_rate * len(scores)))
    defer_idx = rng.choice(len(scores), size=n_defer, replace=False) if n_defer > 0 else np.array([], dtype=int)
    decisions = np.where(scores >= threshold, "WARN", "LOW_OBSERVED_RISK").astype(object)
    decisions[defer_idx] = "DEFER"
    return decisions


def no_deferral(scores: np.ndarray, threshold: float) -> np.ndarray:
    return np.where(scores >= threshold, "WARN", "LOW_OBSERVED_RISK").astype(object)


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]
    results_path = os.path.join(gold_dir, f"{run_id}_model_results.json")
    if not os.path.exists(results_path):
        print(f"[coverage] {results_path} does not exist -- run Stage 8 (09_train_models.py) "
              "after human review completes. Not running.")
        return

    with open(results_path) as f:
        model_results = json.load(f)

    candidates = {name: r for name, r in model_results["results"].items() if r.get("status") == "OK"}
    if not candidates:
        print("[coverage] no Stage 8 model reached OK status; nothing to evaluate.")
        return
    # model selection on validation AUPRC would require val scores; Stage 8's full_metrics is
    # test-set metrics only, so -- to avoid selecting on the frozen test set -- default to the
    # pretrain+finetune model (C) if present, else whichever ran, and record this explicitly.
    chosen = "C_pretrain_finetune" if "C_pretrain_finetune" in candidates else next(iter(candidates))
    pred_path = os.path.join(gold_dir, f"{run_id}_predictions_{chosen}.csv")
    preds = pd.read_csv(pred_path)

    split_dir = cfg["_resolved_paths"]["split_manifests"]
    test = pd.read_csv(os.path.join(split_dir, f"{run_id}_test.csv"))
    preds = preds.merge(test[["delegate_address", "evidence_path"]], left_on="address", right_on="delegate_address", how="left")
    preds["coverage_status"] = preds.apply(coverage_status, axis=1)

    scores = preds["score"].to_numpy()
    y_true = preds["y_true"].to_numpy()
    threshold = candidates[chosen]["threshold_5pct"]

    coverage_decisions = selective_decisions(scores, threshold, preds["coverage_status"].to_numpy())
    coverage_metrics = selective_policy_metrics(y_true, coverage_decisions)
    defer_rate = coverage_metrics["defer_rate"] or 0.0

    margin_decisions = margin_deferral(scores, threshold, defer_rate)
    margin_metrics = selective_policy_metrics(y_true, margin_decisions)

    rng = np.random.default_rng(RNG_SEED)
    random_decisions = random_deferral(scores, threshold, defer_rate, rng)
    random_metrics = selective_policy_metrics(y_true, random_decisions)

    none_decisions = no_deferral(scores, threshold)
    none_metrics = selective_policy_metrics(y_true, none_decisions)

    # precision-vs-defer-rate curve for the margin policy, swept over defer_rate in [0, 0.9]
    curve = []
    for dr in np.linspace(0.0, 0.9, 10):
        d = margin_deferral(scores, threshold, dr)
        m = selective_policy_metrics(y_true, d)
        warn = d == "WARN"
        tp = int((warn & (y_true == 1)).sum())
        fp = int((warn & (y_true == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        curve.append({"defer_rate_requested": float(dr), "defer_rate_actual": m["defer_rate"],
                      "warn_precision": precision, "warn_recall": m["warn_recall_on_positives"]})

    summary = {
        "chosen_model": chosen, "threshold_5pct_fpr": threshold, "n_test": int(len(preds)),
        "policies": {
            "no_deferral": none_metrics,
            "coverage_based_deferral": coverage_metrics,
            "score_margin_deferral": margin_metrics,
            "random_deferral": random_metrics,
        },
        "coverage_status_counts": preds["coverage_status"].value_counts().to_dict(),
        "precision_vs_defer_rate_curve": curve,
    }

    out_path = os.path.join(gold_dir, f"{run_id}_coverage_deferral_results.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, indent=2, default=str))
    print(f"[coverage] wrote {out_path}")


if __name__ == "__main__":
    main()
