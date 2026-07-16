#!/usr/bin/env python3
"""G-MUT v2 + G-VOL v2: corrected clean-M0 thresholds (inner family-grouped OOF on the
outer-training population, frozen, applied unchanged to every transformed condition),
donor-isolated multi-donor flooding (primary arm) + v1-fixed-donor continuity arm,
transformed NEGATIVES included so FPR is reported per condition, per-row persistence.

Protocols stay distinct: G-MUT = tiers M0..M3 (M2/M3 include the ~20% dead-code append);
G-VOL = metadata+addr+selector recipe then flooding fraction sweep {0,.25,.5,1,2}.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from harness import (load_corpus, task_arrays, feature_views, default_methods,  # noqa: E402
                     oof_threshold, metrics_full, write_manifest,
                     verify_frozen_or_die, RV2, DH, SEED, featurize, SENS,
                     normalize_bytecode)
from pools import DonorPools, mut  # noqa: E402

OUT = os.path.join(RV2, "results")
TIERS = ["M0", "M1", "M2", "M3"]
FRACS = [0.0, 0.25, 0.5, 1.0, 2.0]
MODEL_SEEDS = [SEED, 7703, 7704, 7705, 7706]


def gen_gmut_variant(pools, row, fold, tier, arm):
    """G-MUT tier generation. arm='iso' uses donor pools; arm='v1donor' uses frozen v1 code."""
    if arm == "v1donor":
        # v1 continuity arm: identical seed material (address) and fixed v1 donor
        return mut.make_mutant(row["bytecode"], row["address"], tier).hex()
    seed_addr = f"test:{row['sid']}"
    b = mut.to_bytes(row["bytecode"])
    if tier == "M0":
        return normalize_bytecode(row["bytecode"])
    b = mut.mut_metadata(b, seed_addr)
    if tier == "M1":
        return b.hex()
    b = mut.mut_addr_immediates(b, seed_addr)
    if tier == "M2":
        return pools.flood(b, row, fold, "test", "GMUT:M2", 0.20, "test").hex()
    b = mut.mut_selector_rewrite(b, seed_addr)
    return pools.flood(b, row, fold, "test", "GMUT:M3", 0.20, "test").hex()


def gen_gvol_variant(pools, row, fold, frac, arm):
    seed_addr = f"test:{row['sid']}" if arm == "iso" else row["address"]
    b = mut.to_bytes(row["bytecode"])
    b = mut.mut_metadata(b, seed_addr)
    b = mut.mut_addr_immediates(b, seed_addr)
    b = mut.mut_selector_rewrite(b, seed_addr)
    if frac <= 0:
        return b.hex()
    if arm == "v1donor":
        return mut.mut_deadcode_append(b, seed_addr, frac).hex()
    return pools.flood(b, row, fold, "test", f"GVOL:F{int(frac*100)}", frac, "test").hex()


def main():
    started = time.time()
    verify_frozen_or_die()
    for d in ["gmut_v2", "gvol_v2"]:
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    views = feature_views(meta)
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    X = np.hstack([Xds, Xns]).astype(np.float32)
    methods = default_methods(views, views["n_dense"])
    dcols = meta["dense_cols"]
    name_j, call_j = dcols.index("has_sensitive_selector"), dcols.index("n_call_family")

    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "GMUTVOL_V2")

    per_row = []
    thr_store = {}   # (model, seed, fold) -> threshold
    curves = {arm: {m: {t: {"recall": [], "FPR": []} for t in TIERS}
                    for m in list(methods) + ["usenix_name_rule", "usenix_struct_rule", "blocklist"]}
              for arm in ["iso", "v1donor"]}
    vol = {arm: {m: {f: {"recall": [], "FPR": []} for f in FRACS}
                 for m in ["opcode_xgb", "authguard", "usenix_name_rule", "usenix_struct_rule"]}
           for arm in ["iso", "v1donor"]}
    preservation = {t: {"checked": 0, "preserved": 0} for t in TIERS if t != "M0"}

    for fold in range(5):
        pools.assert_disjoint(fold)
        tr = np.flatnonzero(folds != fold); te = np.flatnonzero(folds == fold)
        groups_tr = sub["family_id"].to_numpy()[tr]
        fitted, thrs = {}, {}
        for mname, method in methods.items():
            fitted[mname], thrs[mname] = {}, {}
            for seed in MODEL_SEEDS if mname != "selector_model" else [SEED]:
                thr, _, _ = oof_threshold(method, X[tr], y[tr], groups_tr, seed)
                model = method["fit"](X[tr], y[tr], seed)
                fitted[mname][seed] = model
                thrs[mname][seed] = thr
                thr_store[f"{mname}|{seed}|{fold}"] = thr
        train_mal_hashes = set(sub["bchash"].to_numpy()[tr[y[tr] == 1]])
        held = sub.iloc[te]

        def evaluate(cond_label, hexes, group, arm):
            xd, xn, _ = featurize(hexes, sens=SENS)
            xf = np.hstack([xd, xn]).astype(np.float32)
            yv = held["y"].to_numpy()
            hs = [hashlib.sha256(normalize_bytecode(h).encode()).hexdigest() for h in hexes]
            rule_scores = {
                "usenix_name_rule": (xd[:, name_j] > 0).astype(float),
                "usenix_struct_rule": (xd[:, call_j] > 0).astype(float),
                "blocklist": np.array([1.0 if h in train_mal_hashes else 0.0 for h in hs]),
            }
            for rname, sc in rule_scores.items():
                if rname in group:
                    m = metrics_full(yv, sc, 0.5)
                    group[rname][cond_label]["recall"].append(m["Recall"])
                    group[rname][cond_label]["FPR"].append(m["FPR"])
            for mname in methods:
                if mname not in group:
                    continue
                seeds = MODEL_SEEDS if mname != "selector_model" else [SEED]
                for seed in seeds:
                    sc = methods[mname]["score"](fitted[mname][seed], xf)
                    thr = thrs[mname][seed]
                    m = metrics_full(yv, sc, thr)
                    if seed == SEED:
                        group[mname][cond_label]["recall"].append(m["Recall"])
                        group[mname][cond_label]["FPR"].append(m["FPR"])
                    for k in range(len(sc)):
                        per_row.append(dict(
                            experiment="GMUT" if cond_label in TIERS else "GVOL",
                            arm=arm, condition=str(cond_label), fold=fold, model=mname,
                            seed=seed, sid=held["sid"].iloc[k],
                            family_id=held["family_id"].iloc[k], y=int(yv[k]),
                            score=float(sc[k]), threshold=thr,
                            pred=int(sc[k] >= thr)))

        for arm in ["iso", "v1donor"]:
            for tier in TIERS:
                hexes = []
                for _, row in held.iterrows():
                    h = gen_gmut_variant(pools, row, fold, tier, arm)
                    if arm == "iso" and tier != "M0":
                        preservation[tier]["checked"] += 1
                        preservation[tier]["preserved"] += int(
                            mut.verify_preservation(row["bytecode"], bytearray.fromhex(h)))
                    hexes.append(h)
                evaluate(tier, hexes, curves[arm], arm)
            for frac in FRACS:
                hexes = [gen_gvol_variant(pools, row, fold, frac, arm)
                         for _, row in held.iterrows()]
                evaluate(frac, hexes, vol[arm], arm)
        print(f"[fold {fold}] iso AG M3 R={curves['iso']['authguard']['M3']['recall'][-1]:.3f} "
              f"GVOL+200 R={vol['iso']['authguard'][2.0]['recall'][-1]:.3f} "
              f"({time.time()-started:.0f}s)", flush=True)

    def agg(tree):
        out = {}
        for m, conds in tree.items():
            out[m] = {}
            for c, met in conds.items():
                out[m][str(c)] = {k: {"mean": float(np.mean(v)), "std": float(np.std(v)),
                                      "folds": v} for k, v in met.items()}
        return out

    res_mut = {arm: agg(curves[arm]) for arm in curves}
    res_vol = {arm: agg(vol[arm]) for arm in vol}
    with open(os.path.join(OUT, "gmut_v2", "gmut_v2_results.json"), "w") as f:
        json.dump({"results": res_mut, "preservation": preservation,
                   "protocol": "threshold_protocol_v2 + donor_isolation_protocol v1.1"}, f, indent=2)
    with open(os.path.join(OUT, "gvol_v2", "gvol_v2_results.json"), "w") as f:
        json.dump({"results": res_vol,
                   "protocol": "threshold_protocol_v2 + donor_isolation_protocol v1.1"}, f, indent=2)
    pd.DataFrame(per_row).to_csv(
        os.path.join(OUT, "gmut_v2", "gmutvol_v2_per_row_scores.csv.gz"), index=False)
    pd.DataFrame([{"key": k, "threshold": v} for k, v in thr_store.items()]).to_csv(
        os.path.join(OUT, "gmut_v2", "gmutvol_v2_thresholds.csv"), index=False)
    led = pools.write_ledger(os.path.join(OUT, "gmut_v2", "donor_ledger_gmutvol.csv"))
    print(f"[ledger] {len(led)} flooded variants recorded")

    outputs = [os.path.join(OUT, "gmut_v2", p) for p in
               ["gmut_v2_results.json", "gmutvol_v2_per_row_scores.csv.gz",
                "gmutvol_v2_thresholds.csv", "donor_ledger_gmutvol.csv"]] + \
              [os.path.join(OUT, "gvol_v2", "gvol_v2_results.json")]
    write_manifest(os.path.join(OUT, "gmut_v2"),
                   dict(protocol=["threshold_protocol_v2", "donor_isolation_protocol_v1.1"],
                        arms=["iso", "v1donor"], model_seeds=MODEL_SEEDS),
                   outputs, started,
                   inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(f"[gmutvol_v2] done in {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
