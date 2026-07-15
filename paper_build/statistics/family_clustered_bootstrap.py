#!/usr/bin/env python3
"""Paired family-clustered bootstrap for AuthGuard-M0 vs AuthGuard-aug."""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "paper_build", "statistics")
NBOOT = 10_000
BASE_SEED = 7702
CONDITIONS = ["M0", "M3", "F200"]


def seed_for(cohort: str, condition: str) -> int:
    h = hashlib.blake2b(f"{BASE_SEED}:{cohort}:{condition}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "little")


def paired_frame(path: str, condition: str) -> pd.DataFrame:
    p = pd.read_csv(path)
    p = p[(p["condition"] == condition) &
          p["model"].isin(["AuthGuard-M0", "AuthGuard-aug"])].copy()
    keys = ["sample_id", "family_id", "fold", "true_label"]
    wide = p.pivot(index=keys, columns="model",
                   values=["predicted_label", "raw_score"]).reset_index()
    wide.columns = ["_".join(x).strip("_") if isinstance(x, tuple) else x for x in wide.columns]
    expected = len(p) // 2
    if len(wide) != expected:
        raise AssertionError("model pairing is incomplete")
    return wide


def metric_points(d: pd.DataFrame) -> dict:
    y = d["true_label"].to_numpy()
    out = {}
    for name in ["AuthGuard-M0", "AuthGuard-aug"]:
        pred = d[f"predicted_label_{name}"].to_numpy()
        score = d[f"raw_score_{name}"].to_numpy()
        out[name] = {
            "recall": float(pred[y == 1].mean()),
            "FPR": float(pred[y == 0].mean()),
            "AUPRC": float(average_precision_score(y, score)),
        }
    return out


def bootstrap(path: str, cohort: str, condition: str) -> dict:
    d = paired_frame(path, condition)
    families = np.array(sorted(d["family_id"].unique()))
    family_index = {f: i for i, f in enumerate(families)}
    obs_family = d["family_id"].map(family_index).to_numpy()
    n_families = len(families)
    y = d["true_label"].to_numpy()
    p0 = d["predicted_label_AuthGuard-M0"].to_numpy()
    pa = d["predicted_label_AuthGuard-aug"].to_numpy()
    s0 = d["raw_score_AuthGuard-M0"].to_numpy()
    sa = d["raw_score_AuthGuard-aug"].to_numpy()

    def fam_sums(values, label):
        mask = y == label
        return (np.bincount(obs_family[mask], weights=values[mask], minlength=n_families),
                np.bincount(obs_family[mask], minlength=n_families))

    mal0, maln = fam_sums(p0, 1); mala, _ = fam_sums(pa, 1)
    ben0, benn = fam_sums(p0, 0); bena, _ = fam_sums(pa, 0)

    rng = np.random.default_rng(seed_for(cohort, condition))
    recall_diff = np.empty(NBOOT); fpr_diff = np.empty(NBOOT)
    auprc_diff = np.empty(NBOOT) if condition == "F200" else None
    for b in range(NBOOT):
        sampled = rng.integers(0, n_families, size=n_families)
        counts = np.bincount(sampled, minlength=n_families)
        recall_diff[b] = ((counts @ mala) / (counts @ maln) -
                          (counts @ mal0) / (counts @ maln))
        fpr_diff[b] = ((counts @ bena) / (counts @ benn) -
                       (counts @ ben0) / (counts @ benn))
        if auprc_diff is not None:
            weights = counts[obs_family]
            auprc_diff[b] = (average_precision_score(y, sa, sample_weight=weights) -
                              average_precision_score(y, s0, sample_weight=weights))

    points = metric_points(d)
    result = {
        "cohort": cohort,
        "condition": condition,
        "seed": seed_for(cohort, condition),
        "bootstrap_replicates": NBOOT,
        "n_families": n_families,
        "n_contracts": len(d),
        "point": points,
        "recall_diff_aug_minus_M0": float(points["AuthGuard-aug"]["recall"] -
                                           points["AuthGuard-M0"]["recall"]),
        "recall_diff_CI95": [float(x) for x in np.percentile(recall_diff, [2.5, 97.5])],
        "FPR_diff_aug_minus_M0": float(points["AuthGuard-aug"]["FPR"] -
                                        points["AuthGuard-M0"]["FPR"]),
        "FPR_diff_CI95": [float(x) for x in np.percentile(fpr_diff, [2.5, 97.5])],
    }
    if auprc_diff is not None:
        result["AUPRC_diff_aug_minus_M0"] = float(
            points["AuthGuard-aug"]["AUPRC"] - points["AuthGuard-M0"]["AUPRC"])
        result["AUPRC_diff_CI95"] = [float(x) for x in np.percentile(auprc_diff, [2.5, 97.5])]
    return result


def fmt(x):
    return f"{x:.3f}"


def main():
    os.makedirs(OUT, exist_ok=True)
    cohorts = {
        "original": os.path.join(ROOT, "paired_results.csv"),
        "task_aligned_v1": os.path.join(ROOT, "paper_build", "data_hygiene",
                                         "task_aligned_paired_results.csv"),
    }
    results = {cohort: {cond: bootstrap(path, cohort, cond) for cond in CONDITIONS}
               for cohort, path in cohorts.items()}
    payload = {
        "method": "paired family-clustered percentile bootstrap; sample frozen test families "
                  "with replacement and retain every contract in each sampled family",
        "base_seed": BASE_SEED,
        "replicates": NBOOT,
        "results": results,
    }
    with open(os.path.join(OUT, "family_clustered_bootstrap.json"), "w") as f:
        json.dump(payload, f, indent=2)

    lines = [
        "# Family-Clustered Paired Bootstrap",
        "",
        f"Fixed base seed: {BASE_SEED}. Replicates per cohort/condition: {NBOOT:,}.",
        "",
        "Each replicate samples frozen test families with replacement, retains every contract in "
        "each sampled family, and preserves the AuthGuard-M0/AuthGuard-aug pairing. Intervals are "
        "percentile 95% intervals. Positive recall differences favor augmentation; negative FPR "
        "differences favor augmentation.",
        "",
    ]
    for cohort, cres in results.items():
        lines += [f"## {cohort}", "",
                  "| condition | pooled recall M0→aug | Δ recall [95% CI] | pooled FPR M0→aug | Δ FPR [95% CI] | Δ AUPRC [95% CI] | families |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for cond in CONDITIONS:
            r = cres[cond]; p = r["point"]
            ap = (f"{fmt(r['AUPRC_diff_aug_minus_M0'])} "
                  f"[{fmt(r['AUPRC_diff_CI95'][0])}, {fmt(r['AUPRC_diff_CI95'][1])}]"
                  if "AUPRC_diff_CI95" in r else "—")
            lines.append(
                f"| {cond} | {fmt(p['AuthGuard-M0']['recall'])}→{fmt(p['AuthGuard-aug']['recall'])} "
                f"| {fmt(r['recall_diff_aug_minus_M0'])} [{fmt(r['recall_diff_CI95'][0])}, {fmt(r['recall_diff_CI95'][1])}] "
                f"| {fmt(p['AuthGuard-M0']['FPR'])}→{fmt(p['AuthGuard-aug']['FPR'])} "
                f"| {fmt(r['FPR_diff_aug_minus_M0'])} [{fmt(r['FPR_diff_CI95'][0])}, {fmt(r['FPR_diff_CI95'][1])}] "
                f"| {ap} | {r['n_families']} |")
        lines += [""]
    lines += [
        "## Interpretation rule",
        "",
        "Use the task-aligned-v1 intervals for the revised paper numbers. The original cohort is "
        "retained only to reconcile the earlier contract-level bootstrap. Do not use the old "
        "contract-resampled interval as a submission headline.",
    ]
    with open(os.path.join(OUT, "family_clustered_bootstrap.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
