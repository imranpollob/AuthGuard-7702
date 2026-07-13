#!/usr/bin/env python3
"""
05_supporting.py -- Task E supporting analyses.

  1. Contamination upper-bound on benign_cleared (100-sample + full), conservative.
  2. End-to-end latency (ms/contract) for the pre-signing tool (featurize + score).
  3. Explanation layer: nearest-family + fired signals, 50-case audit + hit-rate.
  4. Synthetic signer-exposure case studies (LABELLED ILLUSTRATIVE, not victim-grounded).
"""
import os, sys, json, time, hashlib, warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, disasm, minhash_signature, SEED
from ag_features import featurize, build_sensitive_selector_set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
SENS = build_sensitive_selector_set()
rng = np.random.default_rng(SEED)


def load():
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    frozen = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    df["family_id"] = frozen["family_id"].values
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    df["bchash"] = df["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())
    return df


# ---------------------------------------------------------------------------
def contamination(df):
    """Conservative UPPER-BOUND on how many benign_cleared are actually malicious-like."""
    mal_hashes = set(df[df["class"] == "malicious"]["bchash"])
    mal_families = set(df[df["class"] == "malicious"]["family_id"])
    cleared = df[df["class"] == "benign_cleared"].copy()

    cleared["exact_dup_malicious"] = cleared["bchash"].isin(mal_hashes)
    cleared["same_family_as_malicious"] = cleared["family_id"].isin(mal_families)
    # sensitive selector present in bytecode (a name-rule footprint the clearing missed)
    def has_sens(bc):
        _, _, sel = disasm(bc)
        return len(set(sel) & SENS) > 0
    cleared["has_sensitive_selector"] = cleared["bc"].map(has_sens)

    def summarize(sub):
        n = len(sub)
        return dict(
            n=n,
            exact_dup_malicious=int(sub["exact_dup_malicious"].sum()),
            same_family_as_malicious=int(sub["same_family_as_malicious"].sum()),
            has_sensitive_selector=int(sub["has_sensitive_selector"].sum()),
            upper_bound_pct=round(100 * sub["same_family_as_malicious"].mean(), 1),
            strong_evidence_pct=round(100 * sub["exact_dup_malicious"].mean(), 1),
        )

    sample_idx = rng.choice(len(cleared), size=100, replace=False)
    sample = cleared.iloc[sample_idx]
    return {"full_benign_cleared": summarize(cleared),
            "random_100_sample": summarize(sample)}


# ---------------------------------------------------------------------------
def latency(df):
    """ms/contract for the pre-signing pipeline: featurize + score. No decompiler in loop."""
    # train a model once on a subset
    mask = df["class"].isin(["malicious", "benign_cleared"])
    Xd = np.load(os.path.join(RES, "features_dense.npz"))["X"][mask.values]
    Xn = np.load(os.path.join(RES, "features_ngram.npz"))["X"][mask.values]
    y = (df[mask]["class"] == "malicious").astype(int).values
    clf = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, random_state=SEED,
                        n_jobs=4, tree_method="hist", eval_metric="logloss")
    clf.fit(np.hstack([Xd, Xn]), y)

    sample = df.sample(300, random_state=SEED)
    # per-contract end-to-end timing (featurize single + predict single)
    times = []
    for bc in sample["bytecode"].tolist():
        t0 = time.perf_counter()
        xd, xn, _ = featurize([bc], sens=SENS)
        clf.predict_proba(np.hstack([xd, xn]))[:, 1]
        times.append((time.perf_counter() - t0) * 1000.0)
    times = np.array(times)
    # batched throughput
    t0 = time.perf_counter()
    xd, xn, _ = featurize(sample["bytecode"].tolist(), sens=SENS)
    clf.predict_proba(np.hstack([xd, xn]))
    batch_ms = (time.perf_counter() - t0) * 1000.0
    return dict(per_contract_ms_mean=float(times.mean()),
                per_contract_ms_p50=float(np.percentile(times, 50)),
                per_contract_ms_p95=float(np.percentile(times, 95)),
                batched_ms_per_contract=float(batch_ms / len(sample)),
                n_timed=len(sample))


# ---------------------------------------------------------------------------
def explanation_audit(df):
    """For 50 held-out malicious: nearest TRAIN neighbor (MinHash) + fired signals.
    Hit-rate = fraction whose nearest train neighbor is genuinely malicious."""
    mask = df["class"].isin(["malicious", "benign_cleared"]).values
    sub = df[mask].reset_index(drop=True)
    y = (sub["class"] == "malicious").astype(int).values
    groups = sub["family_id"].values

    # signatures for the sub-population
    sigs = np.stack([minhash_signature(disasm(bc)[0]) for bc in sub["bc"].values])

    gkf = GroupKFold(n_splits=5)
    tr, te = next(gkf.split(sub, y, groups))
    te_mal = [i for i in te if y[i] == 1]
    # pick 50 (seeded)
    pick = list(rng.choice(te_mal, size=min(50, len(te_mal)), replace=False))

    base_rate = float(y[tr].mean())  # malicious base rate in train (random-NN baseline)
    cases, hits, sig_cov = [], 0, 0
    sims_all, hi_sim_hits, hi_sim_n = [], 0, 0
    HI = 0.70
    for i in pick:
        sims = (sigs[tr] == sigs[i]).mean(axis=1)
        jrel = int(np.argmax(sims)); j = tr[jrel]; nn = sub.iloc[j]
        s = float(sims[jrel]); sims_all.append(s)
        is_hit = (nn["class"] == "malicious"); hits += int(is_hit)
        if s >= HI:
            hi_sim_n += 1; hi_sim_hits += int(is_hit)
        ops, _, sel = disasm(sub.iloc[i]["bc"])
        fired = []
        if set(sel) & SENS: fired.append("sensitive_selector")
        if "DELEGATECALL" in ops: fired.append("delegatecall")
        if any(o in ops for o in ("CALL", "CALLCODE")): fired.append("external_call")
        if "SELFDESTRUCT" in ops: fired.append("selfdestruct")
        if fired: sig_cov += 1
        cases.append(dict(address=sub.iloc[i]["address"], nn_class=nn["class"],
                          nn_family=nn["family_id"], nn_similarity=round(s, 3),
                          fired_signals=fired))
    n = len(pick)
    return dict(
        n_cases=n,
        nn_malicious_rate=round(hits / max(n, 1), 3),
        random_nn_baseline=round(base_rate, 3),
        fired_signal_coverage=round(sig_cov / max(n, 1), 3),
        mean_nn_similarity=round(float(np.mean(sims_all)), 3),
        median_nn_similarity=round(float(np.median(sims_all)), 3),
        high_sim_threshold=HI,
        high_sim_n=hi_sim_n,
        high_sim_malicious_rate=round(hi_sim_hits / hi_sim_n, 3) if hi_sim_n else None,
        cases=cases[:10])


# ---------------------------------------------------------------------------
def synthetic_signer_exposure(df):
    """ILLUSTRATIVE ONLY. No real victim/signer data exists (stripped for ethics).
    Hypothetical loss a signer would face given a delegate's populated capability profile."""
    profiles = {
        "retail":  dict(native_eth=0.5,  erc20_usd=1200,   nft_usd=0,     approvals=2),
        "active":  dict(native_eth=8.0,  erc20_usd=45000,  nft_usd=6000,  approvals=12),
        "whale":   dict(native_eth=140.0, erc20_usd=900000, nft_usd=250000, approvals=30),
    }
    ETH_USD = 3000.0  # illustrative fixed price
    mal = df[df["class"] == "malicious"].copy()
    for c in ["cap_move_erc20", "cap_move_nft", "cap_grant_approval", "cap_attacker_controlled_sink"]:
        mal[c] = df.loc[mal.index, c].fillna(False).astype(bool)

    # a few representative capability profiles among the malicious set
    reps = {
        "erc20_drainer": mal[mal["cap_move_erc20"]].head(1),
        "approval_abuser": mal[mal["cap_grant_approval"]].head(1),
        "nft_sweeper": mal[mal["cap_move_nft"]].head(1),
        "dynamic_sink": mal[mal["cap_attacker_controlled_sink"] & ~mal["cap_move_erc20"]].head(1),
    }
    out = {}
    for rep_name, rows in reps.items():
        if len(rows) == 0:
            continue
        r = rows.iloc[0]
        rep = {}
        for pname, p in profiles.items():
            loss = 0.0
            # native ETH is always reachable via the value-receiving external-call hook
            loss += p["native_eth"] * ETH_USD
            if r["cap_move_erc20"]:
                loss += p["erc20_usd"]
            if r["cap_move_nft"]:
                loss += p["nft_usd"]
            if r["cap_grant_approval"]:
                loss += 0.0  # approval grants enable FUTURE loss; count as at-risk, not immediate
            rep[pname] = dict(illustrative_loss_usd=round(loss, 0),
                              at_risk_approvals=p["approvals"] if r["cap_grant_approval"] else 0)
        out[rep_name] = dict(example_address=r["address"], capability=rep)
    return dict(DISCLAIMER="SYNTHETIC illustrative profiles; no real victim/signer data exists "
                           "(stripped for ethics). Fixed ETH=$3000. Not an evaluation metric.",
                eth_usd=ETH_USD, profiles=profiles, cases=out)


def main():
    df = load()
    results = {}
    print("[E] contamination...", flush=True)
    results["contamination"] = contamination(df)
    print("[E] latency...", flush=True)
    results["latency"] = latency(df)
    print("[E] explanation audit...", flush=True)
    results["explanation"] = explanation_audit(df)
    print("[E] synthetic signer exposure...", flush=True)
    results["synthetic_signer"] = synthetic_signer_exposure(df)

    with open(os.path.join(RES, "supporting.json"), "w") as f:
        json.dump(results, f, indent=2)

    c = results["contamination"]
    print("\n=== CONTAMINATION (upper bound on mislabeled benign_cleared) ===")
    print("full :", c["full_benign_cleared"])
    print("n=100:", c["random_100_sample"])
    print("\n=== LATENCY ===", results["latency"])
    e = results["explanation"]
    print(f"\n=== EXPLANATION === fired_signal_coverage={e['fired_signal_coverage']} "
          f"nn_malicious_rate={e['nn_malicious_rate']} (baseline {e['random_nn_baseline']}) "
          f"high_sim_malicious_rate={e['high_sim_malicious_rate']} (n={e['high_sim_n']})")


if __name__ == "__main__":
    main()
