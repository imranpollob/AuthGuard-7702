#!/usr/bin/env python3
"""Phase 6B — operational analysis + calibration on pooled G-DET v2 test scores.

PR curve, recall-FPR curve, threshold table, alerts per 1,000, hypothetical prevalence
scenarios (0.1% / 1% / 5% — labeled hypothetical), and calibration (reliability, Brier, ECE)
with a family-disjoint Platt/isotonic fit evaluated on held-out families. Scores are NOT
presented as calibrated probabilities unless the calibration analysis supports it.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, precision_recall_curve, roc_curve

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2, SEED, verify_frozen_or_die, write_manifest  # noqa: E402

GDET = os.path.join(RV2, "results", "gdet_v2", "gdet_v2_per_row_scores.csv")
OUT = os.path.join(RV2, "results", "operational")


def pooled(df, model):
    return df[(df["task"] == "primary") & (df["split"] == "family") &
              (df["model"] == model) & (df["seed"] == SEED)].drop_duplicates("sid")


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if m.sum():
            e += (m.mean()) * abs(y[m].mean() - p[m].mean())
    return float(e)


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(GDET)
    d = pooled(df, "authguard")
    y, s, fam = d["y"].to_numpy(), d["score"].to_numpy(), d["family_id"].to_numpy()

    prec, rec, pr_thr = precision_recall_curve(y, s)
    fpr, tpr, roc_thr = roc_curve(y, s)
    prevalence = float(y.mean())

    # threshold table + alerts/1000 at a grid
    grid = np.quantile(s, np.linspace(0.5, 0.999, 12))
    thr_table = []
    for t in grid:
        pred = s >= t
        tp = int(((pred) & (y == 1)).sum()); fp = int(((pred) & (y == 0)).sum())
        fn = int((~pred & (y == 1)).sum()); tn = int((~pred & (y == 0)).sum())
        recall = tp / max(tp + fn, 1); fpr_v = fp / max(fp + tn, 1)
        thr_table.append(dict(threshold=float(t), recall=recall, FPR=fpr_v,
                              precision=tp / max(tp + fp, 1),
                              alerts_per_1000=1000.0 * pred.mean()))

    # hypothetical prevalence scenarios (PPV recomputed at fixed operating point)
    op = np.quantile(s, 0.9)  # illustrative operating point
    pred = s >= op
    tpr_op = ((pred) & (y == 1)).sum() / max((y == 1).sum(), 1)
    fpr_op = ((pred) & (y == 0)).sum() / max((y == 0).sum(), 1)
    scenarios = {}
    for pv in [0.001, 0.01, 0.05]:
        ppv = (tpr_op * pv) / (tpr_op * pv + fpr_op * (1 - pv)) if (tpr_op * pv + fpr_op * (1 - pv)) else 0.0
        scenarios[f"{pv:.3f}"] = dict(prevalence=pv, recall=float(tpr_op), FPR=float(fpr_op),
                                      PPV_hypothetical=float(ppv),
                                      alerts_per_1000=float(1000 * (tpr_op * pv + fpr_op * (1 - pv))))

    # calibration: family-disjoint split (odd/even family hash), fit on one, eval on other
    fam_hash = pd.Series(fam).map(lambda x: int.from_bytes(
        __import__("hashlib").blake2b(str(x).encode(), digest_size=4).digest(), "little") % 2)
    tr = fam_hash.to_numpy() == 0
    te = ~tr
    raw_brier = brier_score_loss(y[te], np.clip(s[te], 0, 1))
    platt = LogisticRegression().fit(s[tr].reshape(-1, 1), y[tr])
    p_platt = platt.predict_proba(s[te].reshape(-1, 1))[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip").fit(s[tr], y[tr])
    p_iso = iso.predict(s[te])
    calib = dict(
        raw=dict(brier=float(raw_brier), ece=ece(y[te], np.clip(s[te], 0, 1))),
        platt=dict(brier=float(brier_score_loss(y[te], p_platt)), ece=ece(y[te], p_platt)),
        isotonic=dict(brier=float(brier_score_loss(y[te], p_iso)), ece=ece(y[te], p_iso)),
        note="Calibration fit on one family-disjoint half, evaluated on the other. Raw scores "
             "are ranking scores; use calibrated probabilities only if Brier/ECE improve.")

    frac_pos, mean_pred = calibration_curve(y[te], np.clip(s[te], 0, 1), n_bins=10)
    payload = dict(prevalence=prevalence, n=int(len(d)),
                   pr_curve=dict(precision=prec.tolist()[::5], recall=rec.tolist()[::5]),
                   roc_curve=dict(fpr=fpr.tolist()[::5], tpr=tpr.tolist()[::5]),
                   threshold_table=thr_table, hypothetical_prevalence_scenarios=scenarios,
                   operating_point_quantile=0.9,
                   calibration=calib,
                   reliability=dict(mean_predicted=mean_pred.tolist(),
                                    fraction_positive=frac_pos.tolist()))
    with open(os.path.join(OUT, "operational.json"), "w") as f:
        json.dump(payload, f, indent=2)
    write_manifest(OUT, dict(protocol="family-disjoint operational and calibration analysis",
                             seed=SEED, prevalence_scenarios=[0.001, 0.01, 0.05]),
                   [os.path.join(OUT, "operational.json")], started, inputs=[GDET])
    verify_frozen_or_die()
    print("prevalence", round(prevalence, 3), "| calib raw ECE", round(calib["raw"]["ece"], 3),
          "platt", round(calib["platt"]["ece"], 3), "iso", round(calib["isotonic"]["ece"], 3))


if __name__ == "__main__":
    main()
