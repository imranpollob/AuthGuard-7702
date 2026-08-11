#!/usr/bin/env python3
"""Gate 0B — nearest-neighbour bytecode lookup as a baseline.

Index construction is deliberately independent of pipeline/01_freeze_families.py:
the frozen `family_id` was clustered GLOBALLY over every row including test, so
reusing it would leak. Here a fresh MinHash index is built from the training
folds only, once per outer fold.

Index parameters (documented separately from the frozen family clustering):
  - tokens: opcode 4-grams from a linear sweep, PUSHn collapsed to PUSH
  - MinHash: 256 permutations, blake2b-64 with an 8-byte little-endian salt
  - similarity: estimated Jaccard = fraction of agreeing signature positions
  - second view: L2-normalised opcode-histogram cosine similarity

Protocol matches run_baseline_v2.py: benchmark v2, PRIMARY_EVALUATION, stored
`fold_id`, seeds 7702/7703/7704, macro-over-folds aggregation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from ag_common import OPCODE_VOCAB, disasm  # noqa: E402

BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
SEQ_PREDS = os.path.join(RV2, "experiments", "baseline_v2", "baseline_predictions.csv.gz")
OUT = os.path.join(RV2, "results", "gate_0b_knn")
SEEDS = [7702, 7703, 7704]
NUM_PERM = 256
KGRAM = 4
KS = [1, 3, 5]
NBOOT = 2000
SIM_BINS = [(0.9, 1.01, ">0.9"), (0.7, 0.9, "0.7-0.9"), (0.5, 0.7, "0.5-0.7"), (-0.01, 0.5, "<0.5")]


def _h(data: bytes, seed: int) -> int:
    salt = seed.to_bytes(8, "little")
    return int.from_bytes(hashlib.blake2b(data, digest_size=8, salt=salt).digest(), "little")


def signature(ops, num_perm=NUM_PERM, k=KGRAM):
    if len(ops) < k:
        grams = {" ".join(ops)} if ops else {"<EMPTY>"}
    else:
        grams = {" ".join(ops[i : i + k]) for i in range(len(ops) - k + 1)}
    gh = np.array([_h(g.encode(), 0) for g in grams], dtype=np.uint64)
    sig = np.empty(num_perm, dtype=np.uint64)
    for i in range(num_perm):
        mixed = gh ^ np.uint64(_h(str(i).encode(), 1))
        sig[i] = mixed.min()
    return sig


def hist_matrix(all_ops):
    idx = {n: i for i, n in enumerate(OPCODE_VOCAB)}
    H = np.zeros((len(all_ops), len(OPCODE_VOCAB)), dtype=np.float32)
    for r, ops in enumerate(all_ops):
        for o in ops:
            j = idx.get(o)
            if j is not None:
                H[r, j] += 1.0
    n = np.linalg.norm(H, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return H / n


def knn_scores(sim, y_train, k):
    """Similarity-weighted malicious fraction over the k nearest training rows."""
    n_test = sim.shape[0]
    scores = np.zeros(n_test)
    maxsim = np.zeros(n_test)
    kk = min(k, sim.shape[1])
    for i in range(n_test):
        row = sim[i]
        top = np.argpartition(-row, kk - 1)[:kk]
        w = row[top]
        maxsim[i] = row[top].max() if kk else 0.0
        scores[i] = float((w * y_train[top]).sum() / w.sum()) if w.sum() > 0 else 0.0
    return scores, maxsim


def recall_at_fpr(y, s, target=0.05):
    fpr, tpr, thr = roc_curve(y, s)
    ok = np.flatnonzero(fpr <= target)
    if len(ok) == 0:
        return 0.0, 1.0
    return float(tpr[ok[-1]]), float(fpr[ok[-1]])


def main():
    os.makedirs(OUT, exist_ok=True)
    df = pd.read_csv(BENCH)
    p = df[df.population == "PRIMARY_EVALUATION"].reset_index(drop=True)
    y = p.label.to_numpy(dtype=int)
    folds = p.fold_id.to_numpy(dtype=int)
    fam = p.family_id.to_numpy()
    sid = p.sample_id.to_numpy()

    t0 = time.perf_counter()
    all_ops = [disasm(str(b)[2:] if str(b)[:2].lower() == "0x" else str(b))[0]
               for b in p.runtime_bytecode]
    sigs = np.stack([signature(o) for o in all_ops])
    index_build_wall = time.perf_counter() - t0
    H = hist_matrix(all_ops)

    fold_rows, per_row = [], []
    query_ms = []

    for f in sorted(np.unique(folds)):
        tr = np.flatnonzero(folds != f)
        te = np.flatnonzero(folds == f)
        # MinHash estimated Jaccard, test x train
        t = time.perf_counter()
        sim_mh = (sigs[te][:, None, :] == sigs[tr][None, :, :]).mean(axis=2)
        query_ms.append((time.perf_counter() - t) / len(te) * 1e3)
        sim_hist = H[te] @ H[tr].T

        for view, sim in (("minhash", sim_mh), ("opcode_hist_cos", sim_hist)):
            for k in KS:
                sc, maxsim = knn_scores(sim, y[tr], k)
                name = f"knn_{view}_k{k}"
                fold_rows.append(dict(
                    model=name, fold=int(f), n=len(te), prevalence=float(y[te].mean()),
                    auprc=float(average_precision_score(y[te], sc)),
                    auroc=float(roc_auc_score(y[te], sc)),
                ))
                for i, gi in enumerate(te):
                    per_row.append(dict(
                        sample_id=sid[gi], family_id=fam[gi], fold=int(f), model=name,
                        true_label=int(y[gi]), score=float(sc[i]), max_train_sim=float(maxsim[i]),
                    ))

    per_fold = pd.DataFrame(fold_rows)
    preds = pd.DataFrame(per_row)
    per_fold.to_csv(os.path.join(OUT, "gate_0b_per_fold.csv"), index=False)
    preds.to_csv(os.path.join(OUT, "gate_0b_predictions.csv.gz"), index=False)

    summary = {}
    for name, g in per_fold.groupby("model"):
        pr = preds[preds.model == name]
        r5, f5 = recall_at_fpr(pr.true_label.to_numpy(), pr.score.to_numpy())
        summary[name] = dict(
            auprc_macro=float(g.auprc.mean()), auroc_macro=float(g.auroc.mean()),
            auprc_pooled=float(average_precision_score(pr.true_label, pr.score)),
            recall_at_5fpr=r5, fpr_at_that_point=f5,
        )

    # ---- stratification by max similarity to the training fold ----
    best = max(summary, key=lambda m: summary[m]["auprc_macro"])
    strat = []
    for name in preds.model.unique():
        pr = preds[preds.model == name]
        for lo, hi, label in SIM_BINS:
            m = (pr.max_train_sim > lo) & (pr.max_train_sim <= hi)
            sub = pr[m]
            row = dict(model=name, sim_bin=label, n=int(len(sub)),
                       n_pos=int(sub.true_label.sum()),
                       prevalence=float(sub.true_label.mean()) if len(sub) else np.nan)
            row["auprc"] = (float(average_precision_score(sub.true_label, sub.score))
                            if len(sub) > 1 and sub.true_label.nunique() > 1 else np.nan)
            strat.append(row)
    strat_df = pd.DataFrame(strat)
    strat_df.to_csv(os.path.join(OUT, "gate_0b_similarity_strata.csv"), index=False)

    # ---- paired family-clustered bootstrap vs AuthGuard-Seq ----
    seq = pd.read_csv(SEQ_PREDS)
    seq = seq[seq.model == "authguard_seq"]
    fams = np.unique(fam)
    fam_idx = {f: i for i, f in enumerate(fams)}
    obs_fam = np.array([fam_idx[f] for f in fam])
    rng = np.random.default_rng(7702)

    def macro_auprc(s_all, w):
        vals = []
        for f in np.unique(folds):
            m = folds == f
            if w[m].sum() == 0 or len(np.unique(y[m][w[m] > 0])) < 2:
                continue
            vals.append(average_precision_score(y[m], s_all[m], sample_weight=w[m]))
        return float(np.mean(vals)) if vals else np.nan

    boot = {}
    for name in [best]:
        kn = p[["sample_id"]].merge(
            preds[preds.model == name][["sample_id", "score"]], on="sample_id")
        deltas = []
        for seed in SEEDS:
            sq = p[["sample_id"]].merge(
                seq[seq.seed == seed][["sample_id", "calibrated_score"]], on="sample_id")
            a_s, b_s = kn.score.to_numpy(), sq.calibrated_score.to_numpy()
            for _ in range(NBOOT // len(SEEDS)):
                w = rng.multinomial(len(fams), np.ones(len(fams)) / len(fams))[obs_fam]
                a, b = macro_auprc(a_s, w), macro_auprc(b_s, w)
                if not (np.isnan(a) or np.isnan(b)):
                    deltas.append(a - b)
        deltas = np.array(deltas)
        boot[name] = dict(
            mean_delta_auprc=float(deltas.mean()),
            ci95=[float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
            replicates=int(len(deltas)),
            excludes_zero=bool(np.percentile(deltas, 2.5) > 0 or np.percentile(deltas, 97.5) < 0),
        )

    out = dict(
        index_params=dict(num_perm=NUM_PERM, kgram=KGRAM, hash="blake2b-64 salted",
                          built_from="training folds only, rebuilt per outer fold"),
        n_rows=int(len(p)), n_families=int(len(fams)),
        summary=summary, best_model=best,
        paired_bootstrap_vs_authguard_seq=boot,
        latency=dict(index_build_all_rows_seconds=float(index_build_wall),
                     mean_query_ms_per_test_row=float(np.mean(query_ms)),
                     note="query = full test-vs-train signature comparison, no ANN structure"),
        similarity_strata=strat_df.to_dict("records"),
    )
    with open(os.path.join(OUT, "gate_0b_results.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
