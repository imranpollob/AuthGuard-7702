#!/usr/bin/env python3
"""G-DET v2: corrected threshold protocol (inner family-grouped stratified OOF), FPR,
per-row score persistence, 5 seeds for stochastic learned methods.

Tasks: primary (mal vs benign_cleared) and secondary (+benign_general), family-grouped
stored folds + random diagnostic. Outputs under revision_v2/results/gdet_v2/.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import (load_corpus, task_arrays, feature_views, default_methods,  # noqa: E402
                     run_gdet, write_manifest, verify_frozen_or_die, RV2, DH, SEED)

OUT = os.path.join(RV2, "results", "gdet_v2")
SEEDS = [SEED, 7703, 7704, 7705, 7706]


def rule_score_arrays(sub, Xds, meta):
    dcols = meta["dense_cols"]
    name_j = dcols.index("has_sensitive_selector")
    call_j = dcols.index("n_call_family")
    return {
        "usenix_shipped_oracle": (sub["class"] == "malicious").astype(float).to_numpy(),
        "usenix_name_rule": (Xds[:, name_j] > 0).astype(float),
        "usenix_struct_rule": (Xds[:, call_j] > 0).astype(float),
    }


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)

    all_out = {}
    row_frames = []
    thr_rows_all = []
    for task in ["primary", "secondary"]:
        sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, task)
        rules = rule_score_arrays(sub, Xds, meta)
        methods = default_methods(views, views["n_dense"])
        task_out = {}
        for split_name, random_split in [("leave_family_out", False), ("random_split", True)]:
            agg, rows, thr_rows = run_gdet(
                sub, y, folds, Xds, Xns, meta, methods, seeds=SEEDS, tag=f"{task}",
                random_split=random_split, rule_scores=rules)
            rows["task"] = task
            row_frames.append(rows)
            thr_rows_all.extend(thr_rows)
            task_out[split_name] = agg
        all_out[task] = task_out

    with open(os.path.join(OUT, "gdet_v2_results.json"), "w") as f:
        json.dump(all_out, f, indent=2)
    per_row = pd.concat(row_frames, ignore_index=True)
    per_row.to_csv(os.path.join(OUT, "gdet_v2_per_row_scores.csv"), index=False)
    pd.DataFrame(thr_rows_all).to_csv(os.path.join(OUT, "gdet_v2_thresholds.csv"), index=False)

    outputs = [os.path.join(OUT, p) for p in
               ["gdet_v2_results.json", "gdet_v2_per_row_scores.csv", "gdet_v2_thresholds.csv"]]
    write_manifest(OUT, dict(protocol="threshold_protocol_v2", seeds=SEEDS,
                             tasks=["primary", "secondary"],
                             splits=["leave_family_out", "random_split"]),
                   outputs, started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[gdet_v2] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
