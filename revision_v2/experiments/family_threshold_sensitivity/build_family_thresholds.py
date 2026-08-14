#!/usr/bin/env python3
"""Steps 0-4 of the family-threshold sensitivity analysis: rebuild the family
construction at theta in {0.80, 0.85, 0.90}, reproduce the frozen 0.85 assignment
exactly, rebuild valid family-disjoint splits, and characterise residual similarity.

Nothing here is re-invented. The clustering is the frozen pipeline's own code path
(`pipeline/01_freeze_families.py` -> `ag_common.minhash_signature` + union-find), and the
fold construction is the frozen task-alignment code path
(`paper_build/data_hygiene/task_alignment.py::original_fold_map`, GroupKFold(5) over the
original capability corpus grouped by family_id). Only the similarity threshold changes.

Writes to revision_v2/results/family_threshold_sensitivity/ only. Reads everything else
read-only. Exits non-zero if the theta=0.85 reproduction check fails, which is the
STOP condition before any retraining.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "family_threshold_sensitivity")

sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from ag_common import (SEED, disasm, minhash_signature,  # noqa: E402
                       normalize_bytecode, opcode_kgrams)

CAPABILITY = os.path.join(ROOT, "capability_dataset.csv")
FROZEN_FAMILIES = os.path.join(ROOT, "family_assignment_frozen.csv")
TASK_ALIGNED = os.path.join(ROOT, "paper_build", "data_hygiene",
                            "task_aligned_dataset_v1.csv")
DESIGNATOR_AUDIT = os.path.join(ROOT, "paper_build", "data_hygiene",
                                "designator_audit.csv")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

NUM_PERM = 128            # pipeline/01_freeze_families.py
KGRAM = 4
THETAS = [0.80, 0.85, 0.90]
REFERENCE_THETA = 0.85
PRIMARY_CLASSES = ["malicious", "benign_cleared"]
SECONDARY_CLASSES = ["malicious", "benign_cleared", "benign_general"]


# --------------------------------------------------------------------------- clustering
class UF:
    """Verbatim behaviour of pipeline/01_freeze_families.py::UF."""

    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def cluster(sigs, threshold):
    """Verbatim behaviour of pipeline/01_freeze_families.py::cluster."""
    n = sigs.shape[0]
    uf = UF(n)
    for i in range(n):
        if i + 1 >= n:
            break
        eq = (sigs[i + 1:] == sigs[i]).mean(axis=1)
        js = np.nonzero(eq >= threshold)[0] + (i + 1)
        for j in js:
            uf.union(i, int(j))
    return np.array([uf.find(i) for i in range(n)])


def relabel(roots, prefix="F"):
    """Verbatim behaviour of pipeline/01_freeze_families.py::relabel."""
    order, out = {}, []
    for r in roots:
        if r not in order:
            order[r] = len(order) + 1
        out.append(f"{prefix}{order[r]:05d}")
    return out


def signatures(frame, cache_path):
    if os.path.exists(cache_path):
        sigs = np.load(cache_path)["sigs"]
        if sigs.shape == (len(frame), NUM_PERM):
            print(f"[fam] reusing signature cache {os.path.basename(cache_path)}")
            return sigs
    sigs = np.empty((len(frame), NUM_PERM), dtype=np.uint64)
    for idx, bc in enumerate(frame["bc"].values):
        ops, _, _ = disasm(bc)
        sigs[idx] = minhash_signature(ops, num_perm=NUM_PERM, k=KGRAM)
        if idx % 500 == 0:
            print(f"  sig {idx}/{len(frame)}", flush=True)
    np.savez_compressed(cache_path, sigs=sigs)
    return sigs


# ------------------------------------------------------------------------------- folds
def original_fold_map(df, classes):
    """Verbatim behaviour of task_alignment.py::original_fold_map, over whatever
    family column has been installed as `family_id`."""
    sub = df[df["class"].isin(classes)].reset_index(drop=True)
    y = (sub["class"] == "malicious").astype(int).to_numpy()
    groups = sub["family_id"].to_numpy()
    out = {}
    for fold, (_, test) in enumerate(GroupKFold(5).split(sub, y, groups)):
        for family in np.unique(groups[test]):
            if family in out and out[family] != fold:
                raise AssertionError("family assigned to multiple outer folds")
            out[family] = fold
    return out


# ------------------------------------------------------------------------------- stats
def family_stats(sizes):
    sizes = np.asarray(sorted(sizes, reverse=True))
    n_fam = len(sizes)
    singles = int((sizes == 1).sum())
    return dict(
        n_families=n_fam,
        singleton_families=singles,
        singleton_pct=round(100 * singles / n_fam, 2) if n_fam else None,
        multi_member_families=int((sizes > 1).sum()),
        median_family_size=float(np.median(sizes)),
        mean_family_size=float(sizes.mean()),
        max_family_size=int(sizes.max()),
        top10_family_sizes=[int(v) for v in sizes[:10]],
        observations=int(sizes.sum()))


def merge_analysis(coarse, fine, frame):
    """How families combine when moving from the finer (higher theta) partition to the
    coarser (lower theta) one. `coarse`/`fine` are family-id series aligned to `frame`."""
    tab = pd.DataFrame({"coarse": coarse, "fine": fine})
    grouped = tab.groupby("coarse")["fine"].nunique()
    merged = grouped[grouped > 1]
    affected = tab[tab.coarse.isin(merged.index)]
    comp_sizes = affected.groupby("coarse").size().sort_values(ascending=False)
    return dict(
        coarse_families_absorbing_multiple_fine=int(len(merged)),
        fine_families_involved=int(grouped[grouped > 1].sum()),
        observations_affected=int(len(affected)),
        largest_merged_component_observations=int(comp_sizes.iloc[0]) if len(comp_sizes) else 0,
        largest_merged_component_fine_families=int(
            merged.max()) if len(merged) else 0,
        top10_merged_component_sizes=[int(v) for v in comp_sizes.head(10)])


# ------------------------------------------------------------------- residual similarity
def exact_jaccard_matrix(gram_sets_a, gram_sets_b):
    """Exact Jaccard of every a against every b. Used for the residual-similarity
    analysis only; family construction uses the pipeline's MinHash estimate."""
    out = np.zeros((len(gram_sets_a), len(gram_sets_b)), dtype=np.float32)
    for i, a in enumerate(gram_sets_a):
        if not a:
            continue
        for j, b in enumerate(gram_sets_b):
            if not b:
                continue
            inter = len(a & b)
            if inter:
                out[i, j] = inter / (len(a) + len(b) - inter)
    return out


def minhash_similarity(sig_a, sig_b_matrix):
    return (sig_b_matrix == sig_a).mean(axis=1)


def similarity_bands(values):
    v = np.asarray(values, dtype=float)
    n = len(v)
    def pct(mask):
        return round(100 * float(mask.sum()) / n, 2) if n else None
    return dict(
        n_test_observations=int(n),
        median=float(np.median(v)) if n else None,
        p90=float(np.percentile(v, 90)) if n else None,
        p95=float(np.percentile(v, 95)) if n else None,
        maximum=float(v.max()) if n else None,
        n_above_0_90=int((v > 0.90).sum()), pct_above_0_90=pct(v > 0.90),
        band_gt_090=int((v > 0.90).sum()),
        band_085_090=int(((v >= 0.85) & (v <= 0.90)).sum()),
        band_080_085=int(((v >= 0.80) & (v < 0.85)).sum()),
        band_070_080=int(((v >= 0.70) & (v < 0.80)).sum()),
        band_lt_070=int((v < 0.70).sum()))


# -------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-similarity", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    report = {}

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()

    # ---------------------------------------------------------------- load + signatures
    cap = pd.read_csv(CAPABILITY)
    cap["bc"] = cap["bytecode"].map(normalize_bytecode)
    frozen = pd.read_csv(FROZEN_FAMILIES)
    if len(frozen) != len(cap):
        raise SystemExit("frozen family file is not row-aligned with capability_dataset")
    if not (frozen["address"].to_numpy() == cap["address"].to_numpy()).all():
        raise SystemExit("frozen family file row order differs from capability_dataset")
    print(f"[fam] capability corpus: {len(cap)} rows")

    sigs = signatures(cap, os.path.join(OUT, "minhash_signatures_cache.npz"))

    # -------------------------------------------------- STEP 1: reproduce theta = 0.85
    # Reproduce every stored threshold, not only the reference, as a pipeline check.
    stored_cols = {0.75: "family_id_075", 0.85: "family_id_085", 0.90: "family_id_090"}
    reproduction = []
    recomputed = {}
    for theta in sorted(set(list(stored_cols) + THETAS)):
        roots = cluster(sigs, theta)
        labels = relabel(roots)
        recomputed[theta] = labels
        row = dict(theta=theta, n_families_recomputed=len(set(labels)))
        col = stored_cols.get(theta)
        if col and col in frozen.columns:
            stored = frozen[col].to_numpy()
            identical = bool((np.asarray(labels) == stored).all())
            same_partition = _same_partition(labels, stored)
            row.update(stored_column=col,
                       n_families_stored=int(pd.unique(stored).size),
                       family_ids_identical=identical,
                       partition_identical=same_partition,
                       n_rows_with_different_id=int(
                           (np.asarray(labels) != stored).sum()))
        else:
            row.update(stored_column=None, n_families_stored=None,
                       family_ids_identical=None, partition_identical=None,
                       n_rows_with_different_id=None)
        reproduction.append(row)
        print(f"[fam] theta={theta}: {row}")

    ref = [r for r in reproduction if r["theta"] == REFERENCE_THETA][0]
    if not ref["family_ids_identical"]:
        pd.DataFrame(reproduction).to_csv(
            os.path.join(OUT, "family_threshold_reproduction_FAILED.csv"), index=False)
        raise SystemExit(
            "STOP: theta=0.85 does not reproduce the frozen family assignment.\n"
            f"  stored families  : {ref['n_families_stored']}\n"
            f"  recomputed       : {ref['n_families_recomputed']}\n"
            f"  rows differing   : {ref['n_rows_with_different_id']}\n"
            "  affected: pipeline/01_freeze_families.py, pipeline/ag_common.py, "
            "family_assignment_frozen.csv")
    report["reproduction"] = reproduction

    # ------------------------------------------- family-dependence of the retained rows
    # The designator-recovery decision in task_alignment.py consults family membership.
    # Verify that the retained row set is invariant to theta before reusing the benchmark.
    designator = pd.read_csv(DESIGNATOR_AUDIT)
    cap_hash = cap["bc"].map(lambda h: hashlib.sha256(h.encode()).hexdigest())
    dependence = []
    for theta in THETAS:
        fam = pd.Series(recomputed[theta], index=cap.index)
        flips = 0
        for _, drow in designator.iterrows():
            raw = drow.get("recovered_runtime_sha256")
            # Unresolved rows store an empty hash (NaN once read back); their decision is
            # "no verified runtime" and consults no family information at all.
            chosen = "" if pd.isna(raw) else str(raw)
            if not chosen:
                continue
            i = int(drow["original_index"])
            elsewhere = fam[cap_hash == chosen]
            others = sorted(set(elsewhere) - {fam.iloc[i]})
            decision = ("replace_and_retain_candidate" if not others
                        else "exclude_recovered_cross_family_exact_duplicate")
            if decision != drow["task_alignment_decision"]:
                flips += 1
        dependence.append(dict(theta=theta, designator_decisions_changed=flips))
        print(f"[fam] theta={theta}: designator decisions changed = {flips}")
    report["retained_row_set_dependence"] = dependence
    if any(d["designator_decisions_changed"] for d in dependence):
        raise SystemExit(
            "STOP: changing theta changes the designator-recovery retention decisions, so "
            "the evaluated row population is not invariant to the family threshold. "
            "Report and stop rather than silently evaluating different populations.")

    # ------------------------------------------------- STEP 2/3: families, folds, splits
    bench = pd.read_csv(BENCH)
    primary_mask = bench["population"] == "PRIMARY_EVALUATION"
    print(f"[fam] benchmark primary rows: {int(primary_mask.sum())}")

    cap_key = (cap["chain"].astype(str) + ":" + cap["address"].astype(str)).to_numpy()
    if pd.Series(cap_key).duplicated().any():
        raise SystemExit("capability corpus has duplicate chain:address keys")

    family_rows, split_rows, similarity_rows = [], [], []
    manifests = {}
    grams_cache = {}

    for theta in THETAS:
        tag = f"theta{int(round(theta * 100)):03d}"
        fam_labels = recomputed[theta]
        cap_theta = cap.copy()
        cap_theta["family_id"] = fam_labels

        # family manifest over the full capability corpus (the clustering population)
        manifest = pd.DataFrame({
            "address": cap["address"], "chain": cap["chain"], "class": cap["class"],
            "sample_id": cap_key, "family_id": fam_labels})
        manifest.to_csv(os.path.join(OUT, f"family_manifest_{tag}.csv"), index=False)

        # folds: identical methodology, recomputed because the grouping changed
        primary_folds = original_fold_map(cap_theta, PRIMARY_CLASSES)
        secondary_folds = original_fold_map(cap_theta, SECONDARY_CLASSES)

        key_to_family = dict(zip(cap_key, fam_labels))
        b = bench.copy()
        b["family_id_theta"] = b["sample_id"].map(key_to_family)
        b["fold_id_theta"] = b["family_id_theta"].map(primary_folds)
        b["outer_fold_secondary_theta"] = b["family_id_theta"].map(secondary_folds)

        prim = b[primary_mask].copy()
        if prim["family_id_theta"].isna().any():
            raise SystemExit(f"{tag}: benchmark rows without a recomputed family")
        if prim["fold_id_theta"].isna().any():
            raise SystemExit(f"{tag}: benchmark primary rows without a fold assignment")
        prim["fold_id_theta"] = prim["fold_id_theta"].astype(int)

        sizes = prim.groupby("family_id_theta").size()
        stats = family_stats(sizes.to_numpy())
        pos = prim.groupby("family_id_theta")["label"].mean()
        stats.update(
            theta=theta, tag=tag,
            source_flagged=int(prim["label"].sum()),
            unflagged=int((prim["label"] == 0).sum()),
            families_all_positive=int((pos == 1).sum()),
            families_all_negative=int((pos == 0).sum()),
            families_mixed=int(((pos > 0) & (pos < 1)).sum()),
            exact_duplicate_groups=int(prim["bytecode_sha256"].nunique()),
            exact_dup_groups_spanning_families=int(
                prim.groupby("bytecode_sha256")["family_id_theta"].nunique().gt(1).sum()),
            exact_dup_groups_spanning_folds=int(
                prim.groupby("bytecode_sha256")["fold_id_theta"].nunique().gt(1).sum()),
            families_spanning_folds=int(
                prim.groupby("family_id_theta")["fold_id_theta"].nunique().gt(1).sum()))
        family_rows.append(stats)

        # split manifest + programmatic disjointness verification
        b[["sample_id", "population", "label", "family_id", "fold_id",
           "family_id_theta", "fold_id_theta", "outer_fold_secondary_theta"]].to_csv(
            os.path.join(OUT, f"split_manifest_{tag}.csv"), index=False)
        manifests[tag] = prim

        for fold in sorted(prim["fold_id_theta"].unique()):
            test = prim[prim["fold_id_theta"] == fold]
            train = prim[prim["fold_id_theta"] != fold]
            # The inner validation split is drawn from train by the training scripts
            # (StratifiedGroupKFold over families); recorded here as the train pool.
            tf, sf = set(train["family_id_theta"]), set(test["family_id_theta"])
            th, sh = set(train["bytecode_sha256"]), set(test["bytecode_sha256"])
            split_rows.append(dict(
                theta=theta, tag=tag, fold=int(fold),
                train_observations=int(len(train)), test_observations=int(len(test)),
                train_families=len(tf), test_families=len(sf),
                train_source_flagged_prevalence=float(train["label"].mean()),
                test_source_flagged_prevalence=float(test["label"].mean()),
                train_test_family_overlap=len(tf & sf),
                train_test_exact_hash_overlap=len(th & sh),
                family_disjoint=bool(not (tf & sf)),
                exact_hash_disjoint=bool(not (th & sh))))

        # ------------------------------------- STEP 4: residual train/test similarity
        if not args.skip_similarity:
            idx = {k: i for i, k in enumerate(cap_key)}
            rows = prim["sample_id"].map(idx).to_numpy()
            if np.isnan(rows.astype(float)).any():
                raise SystemExit(f"{tag}: benchmark sample_id missing from capability corpus")
            sub_sigs = sigs[rows]
            folds_arr = prim["fold_id_theta"].to_numpy()
            best = np.empty(len(prim), dtype=float)
            for fold in np.unique(folds_arr):
                te = np.flatnonzero(folds_arr == fold)
                tr = np.flatnonzero(folds_arr != fold)
                tr_sigs = sub_sigs[tr]
                for local, row_idx in enumerate(te):
                    best[row_idx] = minhash_similarity(sub_sigs[row_idx], tr_sigs).max()
            prim = prim.assign(max_sim_to_train=best)
            manifests[tag] = prim
            band = similarity_bands(best)
            band.update(theta=theta, tag=tag,
                        n_above_theta=int((best >= theta).sum()),
                        pct_above_theta=round(100 * float((best >= theta).sum()) / len(best), 2))
            similarity_rows.append(band)
            prim[["sample_id", "label", "family_id_theta", "fold_id_theta",
                  "max_sim_to_train"]].to_csv(
                os.path.join(OUT, f"residual_similarity_{tag}.csv"), index=False)
            print(f"[fam] {tag}: median nearest-train sim {band['median']:.4f}, "
                  f">0.90 = {band['n_above_0_90']}")

    fam_df = pd.DataFrame(family_rows)
    fam_df.to_csv(os.path.join(OUT, "family_threshold_family_stats.csv"), index=False)
    split_df = pd.DataFrame(split_rows)
    split_df.to_csv(os.path.join(OUT, "family_threshold_split_stats.csv"), index=False)
    if similarity_rows:
        pd.DataFrame(similarity_rows).to_csv(
            os.path.join(OUT, "family_threshold_similarity_stats.csv"), index=False)

    if not split_df.family_disjoint.all():
        raise SystemExit("STOP: family leakage detected in a rebuilt split")
    if not split_df.exact_hash_disjoint.all():
        raise SystemExit("STOP: exact-bytecode leakage detected in a rebuilt split")

    # -------------------------------------------------- how the partition changes
    prim_keys = bench.loc[primary_mask, "sample_id"].to_numpy()
    key_fam = {theta: dict(zip(cap_key, recomputed[theta])) for theta in THETAS}
    prim_fam = {theta: pd.Series([key_fam[theta][k] for k in prim_keys])
                for theta in THETAS}
    merges = {
        "0.90_to_0.85": merge_analysis(prim_fam[0.85], prim_fam[0.90], None),
        "0.85_to_0.80": merge_analysis(prim_fam[0.80], prim_fam[0.85], None)}
    report["merge_analysis"] = merges
    for name, m in merges.items():
        print(f"[fam] {name}: {m['coarse_families_absorbing_multiple_fine']} merges, "
              f"{m['observations_affected']} observations, largest component "
              f"{m['largest_merged_component_observations']} obs")

    giant = {theta: int(fam_df.loc[fam_df.theta == theta, "max_family_size"].iloc[0])
             for theta in THETAS}
    n_primary = int(primary_mask.sum())
    report["giant_component_check"] = {
        str(t): dict(max_family_size=giant[t],
                     pct_of_primary=round(100 * giant[t] / n_primary, 2),
                     flagged=bool(giant[t] > 0.10 * n_primary)) for t in THETAS}

    summary = dict(
        step="family_threshold_sensitivity: family construction, splits, similarity",
        git_commit=commit,
        capability_rows=int(len(cap)), benchmark_primary_rows=n_primary,
        minhash=dict(num_perm=NUM_PERM, kgram=KGRAM, hash="blake2b digest_size=8",
                     permutation="xor of gram hash with per-permutation blake2b seed",
                     seed=SEED, similarity="fraction of equal signature positions",
                     comparison=">= threshold", clustering="union-find, transitive closure",
                     root_rule="root = smaller index"),
        fold_procedure=dict(
            algorithm="GroupKFold(5) over the original capability corpus restricted to "
                      "the task classes, grouped by family_id",
            shuffle=False, random_state=None,
            source="paper_build/data_hygiene/task_alignment.py::original_fold_map"),
        thetas=THETAS, reference_theta=REFERENCE_THETA,
        family_stats=family_rows, split_stats=split_rows,
        similarity_stats=similarity_rows, **report)
    with open(os.path.join(OUT, "family_threshold_structure.json"), "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    print("\n[fam] family structure")
    print(fam_df[["theta", "n_families", "singleton_families", "singleton_pct",
                  "median_family_size", "mean_family_size", "max_family_size",
                  "multi_member_families"]].to_string(index=False))
    print("\n[fam] splits: all family-disjoint =", bool(split_df.family_disjoint.all()),
          "| all exact-hash-disjoint =", bool(split_df.exact_hash_disjoint.all()))
    print(f"[fam] wrote {OUT}")
    return 0


def _same_partition(a, b):
    """True if two labelings induce the same partition, ignoring label names."""
    fa, fb = {}, {}
    for x, y in zip(a, b):
        if fa.setdefault(x, y) != y or fb.setdefault(y, x) != x:
            return False
    return True


if __name__ == "__main__":
    sys.exit(main())
