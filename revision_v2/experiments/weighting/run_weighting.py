#!/usr/bin/env python3
"""Phase 3D — weighting sensitivity on pooled G-DET v2 per-row test scores.

Post-hoc reweighting of the frozen AuthGuard seed-7702 pooled test predictions (each primary
row appears once under leave-family-out). Reports, for AuthGuard and the strongest baseline:
observation-weighted, inverse-family-size-weighted, one-vote-per-exact-bytecode
(duplicate-collapsed), family-macro recall, family-macro FPR, and family-clustered pooled
metrics. AUPRC is computed pooled/weighted or via family bootstrap — never averaged across
tiny per-family AUPRCs.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import load_corpus, RV2, SEED  # noqa: E402

GDET = os.path.join(RV2, "results", "gdet_v2", "gdet_v2_per_row_scores.csv")
OUT = os.path.join(RV2, "results", "weighting")
BASELINES = ["opcode_xgb", "opcode_rf", "selector_model"]


def pooled(df, model):
    return df[(df["task"] == "primary") & (df["split"] == "family") &
              (df["model"] == model) & (df["seed"] == SEED)].drop_duplicates("sid")


def weighted_metrics(y, s, pred, w):
    w = np.asarray(w, float)
    P = (w * (y == 1)).sum(); N = (w * (y == 0)).sum()
    tp = (w * (pred == 1) * (y == 1)).sum(); fp = (w * (pred == 1) * (y == 0)).sum()
    rec = tp / P if P else float("nan"); fpr = fp / N if N else float("nan")
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    auprc = float(average_precision_score(y, s, sample_weight=w)) if len(set(y)) > 1 else float("nan")
    return dict(AUPRC=auprc, recall=float(rec), FPR=float(fpr), precision=float(prec))


def main():
    os.makedirs(OUT, exist_ok=True)
    df, _, _, _ = load_corpus()
    scores = pd.read_csv(GDET)
    res_json = json.load(open(os.path.join(RV2, "results", "gdet_v2", "gdet_v2_results.json")))
    strongest = max(BASELINES,
                    key=lambda m: res_json["primary"]["leave_family_out"][m]["mean"]["AUPRC"])

    # exact-bytecode hash per sid (for duplicate collapse / one-vote)
    hashmap = dict(zip(df["sid"], df["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())))

    out = {}
    for model in ["authguard", strongest]:
        d = pooled(scores, model).copy()
        y = d["y"].to_numpy(); s = d["score"].to_numpy(); pred = d["pred"].to_numpy()
        fam = d["family_id"].to_numpy()
        d["bchash"] = d["sid"].map(hashmap)

        fam_sizes = pd.Series(fam).value_counts().to_dict()
        w_obs = np.ones(len(d))
        w_invfam = np.array([1.0 / fam_sizes[f] for f in fam])

        # one-vote-per-exact-bytecode: collapse duplicates (mean score, majority label)
        collapsed = d.groupby("bchash").agg(y=("y", "max"), s=("score", "mean"),
                                            pred=("pred", "max")).reset_index()
        yc, sc, pc = collapsed["y"].to_numpy(), collapsed["s"].to_numpy(), collapsed["pred"].to_numpy()

        # family-macro recall / FPR
        dd = pd.DataFrame({"fam": fam, "y": y, "pred": pred})
        macro_rec = dd[dd.y == 1].groupby("fam").apply(
            lambda g: (g.pred == 1).mean()).mean()
        fam_with_neg = dd[dd.y == 0].groupby("fam")
        macro_fpr = fam_with_neg.apply(lambda g: (g.pred == 1).mean()).mean()

        # family-clustered pooled AUPRC bootstrap
        families = np.array(sorted(pd.unique(fam)))
        idx = {f: i for i, f in enumerate(families)}
        obs_fam = np.array([idx[f] for f in fam]); nf = len(families)
        rng = np.random.default_rng(int.from_bytes(
            hashlib.blake2b(f"{SEED}:{model}:weight".encode(), digest_size=8).digest(), "little"))
        boot = np.empty(2000)
        for b in range(2000):
            w = np.bincount(rng.integers(0, nf, nf), minlength=nf)[obs_fam]
            boot[b] = average_precision_score(y, s, sample_weight=w)

        out[model] = dict(
            observation_weighted=weighted_metrics(y, s, pred, w_obs),
            inverse_family_size_weighted=weighted_metrics(y, s, pred, w_invfam),
            one_vote_per_exact_bytecode=weighted_metrics(yc, sc, pc, np.ones(len(yc))),
            family_macro_recall=float(macro_rec), family_macro_FPR=float(macro_fpr),
            family_clustered_pooled_AUPRC=dict(
                point=float(average_precision_score(y, s)),
                CI95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]),
            n_obs=int(len(d)), n_unique_bytecode=int(collapsed.shape[0]))
    payload = dict(strongest_baseline=strongest,
                   note="AUPRC computed pooled/weighted or via family bootstrap; never averaged "
                        "across per-family AUPRCs.", models=out)
    with open(os.path.join(OUT, "weighting_sensitivity.json"), "w") as f:
        json.dump(payload, f, indent=2)
    for m, r in out.items():
        print(f"[{m}] obs AUPRC {r['observation_weighted']['AUPRC']:.3f} | "
              f"invfam {r['inverse_family_size_weighted']['AUPRC']:.3f} | "
              f"onevote {r['one_vote_per_exact_bytecode']['AUPRC']:.3f} | "
              f"macro-recall {r['family_macro_recall']:.3f} macro-FPR {r['family_macro_FPR']:.3f}")


if __name__ == "__main__":
    main()
