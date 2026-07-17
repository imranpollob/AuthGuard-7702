#!/usr/bin/env python3
"""Family-clustered paired uncertainty for donor-isolated G-ADV v2.

Reads the completed G-ADV per-row output and applies uncertainty_protocol_v2.md to
AuthGuard-aug minus AuthGuard-M0 under the primary val-threshold arm (seed 7702).
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2, SEED, verify_frozen_or_die, write_manifest  # noqa: E402

GADV = os.path.join(RV2, "results", "gadv_v2")
OUT = os.path.join(RV2, "results", "uncertainty")
NBOOT = 10_000
CONDITIONS = ["M0", "M3", "F200", "M3F200"]


def weighted_metric(y, score, pred, weights, metric):
    y = np.asarray(y); score = np.asarray(score); pred = np.asarray(pred)
    weights = np.asarray(weights, dtype=float)
    if metric == "AUPRC":
        return float(average_precision_score(y, score, sample_weight=weights))
    if metric == "Recall":
        mask = y == 1
    elif metric == "FPR":
        mask = y == 0
    else:
        raise ValueError(metric)
    den = weights[mask].sum()
    if den == 0:
        return float("nan")
    return float((weights[mask] * (pred[mask] == 1)).sum() / den)


def prepare_auprc(y, score):
    """Pre-sort once; group equal scores to match sklearn's threshold/tie semantics."""
    order = np.argsort(-np.asarray(score), kind="mergesort")
    sorted_score = np.asarray(score)[order]
    group_ends = np.flatnonzero(np.r_[sorted_score[1:] != sorted_score[:-1], True])
    return order, group_ends, np.asarray(y)[order]


def weighted_auprc(prepared, weights):
    order, group_ends, sorted_y = prepared
    w = np.asarray(weights, dtype=float)[order]
    pos = w * sorted_y
    total_pos = pos.sum()
    if total_pos == 0:
        return 0.0
    cum_pos = np.cumsum(pos)[group_ends]
    cum_all = np.cumsum(w)[group_ends]
    group_pos = np.diff(np.r_[0.0, cum_pos])
    return float(np.sum((cum_pos / np.maximum(cum_all, 1e-15)) * group_pos) / total_pos)


def paired_bootstrap(a, b, condition, metric):
    """Return aug-minus-M0 point estimate and percentile CI, paired by family."""
    families = np.array(sorted(pd.unique(a["family_id"])))
    fam_index = {fam: i for i, fam in enumerate(families)}
    obs_family = np.array([fam_index[f] for f in a["family_id"]])
    seed = int.from_bytes(hashlib.blake2b(
        f"{SEED}:gadv_v2:{condition}:{metric}".encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(seed)
    ones = np.ones(len(a))
    point_a = weighted_metric(a.y, a.score, a.pred, ones, metric)
    point_b = weighted_metric(b.y, b.score, b.pred, ones, metric)
    prep_a = prepare_auprc(a.y, a.score) if metric == "AUPRC" else None
    prep_b = prepare_auprc(b.y, b.score) if metric == "AUPRC" else None
    delta = np.empty(NBOOT)
    for i in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(families), len(families)),
                             minlength=len(families))
        weights = counts[obs_family]
        if metric == "AUPRC":
            delta[i] = weighted_auprc(prep_a, weights) - weighted_auprc(prep_b, weights)
        else:
            delta[i] = (weighted_metric(a.y, a.score, a.pred, weights, metric) -
                        weighted_metric(b.y, b.score, b.pred, weights, metric))
    finite = delta[np.isfinite(delta)]
    ci = [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))]
    return dict(aug=point_a, M0=point_b, delta_point=point_a - point_b, delta_CI95=ci,
                excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                boot_mean=float(finite.mean()), boot_std=float(finite.std()),
                replicates=NBOOT, finite_replicates=int(len(finite)))


def main():
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    source = os.path.join(GADV, "gadv_v2_paired_results.csv.gz")
    df = pd.read_csv(source)
    df = df[(df.arm == "val_threshold") & (df.seed == SEED)]
    payload = dict(
        method="paired family-clustered percentile bootstrap; frozen test families sampled "
               "with replacement; primary val-threshold arm; seed 7702",
        results={})
    for condition in CONDITIONS:
        aug = df[(df.condition == condition) & (df.model == "AuthGuard-aug")]
        m0 = df[(df.condition == condition) & (df.model == "AuthGuard-M0")]
        aug = aug.drop_duplicates("sid").set_index("sid").sort_index()
        m0 = m0.drop_duplicates("sid").set_index("sid").loc[aug.index]
        assert len(aug) == len(m0) and (aug.y.to_numpy() == m0.y.to_numpy()).all()
        assert (aug.family_id.to_numpy() == m0.family_id.to_numpy()).all()
        payload["results"][condition] = {}
        for metric in ["Recall", "FPR", "AUPRC"]:
            payload["results"][condition][metric] = paired_bootstrap(
                aug.reset_index(), m0.reset_index(), condition, metric)
    out = os.path.join(OUT, "gadv_v2_bootstrap.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    write_manifest(OUT, dict(protocol="uncertainty_protocol_v2", experiment="gadv_v2",
                             arm="val_threshold", seed=SEED, replicates=NBOOT),
                   [out], started, inputs=[source])
    verify_frozen_or_die()
    print(json.dumps(payload["results"], indent=1)[:4000])


if __name__ == "__main__":
    main()
