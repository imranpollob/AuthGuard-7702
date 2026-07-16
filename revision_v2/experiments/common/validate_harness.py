#!/usr/bin/env python3
"""Phase 0 go/no-go: the v2 harness must reproduce v1 per-fold AUPRCs exactly.

AUPRC is threshold-free, so with identical stored folds, features, and seed the harness's
fits must match the frozen task-aligned v1 detection results for authguard and opcode_xgb.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import (DH, RV2, load_corpus, task_arrays, feature_views,  # noqa: E402
                     default_methods, SEED)
import harness  # noqa: E402


def main():
    df, Xd, Xn, meta = load_corpus()
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    views = feature_views(meta)
    X = np.hstack([Xds, Xns]).astype(np.float32)
    methods = default_methods(views, views["n_dense"])

    frozen = json.load(open(os.path.join(DH, "task_aligned_detection_results.json")))
    ref = frozen["primary_mal_vs_cleared"]["leave_family_out"]

    report = {}
    ok = True
    for name in ["authguard", "opcode_xgb"]:
        got = []
        for f in range(5):
            tr, te = np.flatnonzero(folds != f), np.flatnonzero(folds == f)
            model = methods[name]["fit"](X[tr], y[tr], SEED)
            s = methods[name]["score"](model, X[te])
            from sklearn.metrics import average_precision_score
            got.append(float(average_precision_score(y[te], s)))
        want = [fold["AUPRC"] for fold in ref[name]["folds"]]
        diff = max(abs(a - b) for a, b in zip(got, want))
        report[name] = {"v2_harness": got, "v1_frozen": want, "max_abs_diff": diff}
        print(f"[validate] {name}: max |diff| = {diff:.2e}")
        if diff > 1e-6:
            ok = False
    out = os.path.join(RV2, "audits", "harness_validation.json")
    with open(out, "w") as f:
        json.dump({"pass": ok, "tolerance": 1e-6, "results": report}, f, indent=2)
    print(f"[validate] {'PASS' if ok else 'FAIL'} -> {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
