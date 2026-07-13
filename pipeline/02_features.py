#!/usr/bin/env python3
"""
02_features.py -- bulk bytecode-only feature extraction (delegates to ag_features.featurize).
Writes results/features_dense.npz, results/features_ngram.npz, results/feature_meta.json.
Banned features (chain, tautological caps, family_id, class) never enter the matrix.
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_features import featurize, build_sensitive_selector_set, NGRAM_DIM
from ag_common import SEED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
np.random.seed(SEED)


def main():
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    sens = build_sensitive_selector_set()
    print(f"[feat] sensitive selector set size: {len(sens)}", flush=True)
    X_dense, X_ngram, dense_cols = featurize(df["bytecode"].tolist(), sens=sens)

    banned = {"chain", "cap_value_receiving_hook", "cap_unrestricted_external_call",
              "family_id", "class"}
    assert not (set(dense_cols) & banned), "banned feature leaked!"

    np.savez_compressed(os.path.join(RES, "features_dense.npz"), X=X_dense)
    np.savez_compressed(os.path.join(RES, "features_ngram.npz"), X=X_ngram)
    hist_dim = sum(1 for c in dense_cols if c.startswith("op_"))
    meta = dict(dense_cols=dense_cols, ngram_dim=NGRAM_DIM, n_rows=len(df),
                n_dense=X_dense.shape[1], sensitive_selector_count=len(sens),
                hist_dim=hist_dim, struct_dim=len(dense_cols) - hist_dim,
                banned_features=sorted(banned))
    with open(os.path.join(RES, "feature_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[feat] X_dense {X_dense.shape}, X_ngram {X_ngram.shape}; "
          f"hist {hist_dim} + struct {len(dense_cols)-hist_dim}", flush=True)


if __name__ == "__main__":
    main()
