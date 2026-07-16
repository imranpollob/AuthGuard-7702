#!/usr/bin/env python3
"""Phase 2B — agreement/merge script (runs once human reviewers return blinded forms).

Ingests review_form_R*_COMPLETED.csv (same schema as the BLINDED forms, `label` filled),
computes pairwise Cohen's kappa, Fleiss' kappa, majority-vote adjudication, and disagreement
list. Does NOT alter the frozen sampling. If completed forms are absent it exits cleanly with
a pending notice so the pipeline is not blocked.
"""
import glob
import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2  # noqa: E402

OUT = os.path.join(RV2, "artifact", "label_audit")
LABELS = ["malicious", "benign", "uncertain"]


def cohen_kappa(a, b):
    cats = LABELS
    n = len(a)
    po = np.mean([x == y for x, y in zip(a, b)])
    pe = sum((np.mean([x == c for x in a])) * (np.mean([y == c for y in b])) for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def fleiss_kappa(mat):
    n, k = mat.shape
    N = mat.sum(axis=1)[0]
    p = mat.sum(axis=0) / (n * N)
    Pi = (( (mat ** 2).sum(axis=1) - N) / (N * (N - 1)))
    Pbar = Pi.mean()
    Pe = (p ** 2).sum()
    return float((Pbar - Pe) / (1 - Pe)) if Pe < 1 else 1.0


def main():
    forms = sorted(glob.glob(os.path.join(OUT, "review_form_R*_COMPLETED.csv")))
    if len(forms) < 2:
        msg = dict(status="pending_human_labels",
                   note="Provide review_form_R*_COMPLETED.csv (>=2) to compute agreement.",
                   found=len(forms))
        with open(os.path.join(OUT, "agreement_results.json"), "w") as f:
            json.dump(msg, f, indent=2)
        print(json.dumps(msg, indent=1))
        return

    dfs = {os.path.basename(p).split("_")[2]: pd.read_csv(p).set_index("anon_id")["label"]
           for p in forms}
    merged = pd.DataFrame(dfs)
    merged = merged[merged.notna().all(axis=1)]
    reviewers = list(dfs)

    pair = {}
    for a, b in itertools.combinations(reviewers, 2):
        pair[f"{a}-{b}"] = cohen_kappa(merged[a].tolist(), merged[b].tolist())

    counts = np.array([[ (merged.loc[i] == c).sum() for c in LABELS]
                       for i in merged.index])
    fk = fleiss_kappa(counts)

    def majority(row):
        vc = row.value_counts()
        return vc.index[0] if vc.iloc[0] > len(row) / 2 else "no_majority"
    adjudicated = merged.apply(majority, axis=1)
    disagreements = merged[adjudicated == "no_majority"]

    out = dict(reviewers=reviewers, n_items=int(len(merged)),
               pairwise_cohen_kappa=pair, fleiss_kappa=fk,
               majority_distribution=adjudicated.value_counts().to_dict(),
               n_disagreements=int((adjudicated == "no_majority").sum()))
    with open(os.path.join(OUT, "agreement_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    adjudicated.rename("majority_label").to_csv(
        os.path.join(OUT, "adjudicated_labels.csv"))
    disagreements.to_csv(os.path.join(OUT, "disagreements.csv"))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
