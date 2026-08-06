"""Stage 8: three model experiments, all evaluated once on the same frozen human-reviewed
temporal test set (data/split_manifests/{run_id}_test.csv). Refuses to run (rather than
fabricate results) if the gold splits from Stage 7 don't exist yet.

  A. Train on Huang/USENIX weak labels only.
  B. Train on human-reviewed train+val (dev) only.
  C. Pretrain on Huang weak labels, fine-tune (continued boosting) on the human-reviewed dev set.

Label mapping: R1/R2 -> positive (1), B -> negative (0). U ("insufficient evidence") rows are
excluded from binary train/eval, matching the spec's requirement to report U results separately
rather than force them into a class -- see the "by_label" breakdown in the output.

Model: XGBoost over the 36-field structural/selector vector (lib/features.py) -- see that
module's docstring for why a compact tabular model, not a deep sequence model, is the right
choice at this sample size.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xgboost as xgb  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.features import build_feature_matrix  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from evaluation.metrics import full_metrics  # noqa: E402

POSITIVE_LABELS = {"R1", "R2"}
NEGATIVE_LABELS = {"B"}
XGB_PARAMS = dict(max_depth=3, eta=0.1, objective="binary:logistic", eval_metric="aucpr", seed=7702)
N_ROUNDS = 100


def to_binary(label: str) -> int | None:
    if label in POSITIVE_LABELS:
        return 1
    if label in NEGATIVE_LABELS:
        return 0
    return None  # U -- excluded from binary train/eval


def load_split(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["y"] = df["final_label"].map(to_binary)
    return df


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    split_dir = cfg["_resolved_paths"]["split_manifests"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]

    train_path = os.path.join(split_dir, f"{run_id}_train.csv")
    val_path = os.path.join(split_dir, f"{run_id}_val.csv")
    test_path = os.path.join(split_dir, f"{run_id}_test.csv")
    huang_path = os.path.join(gold_dir, f"{run_id}_huang_weak_labels.csv")
    if not (os.path.exists(train_path) and os.path.exists(test_path)):
        print(f"[train] {train_path} / {test_path} do not exist -- run Stage 7 "
              "(08_build_gold_dataset.py) after human review completes. Not running.")
        return
    if not os.path.exists(huang_path):
        print(f"[train] {huang_path} does not exist -- run Stage 7 first. Not running.")
        return

    train = load_split(train_path)
    val = load_split(val_path)
    test = load_split(test_path)
    huang = pd.read_csv(huang_path)

    # exclude Huang rows whose address also appears in the gold test set (avoid leakage into
    # Experiment A/C's training data from the population this workflow separately collected)
    test_addresses = set(test["delegate_address"].str.lower())
    huang_before = len(huang)
    huang = huang[~huang["address"].str.lower().isin(test_addresses)]
    n_excluded = huang_before - len(huang)

    X_huang = build_feature_matrix(huang["runtime_bytecode"])
    y_huang = huang["label"].to_numpy()

    dev = pd.concat([train[train["y"].notna()], val[val["y"].notna()]], ignore_index=True)
    X_dev = build_feature_matrix(dev["runtime_bytecode"])
    y_dev = dev["y"].to_numpy().astype(int)

    X_val = build_feature_matrix(val[val["y"].notna()]["runtime_bytecode"])
    y_val = val[val["y"].notna()]["y"].to_numpy().astype(int)

    test_labeled = test[test["y"].notna()].reset_index(drop=True)
    X_test = build_feature_matrix(test_labeled["runtime_bytecode"])
    y_test = test_labeled["y"].to_numpy().astype(int)
    n_u_test = int((test["final_label"] == "U").sum())

    results = {}
    predictions = {}

    def train_xgb(X, y, xgb_model=None):
        dtrain = xgb.DMatrix(X, label=y)
        return xgb.train(XGB_PARAMS, dtrain, num_boost_round=N_ROUNDS, xgb_model=xgb_model)

    booster_a = train_xgb(X_huang, y_huang)
    booster_b = train_xgb(X_dev, y_dev) if len(dev) > 0 else None
    booster_c = train_xgb(X_dev, y_dev, xgb_model=booster_a) if len(dev) > 0 else None

    for name, booster in [("A_huang_only", booster_a), ("B_human_only", booster_b), ("C_pretrain_finetune", booster_c)]:
        if booster is None:
            results[name] = {"status": "SKIPPED", "reason": "no human-reviewed dev rows available"}
            continue
        val_scores = booster.predict(xgb.DMatrix(X_val)) if len(X_val) else np.array([])
        test_scores = booster.predict(xgb.DMatrix(X_test)) if len(X_test) else np.array([])
        if len(X_val) == 0 or len(X_test) == 0:
            results[name] = {"status": "INSUFFICIENT_DATA",
                              "n_val_labeled": int(len(X_val)), "n_test_labeled": int(len(X_test))}
            continue
        m = full_metrics(y_test, test_scores, val_scores, y_val)
        m["status"] = "OK"
        m["n_train"] = int(len(y_huang) if name == "A_huang_only" else len(y_dev))
        m["n_test_labeled"] = int(len(y_test))
        m["n_test_positive"] = int(y_test.sum())
        m["n_test_u_excluded"] = n_u_test
        results[name] = m
        predictions[name] = pd.DataFrame({
            "address": test_labeled["delegate_address"], "final_label": test_labeled["final_label"],
            "y_true": y_test, "score": test_scores,
        })

    out_dir = gold_dir
    for name, pred_df in predictions.items():
        pred_df.to_csv(os.path.join(out_dir, f"{run_id}_predictions_{name}.csv"), index=False)

    summary = {
        "n_huang_train": int(len(y_huang)), "n_huang_excluded_test_overlap": int(n_excluded),
        "n_dev_train": int(len(dev)), "n_test_labeled": int(len(test_labeled)), "n_test_u": n_u_test,
        "results": results,
    }
    results_path = os.path.join(gold_dir, f"{run_id}_model_results.json")
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, indent=2, default=str))
    print(f"[train] wrote {results_path}")


if __name__ == "__main__":
    main()
