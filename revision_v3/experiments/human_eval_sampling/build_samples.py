"""Phase 2, Part 7: Pilot / Gold-Dev / locked Gold-Test sampling.

Sampling unit is UNIQUE EXACT RUNTIME BYTECODE (bytecode_sha256), not address rows -- one
representative (chain, address) row per unique bytecode is carried forward for the evidence
packet, but selection, counts, and disjointness are all computed at the bytecode level.
family_id is retained (verified 1:1 with bytecode_sha256 in the primary population) for
isolation checks.

Construction order (to satisfy the disjointness requirements):
  1. Gold-Test (locked): population-proportional by source label (~50 positive / ~100
     unflagged out of 150), purely random within each stratum -- NEVER using model score --
     with a light per-family cap (max 3 unique bytecodes per family) for diversity. Frozen and
     hashed immediately after construction.
  2. Gold-Dev (60): excludes Gold-Test's families entirely (family-disjoint by construction).
     Deliberately oversamples four "informative" strata crossing source label with
     authguard_reference_v3's out-of-fold calibrated score (mean across the 3 Phase 1 seeds --
     this is exactly the kind of use the audit brief permits for Gold-Dev, and explicitly
     forbids for Gold-Test).
  3. Pilot (20): excludes exact bytecodes already used in Gold-Dev/Gold-Test (avoids wasted
     duplicate review effort) but MAY share families with them (not a stated constraint).
     Mixes source positives/unflagged, deliberately includes some model/source
     "disagreement" cases (score on the wrong side of the frozen 5%-FPR threshold vs. the
     source label), and spans multiple chains/code sizes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from data.loader import load_primary_dataset  # noqa: E402

OUT_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
os.makedirs(OUT_DIR, exist_ok=True)

SEED = 770220262
RNG = np.random.default_rng(SEED)

GOLD_TEST_N = 150
GOLD_TEST_N_POSITIVE = 50
GOLD_TEST_N_UNFLAGGED = 100
GOLD_TEST_MAX_PER_FAMILY = 3

GOLD_DEV_N = 60
PILOT_N = 20


def unique_bytecode_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per unique bytecode_sha256: representative sample_id/chain/address (lowest
    sample_id, deterministic), family_id, label, code_bytes, and the SET of chains/addresses
    the bytecode appears under (for diversity reporting)."""
    df = df.sort_values("sample_id")
    rep = df.groupby("bytecode_sha256").first().reset_index()
    chain_counts = df.groupby("bytecode_sha256")["chain"].apply(lambda s: sorted(set(s))).rename("all_chains")
    addr_counts = df.groupby("bytecode_sha256")["sample_id"].apply(list).rename("all_sample_ids")
    rep = rep.merge(chain_counts, on="bytecode_sha256").merge(addr_counts, on="bytecode_sha256")
    return rep


def attach_reference_scores(unique_df: pd.DataFrame) -> pd.DataFrame:
    pred_path = os.path.join(REPO_ROOT, "revision_v3", "results", "authguard_reference_v3_predictions.csv.gz")
    fs_path = os.path.join(REPO_ROOT, "revision_v3", "results", "authguard_reference_v3_fold_seed.csv")
    pred = pd.read_csv(pred_path)
    fs = pd.read_csv(fs_path)[["seed", "test_fold", "threshold_5pct"]]
    pred = pred.merge(fs, on=["seed", "test_fold"], how="left")
    pred["predicted_positive"] = (pred["calibrated_score"] >= pred["threshold_5pct"]).astype(int)

    mean_score = pred.groupby("sample_id")["calibrated_score"].mean().rename("ref_model_mean_score")
    mean_pred = pred.groupby("sample_id")["predicted_positive"].mean().rename("ref_model_mean_prediction")

    unique_df = unique_df.merge(mean_score, left_on="sample_id", right_index=True, how="left")
    unique_df = unique_df.merge(mean_pred, left_on="sample_id", right_index=True, how="left")
    unique_df["disagrees_with_source_label"] = (
        (unique_df["ref_model_mean_prediction"] >= 0.5).astype(int) != unique_df["label"]
    )
    return unique_df


def sample_family_capped(pool: pd.DataFrame, n: int, max_per_family: int, rng: np.random.Generator) -> pd.DataFrame:
    pool = pool.sample(frac=1.0, random_state=int(rng.integers(0, 2**31)))  # shuffle
    family_counts: dict = {}
    chosen = []
    for _, row in pool.iterrows():
        if len(chosen) >= n:
            break
        fam = row["family_id"]
        if family_counts.get(fam, 0) >= max_per_family:
            continue
        chosen.append(row)
        family_counts[fam] = family_counts.get(fam, 0) + 1
    return pd.DataFrame(chosen)


def build_gold_test(unique_df: pd.DataFrame) -> pd.DataFrame:
    positives = unique_df[unique_df["label"] == 1]
    unflagged = unique_df[unique_df["label"] == 0]
    pos_sample = sample_family_capped(positives, GOLD_TEST_N_POSITIVE, GOLD_TEST_MAX_PER_FAMILY, RNG)
    neg_sample = sample_family_capped(unflagged, GOLD_TEST_N_UNFLAGGED, GOLD_TEST_MAX_PER_FAMILY, RNG)
    gold_test = pd.concat([pos_sample, neg_sample], ignore_index=True)
    assert len(gold_test) == GOLD_TEST_N, len(gold_test)
    return gold_test


def build_gold_dev(unique_df: pd.DataFrame, excluded_families: set) -> pd.DataFrame:
    """Family-disjoint from Gold-Test (the only disjointness the audit brief requires here);
    WITHIN Gold-Dev, a bytecode-level exclusion (not family-level) is used across strata so
    the four cells don't literally duplicate an item, but strata MAY share a family -- e.g.
    the source-positive/low-model-score cell is a genuinely rare stratum (only 8 distinct
    families exist for it at all in the primary population) and requiring it to also avoid
    every family already used by the other three cells made the target of 15 unreachable."""
    pool = unique_df[~unique_df["family_id"].isin(excluded_families)].copy()
    median_score = pool["ref_model_mean_score"].median()

    strata = {
        "positive_high_score": pool[(pool["label"] == 1) & (pool["ref_model_mean_score"] >= median_score)],
        "positive_low_score": pool[(pool["label"] == 1) & (pool["ref_model_mean_score"] < median_score)],
        "unflagged_high_score": pool[(pool["label"] == 0) & (pool["ref_model_mean_score"] >= median_score)],
        "unflagged_low_score": pool[(pool["label"] == 0) & (pool["ref_model_mean_score"] < median_score)],
    }
    per_stratum = GOLD_DEV_N // 4
    chosen_frames = []
    used_bytecodes = set()
    shortfall = 0
    for name, stratum_pool in strata.items():
        stratum_pool = stratum_pool[~stratum_pool["bytecode_sha256"].isin(used_bytecodes)]
        max_per_family = 1 if name != "positive_low_score" else 3  # rare stratum: relax the cap
        picked = sample_family_capped(stratum_pool, per_stratum, max_per_family=max_per_family, rng=RNG)
        picked = picked.copy()
        picked["gold_dev_stratum"] = name
        chosen_frames.append(picked)
        used_bytecodes |= set(picked["bytecode_sha256"])
        if len(picked) < per_stratum:
            shortfall += per_stratum - len(picked)

    # positive_low_score is a genuinely rare stratum (only 8 distinct families exist for
    # "source-positive, below-median model score" in the whole primary population, before
    # even excluding Gold-Test's families) -- document the shortfall and backfill from the
    # largest remaining stratum (unflagged_high_score) rather than silently under-delivering
    # the requested total of 60.
    if shortfall > 0:
        backfill_pool = strata["unflagged_high_score"]
        backfill_pool = backfill_pool[~backfill_pool["bytecode_sha256"].isin(used_bytecodes)]
        backfill = sample_family_capped(backfill_pool, shortfall, max_per_family=1, rng=RNG)
        backfill = backfill.copy()
        backfill["gold_dev_stratum"] = "unflagged_high_score_backfill"
        chosen_frames.append(backfill)

    gold_dev = pd.concat(chosen_frames, ignore_index=True)
    return gold_dev, shortfall


def build_pilot(unique_df: pd.DataFrame, excluded_bytecodes: set) -> pd.DataFrame:
    pool = unique_df[~unique_df["bytecode_sha256"].isin(excluded_bytecodes)].copy()
    disagreement = pool[pool["disagrees_with_source_label"]]
    n_disagreement = min(6, len(disagreement))
    disagreement_sample = sample_family_capped(disagreement, n_disagreement, max_per_family=1, rng=RNG)

    remaining_pool = pool[~pool["bytecode_sha256"].isin(disagreement_sample.get("bytecode_sha256", []))]
    n_pos = 7
    n_neg = PILOT_N - n_disagreement - n_pos
    pos_sample = sample_family_capped(remaining_pool[remaining_pool["label"] == 1], n_pos, max_per_family=1, rng=RNG)
    neg_sample = sample_family_capped(remaining_pool[remaining_pool["label"] == 0], n_neg, max_per_family=1, rng=RNG)

    pilot = pd.concat([disagreement_sample, pos_sample, neg_sample], ignore_index=True)
    pilot["pilot_reason"] = (
        ["known_disagreement"] * len(disagreement_sample) + ["source_positive"] * len(pos_sample) +
        ["source_unflagged"] * len(neg_sample)
    )
    return pilot


def write_manifest(df: pd.DataFrame, sample_set: str, extra_cols: list[str]) -> pd.DataFrame:
    out = pd.DataFrame({
        "item_id": df["sample_id"],
        "sample_set": sample_set,
        "family_id": df["family_id"],
        "chain": df["chain"],
        "address": df["address"],
        "runtime_bytecode": df["runtime_bytecode"],
        "bytecode_sha256": df["bytecode_sha256"],
        "source_label": df["label"],
        "code_bytes": df["code_bytes"],
        "all_chains_with_this_bytecode": df["all_chains"].apply(json.dumps),
    })
    for c in extra_cols:
        if c in df.columns:
            out[c] = df[c]
    return out


def main() -> int:
    primary = load_primary_dataset()
    unique_df = unique_bytecode_table(primary)
    unique_df = attach_reference_scores(unique_df)

    gold_test = build_gold_test(unique_df)
    gold_dev, gold_dev_shortfall = build_gold_dev(unique_df, excluded_families=set(gold_test["family_id"]))

    # verify disjointness before proceeding
    assert set(gold_test["bytecode_sha256"]).isdisjoint(set(gold_dev["bytecode_sha256"]))
    assert set(gold_test["family_id"]).isdisjoint(set(gold_dev["family_id"]))

    pilot = build_pilot(unique_df, excluded_bytecodes=set(gold_test["bytecode_sha256"]) | set(gold_dev["bytecode_sha256"]))

    gold_test_manifest = write_manifest(gold_test, "gold_test", [])
    gold_dev_manifest = write_manifest(gold_dev, "gold_dev", ["gold_dev_stratum", "ref_model_mean_score"])
    pilot_manifest = write_manifest(pilot, "pilot", ["pilot_reason"])

    gold_test_manifest.to_csv(os.path.join(OUT_DIR, "gold_test_manifest.csv"), index=False)
    gold_dev_manifest.to_csv(os.path.join(OUT_DIR, "gold_dev_manifest.csv"), index=False)
    pilot_manifest.to_csv(os.path.join(OUT_DIR, "pilot_manifest.csv"), index=False)

    gold_test_hashes = {
        "manifest_sha256": hashlib.sha256(
            gold_test_manifest.drop(columns=["runtime_bytecode"]).to_csv(index=False).encode()
        ).hexdigest(),
        "n_items": len(gold_test_manifest),
        "n_positive": int((gold_test_manifest["source_label"] == 1).sum()),
        "n_unflagged": int((gold_test_manifest["source_label"] == 0).sum()),
        "unique_bytecode_sha256_list_sha256": hashlib.sha256(
            "\n".join(sorted(gold_test_manifest["bytecode_sha256"])).encode()
        ).hexdigest(),
        "unique_family_id_list_sha256": hashlib.sha256(
            "\n".join(sorted(str(f) for f in gold_test_manifest["family_id"].unique())).encode()
        ).hexdigest(),
        "frozen_at_utc": pd.Timestamp.utcnow().isoformat(),
        "sampling_seed": SEED,
    }
    with open(os.path.join(OUT_DIR, "gold_test_hashes.json"), "w") as f:
        json.dump(gold_test_hashes, f, indent=2, default=str)

    print(f"pilot: {len(pilot_manifest)} items ({pilot_manifest['pilot_reason'].value_counts().to_dict()})")
    print(f"gold_dev: {len(gold_dev_manifest)} items ({gold_dev_manifest['gold_dev_stratum'].value_counts().to_dict()}), "
          f"positive_low_score shortfall backfilled: {gold_dev_shortfall}")
    print(f"gold_test: {len(gold_test_manifest)} items "
          f"({gold_test_hashes['n_positive']} positive / {gold_test_hashes['n_unflagged']} unflagged)")
    print(f"gold_test unique chains: {sorted(set(c for lst in gold_test_manifest['all_chains_with_this_bytecode'] for c in json.loads(lst)))}")
    print(f"gold_test unique families: {gold_test_manifest['family_id'].nunique()} / {len(gold_test_manifest)} items")
    print(f"gold_dev unique families: {gold_dev_manifest['family_id'].nunique()} / {len(gold_dev_manifest)} items")
    print("gold_test/gold_dev family-disjoint:", set(gold_test_manifest["family_id"]).isdisjoint(set(gold_dev_manifest["family_id"])))
    print("gold_test/gold_dev bytecode-disjoint:", set(gold_test_manifest["bytecode_sha256"]).isdisjoint(set(gold_dev_manifest["bytecode_sha256"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
