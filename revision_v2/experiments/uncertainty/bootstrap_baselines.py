#!/usr/bin/env python3
"""Paired family bootstrap: same-host AuthGuard full vs strongest Phase-3 bytecode baseline."""
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
from harness import RV2, SEED, verify_frozen_or_die, sha256_file  # noqa: E402

BASE = os.path.join(RV2, "results", "baselines")
ABL = os.path.join(RV2, "results", "ablations")
NBOOT = 10_000


def summary_mean(path, key):
    return json.load(open(path))[key]["mean"]["AUPRC"]


def main():
    started = time.time()
    verify_frozen_or_die()
    baseline_json = os.path.join(BASE, "baselines_results.json")
    ablation_json = os.path.join(ABL, "ablations_results.json")
    rows_path = os.path.join(BASE, "baselines_ablations_per_row.csv.gz")
    candidates = {
        "hash_xgb": summary_mean(baseline_json, "hash_xgb"),
        "tfidf_lr": summary_mean(baseline_json, "tfidf_lr"),
        "tfidf_svm": summary_mean(baseline_json, "tfidf_svm"),
        "abl_hist_only": summary_mean(ablation_json, "hist_only"),
        "abl_ngram_only": summary_mean(ablation_json, "ngram_only"),
        "abl_hist_struct": summary_mean(ablation_json, "hist_struct"),
        "abl_hist_ngram": summary_mean(ablation_json, "hist_ngram"),
    }
    strongest = max(candidates, key=candidates.get)
    df = pd.read_csv(rows_path)

    def scores(model):
        d = df[(df.model == model) & (df.seed == SEED) & (df.split == "family")]
        return d.drop_duplicates("sid").set_index("sid").sort_index()

    full = scores("abl_full_773")
    base = scores(strongest).loc[full.index]
    assert (full.y.to_numpy() == base.y.to_numpy()).all()
    assert (full.family_id.to_numpy() == base.family_id.to_numpy()).all()
    y = full.y.to_numpy(); fam = full.family_id.to_numpy()
    s_full = full.score.to_numpy(); s_base = base.score.to_numpy()
    families = np.array(sorted(pd.unique(fam)))
    fam_index = {f: i for i, f in enumerate(families)}
    obs_family = np.array([fam_index[f] for f in fam])
    rng_seed = int.from_bytes(hashlib.blake2b(
        f"{SEED}:phase3:{strongest}:minus_authguard".encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(rng_seed)
    delta = np.empty(NBOOT)
    for i in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(families), len(families)),
                             minlength=len(families))
        weights = counts[obs_family]
        delta[i] = (average_precision_score(y, s_full, sample_weight=weights) -
                    average_precision_score(y, s_base, sample_weight=weights))
    ci = [float(np.percentile(delta, 2.5)), float(np.percentile(delta, 97.5))]
    payload = dict(
        selection="highest seed-7702 five-fold mean AUPRC among Phase-3 same-host bytecode baselines",
        candidate_fold_mean_AUPRC=candidates, strongest_baseline=strongest,
        authguard_full_pooled_AUPRC=float(average_precision_score(y, s_full)),
        strongest_pooled_AUPRC=float(average_precision_score(y, s_base)),
        authguard_minus_strongest=dict(
            delta_point=float(average_precision_score(y, s_full) -
                              average_precision_score(y, s_base)),
            delta_CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
            boot_mean=float(delta.mean()), boot_std=float(delta.std()), replicates=NBOOT),
        platform_policy="Both models refit on the same Linux x86_64 host; no ARM/Linux mixing.")
    out = os.path.join(BASE, "paired_family_bootstrap.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    manifest = dict(command=" ".join(sys.argv), seed=SEED, replicates=NBOOT,
                    wall_seconds=round(time.time() - started, 1),
                    inputs={os.path.relpath(rows_path, os.path.dirname(RV2)): sha256_file(rows_path),
                            os.path.relpath(baseline_json, os.path.dirname(RV2)): sha256_file(baseline_json),
                            os.path.relpath(ablation_json, os.path.dirname(RV2)): sha256_file(ablation_json)},
                    outputs={os.path.relpath(out, os.path.dirname(RV2)): sha256_file(out)})
    with open(os.path.join(BASE, "bootstrap_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    verify_frozen_or_die()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
