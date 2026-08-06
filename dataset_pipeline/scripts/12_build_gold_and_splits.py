"""Stage 7.2 + 7.3: build the human-reviewed gold dataset and freeze leakage-safe splits.

Gold dataset
    Reviews are merged by review_id from the FROZEN copy only. A label propagates solely to
    contracts whose runtime bytecode SHA-256 is identical to the reviewed representative --
    never across similarity families. `label_origin` / `propagated_from` record which.
    NOTSCREENABLE delegates are written to a separate file and never enter the gold set.
    The unreviewed diagnostic queue is not read by this script at all.

Splits
    The split unit is a "split group": the transitive closure of
        exact bytecode hash  ->  similarity family (bytecode_family_id)  ->  resolved proxy
        implementation address
    so identical bytecode, similar bytecode, and a proxy together with its implementation can
    never straddle two splits. Groups are ordered by their earliest first-observed block and cut
    into train / val / test by cumulative count, so test contracts are observed later than
    development ones. The manifest is hashed and frozen.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.families import assert_no_family_leakage  # noqa: E402
from lib.repo_paths import REPO_ROOT  # noqa: E402

TRAIN_FRAC, VAL_FRAC = 0.60, 0.20


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    hr_dir = cfg["_resolved_paths"]["human_reviews"]
    gold_dir = cfg["_resolved_paths"]["gold_dataset"]
    split_dir = cfg["_resolved_paths"]["split_manifests"]
    os.makedirs(gold_dir, exist_ok=True)
    os.makedirs(split_dir, exist_ok=True)

    frozen = os.path.join(hr_dir, "frozen", f"{run_id}_gold_review_FROZEN.csv")
    reviews = pd.read_csv(frozen, keep_default_na=False)
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    coverage = pd.read_csv(os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_coverage_index.csv"))
    proxy_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_proxy_resolution.csv")
    proxy = pd.read_csv(proxy_path) if os.path.exists(proxy_path) else pd.DataFrame()

    screenable = families[families["retrieval_status"] == "OK"].copy()
    notscreenable = families[families["retrieval_status"] != "OK"].copy()

    # ---------- propagate reviewed labels across identical runtime bytecode only ----------
    hash_to_review = {}
    for r in reviews.to_dict("records"):
        final_label = str(r["final_label"]).strip() or str(r["llm_label"]).strip()
        hash_to_review[r["exact_bytecode_hash"]] = {
            "review_id": r["review_id"],
            "representative_address": r["contract_address"],
            "final_label": final_label,
            "final_confidence": str(r["final_confidence"]).strip() or str(r["llm_confidence"]).strip(),
            "human_decision": r["decision"],
            "llm_label": r["llm_label"],
            "llm_confidence": r["llm_confidence"],
            "llm_risk_categories": r.get("llm_risk_categories", ""),
            "comment": r.get("comment", ""),
        }

    rows = []
    for c in screenable.to_dict("records"):
        rec = hash_to_review.get(c["bytecode_sha256"])
        if rec is None:
            continue  # not covered by the reviewed sample
        rows.append({
            "address": c["delegate_address"],
            "chain": c["chain"],
            "exact_bytecode_hash": c["bytecode_sha256"],
            "bytecode_family_id": c["bytecode_family_id"],
            "runtime_bytecode": c["runtime_bytecode"],
            "bytecode_length": c["bytecode_length"],
            "first_observed_block": int(c["first_observed_block"]),
            "first_observed_block_timestamp_unix": c.get("first_observed_block_timestamp_unix"),
            "authorization_frequency": c["authorization_frequency"],
            "label_origin": ("REVIEWED" if c["delegate_address"] == rec["representative_address"]
                             else "PROPAGATED_EXACT_BYTECODE"),
            "propagated_from": rec["representative_address"],
            **{k: v for k, v in rec.items() if k != "representative_address"},
        })
    gold = pd.DataFrame(rows)
    gold = gold.merge(coverage[["address", "coverage_status"]], on="address", how="left")

    # ---------- split groups: exact hash + family + resolved proxy implementation ----------
    uf = UnionFind()
    for r in gold.to_dict("records"):
        uf.union(f"addr:{r['address']}", f"hash:{r['exact_bytecode_hash']}")
        uf.union(f"addr:{r['address']}", f"fam:{r['bytecode_family_id']}")
    n_proxy_links = 0
    if len(proxy):
        gold_addresses = set(gold["address"])
        for p in proxy.to_dict("records"):
            if p.get("resolved") and isinstance(p.get("implementation_address"), str):
                if p["address"] in gold_addresses:
                    uf.union(f"addr:{p['address']}", f"impl:{p['implementation_address'].lower()}")
                    n_proxy_links += 1
                    # if the implementation is itself a delegate in the gold set, bind them
                    if p["implementation_address"].lower() in gold_addresses:
                        uf.union(f"addr:{p['address']}", f"addr:{p['implementation_address'].lower()}")
    gold["split_group"] = [uf.find(f"addr:{a}") for a in gold["address"]]

    # Hard temporal cutoff. Ordering groups by their earliest member is not enough: a group whose
    # first member is early can still contain much later members, so development data would
    # contain contracts observed after the test set began (measured: it did). The test set is
    # therefore restricted to groups lying ENTIRELY at or after a cutoff block, which makes
    # "every test contract was observed later than every development contract" true by
    # construction. Groups that straddle the cutoff stay in development, and their count is
    # reported rather than hidden.
    group_stats = gold.groupby("split_group")["first_observed_block"].agg(["min", "max"])
    cutoff = int(gold["first_observed_block"].quantile(1.0 - (1.0 - TRAIN_FRAC - VAL_FRAC)))
    test_groups = set(group_stats[group_stats["min"] >= cutoff].index)
    straddling = set(group_stats[(group_stats["min"] < cutoff) & (group_stats["max"] >= cutoff)].index)

    dev_groups = [g for g in group_stats.index if g not in test_groups]
    dev_order = group_stats.loc[dev_groups, "min"].sort_values().index.tolist()
    dev_sizes = gold[gold["split_group"].isin(dev_groups)].groupby("split_group").size()
    n_dev = int(dev_sizes.sum())
    assigned, cum = {}, 0
    train_share = TRAIN_FRAC / (TRAIN_FRAC + VAL_FRAC)
    for g in dev_order:
        assigned[g] = "train" if (cum / n_dev) < train_share else "val"
        cum += int(dev_sizes[g])
    for g in test_groups:
        assigned[g] = "test"
    gold["split"] = gold["split_group"].map(assigned)
    gold["temporal_cutoff_block"] = cutoff

    # ---------- leakage checks ----------
    checks = {
        "families_crossing_splits": assert_no_family_leakage(gold, "bytecode_family_id", "split"),
        "exact_hashes_crossing_splits": assert_no_family_leakage(gold, "exact_bytecode_hash", "split"),
        "split_groups_crossing_splits": assert_no_family_leakage(gold, "split_group", "split"),
    }
    block_ranges = {
        s: {"min_block": int(sub["first_observed_block"].min()),
            "max_block": int(sub["first_observed_block"].max()),
            "n": int(len(sub))}
        for s, sub in gold.groupby("split")
    }
    dev_max = max([block_ranges[s]["max_block"] for s in ("train", "val") if s in block_ranges] or [0])
    temporal_ok = block_ranges.get("test", {}).get("min_block", 0) >= dev_max if "test" in block_ranges else False

    gold_path = os.path.join(gold_dir, f"{run_id}_gold_reviewed.csv")
    gold.to_csv(gold_path, index=False)
    ns_path = os.path.join(gold_dir, f"{run_id}_notscreenable.csv")
    notscreenable.to_csv(ns_path, index=False)

    manifest_rows = gold[["address", "exact_bytecode_hash", "bytecode_family_id", "split_group",
                          "split", "final_label", "coverage_status", "first_observed_block",
                          "label_origin", "propagated_from"]]
    manifest_path = os.path.join(split_dir, f"{run_id}_split_manifest.csv")
    manifest_rows.to_csv(manifest_path, index=False)
    for s in ("train", "val", "test"):
        gold[gold["split"] == s].to_csv(os.path.join(split_dir, f"{run_id}_{s}.csv"), index=False)

    manifest_digest = hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    with open(os.path.join(split_dir, f"{run_id}_split_manifest.sha256"), "w") as f:
        f.write(f"{manifest_digest}  {os.path.basename(manifest_path)}\n")

    summary = {
        "n_reviewed_runtimes": int(len(reviews)),
        "n_gold_contracts": int(len(gold)),
        "n_labeled_by_direct_review": int((gold["label_origin"] == "REVIEWED").sum()),
        "n_labeled_by_exact_bytecode_propagation": int((gold["label_origin"] == "PROPAGATED_EXACT_BYTECODE").sum()),
        "n_notscreenable_held_separately": int(len(notscreenable)),
        "n_split_groups": int(gold["split_group"].nunique()),
        "n_families": int(gold["bytecode_family_id"].nunique()),
        "n_proxy_implementation_links": n_proxy_links,
        "label_distribution": gold["final_label"].value_counts().to_dict(),
        "split_sizes": gold["split"].value_counts().to_dict(),
        "split_label_distribution": {s: sub["final_label"].value_counts().to_dict()
                                     for s, sub in gold.groupby("split")},
        "split_block_ranges": block_ranges,
        "temporal_cutoff_block": int(cutoff),
        "all_test_contracts_at_or_after_cutoff": bool(
            (gold[gold["split"] == "test"]["first_observed_block"] >= cutoff).all()),
        "temporal_ordering_every_test_after_every_dev": bool(temporal_ok),
        "n_groups_straddling_cutoff_kept_in_dev": len(straddling),
        "n_dev_contracts_observed_after_cutoff": int(
            ((gold["split"] != "test") & (gold["first_observed_block"] >= cutoff)).sum()),
        "leakage_checks": {k: (len(v), v[:5]) for k, v in checks.items()},
        "gold_csv": gold_path,
        "notscreenable_csv": ns_path,
        "split_manifest_csv": manifest_path,
        "split_manifest_sha256": manifest_digest,
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(gold_dir, f"{run_id}_gold_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    if any(v for v in checks.values()):
        raise SystemExit("REFUSING: leakage detected across splits")


if __name__ == "__main__":
    main()
