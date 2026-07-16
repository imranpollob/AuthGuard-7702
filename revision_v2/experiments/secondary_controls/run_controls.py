#!/usr/bin/env python3
"""Phase 2D — secondary controls at frozen v2 operating thresholds.

Trains each learned method on the FULL task-aligned primary population (mal vs benign_cleared),
selects the operating threshold by inner family-grouped OOF (protocol v2) BEFORE scoring any
control, freezes it, then scores the held-out task-aligned benign_general (797) and benign_AA
(5) rows. benign_general: FPR, score distribution (median/p90/p95/p99), alerts per 1,000,
family-weighted FPR, highest-scoring cases. benign_AA: five cases individually.
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
                     oof_threshold, write_manifest, verify_frozen_or_die, RV2, DH, SEED)

OUT = os.path.join(RV2, "results", "secondary_controls")


def wilson(k, n, z=1.96):
    if n == 0:
        return [float("nan"), float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(p), float(max(0, c - hw)), float(min(1, c + hw))]


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    methods = default_methods(views, views["n_dense"])

    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    Xtr = np.hstack([Xds, Xns]).astype(np.float32)
    groups = sub["family_id"].to_numpy()

    Xall = np.hstack([Xd, Xn]).astype(np.float32)
    bg = df[df["class"] == "benign_general"].reset_index()
    aa = df[df["class"] == "benign_AA"].reset_index()
    Xbg = Xall[bg["index"].to_numpy()]
    Xaa = Xall[aa["index"].to_numpy()]

    frozen_models, frozen_thr = {}, {}
    for mname, method in methods.items():
        thr, splitter, _ = oof_threshold(method, Xtr, y, groups, SEED)
        model = method["fit"](Xtr, y, SEED)
        frozen_models[mname] = (method, model)
        frozen_thr[mname] = thr

    bg_out, aa_rows, bg_top = {}, [], {}
    for mname, (method, model) in frozen_models.items():
        thr = frozen_thr[mname]
        s = method["score"](model, Xbg)
        flagged = int((s >= thr).sum())
        n = len(s)
        fam_fpr = (pd.DataFrame({"fam": bg["family_id"].to_numpy(), "flag": (s >= thr)})
                   .groupby("fam")["flag"].mean().mean())
        bg_out[mname] = dict(
            threshold=float(thr), n=n, flagged=flagged,
            FPR=flagged / n, FPR_wilson95=wilson(flagged, n),
            alerts_per_1000=1000.0 * flagged / n,
            family_macro_FPR=float(fam_fpr),
            score_median=float(np.median(s)), score_p90=float(np.percentile(s, 90)),
            score_p95=float(np.percentile(s, 95)), score_p99=float(np.percentile(s, 99)),
            score_max=float(s.max()))
        order = np.argsort(-s)[:10]
        bg_top[mname] = [dict(sid=bg["sid"].iloc[int(i)], family_id=bg["family_id"].iloc[int(i)],
                              score=float(s[int(i)]), flagged=bool(s[int(i)] >= thr))
                         for i in order]
        saa = method["score"](model, Xaa)
        for j in range(len(aa)):
            aa_rows.append(dict(model=mname, sid=aa["sid"].iloc[j],
                                family_id=aa["family_id"].iloc[j], score=float(saa[j]),
                                threshold=float(thr), flagged=bool(saa[j] >= thr)))

    payload = dict(
        note="Thresholds selected by inner family-grouped OOF on the primary population and "
             "frozen BEFORE scoring controls. benign_AA (n=5) reported as case observations only.",
        thresholds=frozen_thr, benign_general=bg_out,
        benign_general_top10=bg_top, benign_AA_cases=aa_rows,
        benign_general_n=int(len(bg)), benign_AA_n=int(len(aa)))
    with open(os.path.join(OUT, "secondary_controls.json"), "w") as f:
        json.dump(payload, f, indent=2)
    pd.DataFrame(aa_rows).to_csv(os.path.join(OUT, "benign_AA_cases.csv"), index=False)

    outputs = [os.path.join(OUT, "secondary_controls.json"),
               os.path.join(OUT, "benign_AA_cases.csv")]
    write_manifest(OUT, dict(protocol="threshold_protocol_v2 frozen thresholds"),
                   outputs, started, inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print("AuthGuard benign_general:", bg_out["authguard"]["flagged"], "/",
          bg_out["authguard"]["n"], f"FPR={bg_out['authguard']['FPR']:.4f}")
    print(f"[controls] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
