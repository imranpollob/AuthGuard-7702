#!/usr/bin/env python3
"""Phase 1.2-1.5 — direct robust recall, benchmark count, byte budget, live-holdout facts.

Every value is read from code or data. Nothing is assumed, estimated, or carried over
from the manuscript.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
RESULTS = os.path.join(RV2, "results", "adaptive_attacks_v2")
OUT = os.path.join(RV2, "results", "sprint_phase1")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

spec = importlib.util.spec_from_file_location("phase0", os.path.join(
    RV2, "experiments", "sprint_phase0", "phase0_fixed_oracles.py"))
_p0 = importlib.util.module_from_spec(spec)
sys.modules["phase0"] = _p0
spec.loader.exec_module(_p0)


# ------------------------------------------------------------------ 1.2 robust recall
def robust_recall(frame, target, method_set, label):
    """Direct source-level robust recall.

    numerator   = positive source-seed observations cleanly detected AND still detected
                  after the strongest attack in `method_set`
    denominator = ALL positive source-seed observations for that target
    """
    g = frame[frame.target_model == target]
    if not len(g):
        return None
    sub = g[g.method.isin(method_set)]
    key = ["seed", "fold", "sid"]
    # strongest attack per observation = lowest adversarial score across the method set
    idx = sub.groupby(key).adversarial_score.idxmin()
    best = sub.loc[idx]
    detected_clean = best.clean_detected.to_numpy(bool)
    still_detected = best.adversarial_score.to_numpy() >= best.threshold.to_numpy()
    survived = int((detected_clean & still_detected).sum())
    total = int(g.drop_duplicates(key).shape[0])
    clean = float(detected_clean.mean())
    eligible = best[best.clean_detected]
    asr = float((eligible.adversarial_score < eligible.threshold).mean()) if len(eligible) else np.nan
    return dict(
        model=target, attack_set=label, n_positive_observations=total,
        n_survived=survived, robust_recall_direct=survived / total if total else np.nan,
        clean_detection=clean, ASR=asr,
        robust_recall_product=clean * (1 - asr) if not np.isnan(asr) else np.nan,
        seed_scope=sorted(int(s) for s in g.seed.unique()),
        fold_scope=sorted(int(f) for f in g.fold.unique()),
        provenance="stored_artifact")


# --------------------------------------------------------------- 1.3 benchmark count
def benchmark_audit():
    bench = pd.read_csv(BENCH)
    counts = bench.population.value_counts().to_dict()
    prod_csv = os.path.join(ROOT, "benign_7702_bytecode.csv")
    production = pd.read_csv(prod_csv) if os.path.exists(prod_csv) else None
    cats = {
        "PRIMARY_EVALUATION": int(counts.get("PRIMARY_EVALUATION", 0)),
        "EXTERNAL_BENIGN_CONTROL": int(counts.get("EXTERNAL_BENIGN_CONTROL", 0)),
        "QUALITATIVE_CONTROL": int(counts.get("QUALITATIVE_CONTROL", 0)),
        "EXCLUDED_UNCERTAIN_INPUT": int(counts.get("EXCLUDED_UNCERTAIN_INPUT", 0)),
    }
    total_rows = int(len(bench))
    # Do rows collide across categories by identity (sample_id) or by content hash?
    dup_sid = bench[bench.duplicated("sample_id", keep=False)]
    dup_hash = bench[bench.duplicated("bytecode_sha256", keep=False)]
    cross_hash = (dup_hash.groupby("bytecode_sha256").population.nunique()
                  if len(dup_hash) else pd.Series(dtype=int))
    cross_cat_hashes = cross_hash[cross_hash > 1].index.tolist() if len(cross_hash) else []
    return dict(
        file=os.path.relpath(BENCH, RV2),
        categories_in_file=cats,
        sum_of_categories_in_file=sum(cats.values()),
        actual_rows_in_file=total_rows,
        manuscript_claim_3082=3082,
        manuscript_table_production_controls=8,
        production_registry_rows=(int(len(production)) if production is not None else None),
        production_registry_unique_projects=(int(production.project.nunique())
                                             if production is not None else None),
        production_registry_unique_bytecode=(int(production.bytecode.nunique())
                                             if production is not None else None),
        duplicate_sample_ids=int(len(dup_sid)),
        duplicate_sample_id_values=dup_sid.sample_id.unique().tolist()[:20],
        hashes_appearing_in_multiple_populations=len(cross_cat_hashes),
        example_cross_population_hashes=cross_cat_hashes[:10],
        provenance="stored_artifact")


# ------------------------------------------------------------------ 1.4 byte budget
def byte_budget_audit():
    runner_path = os.path.join(RV2, "experiments", "adaptive_attacks_v2",
                               "run_adaptive_attacks_v2.py")
    text = open(runner_path).read()
    m = re.search(r"def valid\(self, candidate\):.*?return bool\(ops\)[^\n]*", text, re.S)
    snippet = m.group(0) if m else "NOT FOUND"
    max_overhead = re.search(r"^MAX_OVERHEAD\s*=\s*([0-9.]+)", text, re.M)
    frames = [pd.read_csv(f) for f in sorted(glob.glob(
        os.path.join(RESULTS, "attack_per_row_seed*.csv.gz")))]
    frame = pd.concat(frames, ignore_index=True)
    f200 = frame[frame.method == "F200"]
    ratio = 1.0 + f200.byte_overhead.to_numpy(dtype=float)  # final/original
    return dict(
        enforcing_code=snippet.strip(),
        MAX_OVERHEAD=float(max_overhead.group(1)) if max_overhead else None,
        rule_as_implemented=("len(final_bytes) <= original_size * (1 + MAX_OVERHEAD) + 1, "
                             "i.e. ADDED bytes <= 2x original, FINAL size <= 3x original "
                             "(+1 byte for the STOP guard)"),
        byte_overhead_column_definition=("(len(candidate)//2 - original_size) / original_size "
                                         "= added/original, NOT final/original"),
        f200_final_over_original=dict(
            n=int(len(ratio)), median=float(np.median(ratio)),
            p95=float(np.percentile(ratio, 95)), max=float(ratio.max()),
            min=float(ratio.min())),
        provenance="stored_artifact")


# ------------------------------------------------------------- 1.5 live-holdout facts
def live_holdout_facts():
    path = os.path.join(RV2, "results", "temporal_holdout_v1")
    scores = pd.read_csv(os.path.join(path, "temporal_live_scores.csv.gz"))
    res = json.load(open(os.path.join(path, "temporal_holdout_results.json")))
    rates = pd.read_csv(os.path.join(path, "temporal_flag_rates.csv"))
    bench = pd.read_csv(BENCH)
    live_hashes = set(scores.bytecode_sha256.str.lower())
    bench_hashes = set(bench.bytecode_sha256.str.lower())
    clean_mask = scores["max_minhash_sim_to_primary"] < 0.85
    per_point = {}
    for point, grp in rates.groupby("operating_point"):
        per_seed = grp.groupby("seed")[
            ["flag_rate", "flag_rate_leakage_clean",
             "flag_rate_authorization_weighted", "alerts_per_1000_authorizations"]].mean()
        per_point[str(point)] = {c: dict(mean=float(per_seed[c].mean()),
                                         sd=float(per_seed[c].std(ddof=0)))
                                 for c in per_seed.columns}
    return dict(
        total_live_delegates=int(len(scores)),
        unique_runtime_bytecodes=int(scores.bytecode_sha256.nunique()),
        exact_hash_overlap_with_benchmark=len(live_hashes & bench_hashes),
        family_overlap_at_0_85=int((~clean_mask).sum()),
        leakage_clean_denominator=int(clean_mask.sum()),
        leakage_clean_formula="clean_mask = max_minhash_sim_to_primary < 0.85 (line 168)",
        leakage_gate_json=res["leakage_gate"],
        flag_rates_by_operating_point=per_point,
        n_checkpoints=int(rates.groupby(["seed", "fold"]).ngroups),
        seed_scope=sorted(int(s) for s in rates.seed.unique()),
        fold_scope=sorted(int(f) for f in rates.fold.unique()),
        provenance="stored_artifact")


def main():
    os.makedirs(OUT, exist_ok=True)
    frames = {os.path.basename(f): pd.read_csv(f) for f in sorted(glob.glob(
        os.path.join(RESULTS, "attack_per_row_seed*.csv.gz")))}
    main3 = pd.concat([v for k, v in frames.items()
                       if not k.endswith("_ext.csv.gz")], ignore_index=True)
    ext = frames["attack_per_row_seed7702_ext.csv.gz"]

    sets = {
        "TierA_fixed_flooding": _p0.FLOODS,
        "TierB_fixed_flooding_metadata": _p0.FLOODS + ["M1"],
        "TierC_fixed_all_seven": _p0.FLOODS + ["M1", "M2", "M3"],
        "TierC_adaptive_best": ["random_search", "beam_search"],
        "TierC_all_evaluated": _p0.FLOODS + ["M1", "M2", "M3",
                                             "random_search", "beam_search"],
    }
    rr = []
    for src, targets in [(main3, _p0.PRIMARY), (ext, sorted(ext.target_model.unique()))]:
        for t in targets:
            for label, methods in sets.items():
                have = set(src[src.target_model == t].method.unique())
                if not set(methods) <= have:
                    continue
                r = robust_recall(src, t, methods, label)
                if r:
                    rr.append(r)
    rr_frame = pd.DataFrame(rr)
    rr_frame.to_csv(os.path.join(OUT, "phase1_robust_recall.csv"), index=False)
    print("[1.2] direct robust recall (seed-scope labelled):")
    for _, r in rr_frame.iterrows():
        flag = "" if abs(r.robust_recall_direct - r.robust_recall_product) < 5e-4 else "  <-- differs"
        print(f"   {r.model:<24}{r.attack_set:<32}direct={r.robust_recall_direct:.4f} "
              f"product={r.robust_recall_product:.4f} seeds={r.seed_scope}{flag}")

    bench_audit = benchmark_audit()
    print("\n[1.3] benchmark count audit:")
    for k, v in bench_audit.items():
        if k not in ("example_cross_population_hashes", "duplicate_sample_id_values"):
            print(f"   {k}: {v}")

    budget = byte_budget_audit()
    print("\n[1.4] byte budget:")
    print(f"   MAX_OVERHEAD = {budget['MAX_OVERHEAD']}")
    print(f"   rule: {budget['rule_as_implemented']}")
    print(f"   F200 final/original: {budget['f200_final_over_original']}")

    live = live_holdout_facts()
    print("\n[1.5] live holdout:")
    for k in ("total_live_delegates", "unique_runtime_bytecodes",
              "exact_hash_overlap_with_benchmark", "family_overlap_at_0_85",
              "leakage_clean_denominator", "n_checkpoints"):
        print(f"   {k}: {live[k]}")

    payload = dict(
        phase="1.2-1.5 factual repairs",
        script="revision_v2/experiments/sprint_phase1/phase1_facts.py",
        git_commit=_p0.git_commit(), provenance="stored_artifact",
        robust_recall=rr, benchmark_audit=bench_audit,
        byte_budget=budget, live_holdout=live)
    with open(os.path.join(OUT, "phase1_facts.json"), "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\n[1.2-1.5] wrote {OUT}/phase1_facts.json")


if __name__ == "__main__":
    main()
