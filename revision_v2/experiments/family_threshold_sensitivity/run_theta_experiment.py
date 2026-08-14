#!/usr/bin/env python3
"""Steps 5-7: retrain AuthGuard-Seq and the 15-feature emulator logistic regression under
a given family threshold, evaluate clean performance, and run the Tier-B adaptive attack.

Isolated entry point. It does not modify the shared attack runner, the architectures, the
training protocol, the threshold fitting, the donor isolation, or the statistics. Two
things are patched in the loaded process:

  1. `search.ACTIONS` -> the Tier-B action set (same restriction, same verification as the
     RQ4 Tier-B replication; the restriction module is imported rather than reimplemented).
  2. `runner.load_primary` -> returns the benchmark with `family_id`, `fold_id` and
     `outer_fold_secondary` replaced by the theta-specific assignments built by
     build_family_thresholds.py. The row set is unchanged and is asserted to be unchanged.

`fit_fold_models` is additionally wrapped so that clean metrics are computed on the full
test fold from the same trained scorers that the attack then uses. No second training run,
so the clean and adaptive numbers are guaranteed to come from identical models.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(RV2, "results", "family_threshold_sensitivity")
RUNNER = os.path.join(RV2, "experiments", "adaptive_attacks_v2",
                      "run_adaptive_attacks_v2.py")
TIERB = os.path.join(RV2, "experiments", "rq4_replication", "run_rq4_tierb.py")

MODELS = ["authguard_seq", "emulator_logreg"]
CLEAN_ROWS: list[dict] = []
PREDICTION_ROWS: list[dict] = []


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def theta_frames(runner, theta, tag):
    """Benchmark with theta-specific family/fold columns installed."""
    split = pd.read_csv(os.path.join(OUT, f"split_manifest_{tag}.csv"))
    bench = pd.read_csv(runner.BENCH)
    if len(split) != len(bench):
        raise SystemExit(f"{tag}: split manifest rows {len(split)} != benchmark {len(bench)}")
    merged = bench.merge(split[["sample_id", "family_id_theta", "fold_id_theta",
                                "outer_fold_secondary_theta"]],
                         on="sample_id", how="left", validate="one_to_one")
    if merged["family_id_theta"].isna().any():
        raise SystemExit(f"{tag}: benchmark rows without a theta family assignment")

    before_rows = int((merged["population"] == "PRIMARY_EVALUATION").sum())
    merged["family_id"] = merged["family_id_theta"]
    primary = merged["population"] == "PRIMARY_EVALUATION"
    merged.loc[primary, "fold_id"] = merged.loc[primary, "fold_id_theta"].astype(int)
    merged["outer_fold_secondary"] = merged["outer_fold_secondary_theta"]
    merged = merged.drop(columns=["family_id_theta", "fold_id_theta",
                                  "outer_fold_secondary_theta"])

    frame = merged[primary].reset_index(drop=True)
    # Same invariants the runner's own load_primary asserts, re-asserted after the swap.
    assert not frame["bytecode_repaired"].any()
    assert len(frame) == 2190 and int(frame["label"].sum()) == 727, \
        f"{tag}: population changed ({len(frame)} rows, {int(frame['label'].sum())} positives)"
    assert before_rows == len(frame)
    assert frame.groupby("family_id")["fold_id"].nunique().max() == 1, \
        f"{tag}: a family spans more than one fold"
    assert frame.groupby("bytecode_sha256")["fold_id"].nunique().max() == 1, \
        f"{tag}: an exact bytecode spans more than one fold"
    return merged, frame


def wrap_clean_metrics(runner, theta, tag, seed):
    """Record clean test-fold metrics from the same scorers the attack will use."""
    original = runner.fit_fold_models
    from authguard7702.features import normalize_bytecode

    def wrapped(frame, features, token_store, y, folds, fold, seed_arg, device, args):
        scorers, policies, test_idx = original(
            frame, features, token_store, y, folds, fold, seed_arg, device, args)
        hexes = [normalize_bytecode(frame["runtime_bytecode"].iloc[int(i)])
                 for i in test_idx]
        y_test = y[test_idx].astype(int)
        sids = frame["sample_id"].astype(str).to_numpy()[test_idx]
        fams = frame["family_id"].astype(str).to_numpy()[test_idx]
        for name, scorer in scorers.items():
            scores = np.asarray(scorer.score_hexes(hexes), dtype=float)
            thr = policies[name].threshold_05
            pos = y_test == 1
            neg = ~pos
            # Per-observation clean predictions: required for the paired clean contrast
            # (family-clustered bootstrap needs observation-level scores, not summaries).
            PREDICTION_ROWS.extend(
                dict(theta=theta, seed=seed, fold=int(fold), model=name, sid=sids[i],
                     family_id=fams[i], label=int(y_test[i]), score=float(scores[i]),
                     threshold_05=float(thr))
                for i in range(len(scores)))
            CLEAN_ROWS.append(dict(
                theta=theta, tag=tag, seed=seed, fold=int(fold), model=name,
                n_test=int(len(y_test)), n_positive=int(pos.sum()),
                n_negative=int(neg.sum()),
                n_test_families=int(pd.unique(
                    frame["family_id"].to_numpy()[test_idx]).size),
                AUPRC=float(average_precision_score(y_test, scores)),
                AUROC=float(roc_auc_score(y_test, scores)),
                Brier=float(np.mean((scores - y_test) ** 2)),
                threshold_05=float(thr),
                recall_at_5pct_nominal_fpr=float((scores[pos] >= thr).mean()),
                realized_fpr_at_threshold=float((scores[neg] >= thr).mean()),
                positive_rate=float(pos.mean())))
        return scorers, policies, test_idx

    runner.fit_fold_models = wrapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theta", type=float, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    tag = f"theta{int(round(args.theta * 100)):03d}"
    runner = _load("run_adaptive_attacks_v2", RUNNER)
    tierb = _load("run_rq4_tierb", TIERB)

    # ---- Tier-B action restriction, verified exactly as in the RQ4 replication ----
    audit = tierb.restrict(runner)
    checks = tierb.validate(runner, args.budget, audit)
    print("=== Tier-B action-space restriction ===")
    print(f"  before  : {audit['actions_before']}")
    print(f"  after   : {audit['actions_after']}")
    print(f"  excluded: {audit['excluded']}")
    for c in checks:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']}"
              f"{('  ' + c['detail']) if (c['detail'] and not c['passed']) else ''}")
    if not all(c["passed"] for c in checks):
        raise SystemExit("Tier-B restriction validation FAILED; not running")

    # ---- theta-specific families/folds -------------------------------------------
    bench_theta, frame_theta = theta_frames(runner, args.theta, tag)
    print(f"[theta] {tag}: {len(frame_theta)} primary rows, "
          f"{frame_theta['family_id'].nunique()} families, "
          f"{int(frame_theta['label'].sum())} source-flagged")
    runner.load_primary = lambda: (bench_theta, frame_theta)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"tierb_action_audit_{tag}_s{args.seed}.json"), "w") as fh:
        json.dump(dict(theta=args.theta, tag=tag, seed=args.seed, audit=audit,
                       checks=checks, query_budget=args.budget,
                       beam_width=runner.BEAM_WIDTH, max_depth=runner.MAX_DEPTH,
                       max_byte_overhead=runner.MAX_OVERHEAD,
                       primary_rows=int(len(frame_theta)),
                       primary_families=int(frame_theta["family_id"].nunique()),
                       primary_positives=int(frame_theta["label"].sum())), fh, indent=2)
    if args.validate_only:
        print("[theta] validate-only: not running")
        return 0

    wrap_clean_metrics(runner, args.theta, tag, args.seed)

    run_tag = f"{tag}_s{args.seed}"       # threshold- and seed-bearing: no collisions
    sys.argv = ["run_adaptive_attacks_v2.py",
                "--seeds", str(args.seed),
                "--folds", *[str(f) for f in args.folds],
                "--budget", str(args.budget),
                "--epochs", str(args.epochs),
                "--models", *MODELS,
                "--tag", run_tag]
    print(f"[theta] delegating to runner with tag={run_tag}", flush=True)
    rc = runner.main()

    clean = pd.DataFrame(CLEAN_ROWS)
    clean_path = os.path.join(OUT, f"clean_per_fold_{run_tag}.csv")
    clean.to_csv(clean_path, index=False)
    pred_path = os.path.join(OUT, f"clean_predictions_{run_tag}.csv.gz")
    pd.DataFrame(PREDICTION_ROWS).to_csv(pred_path, index=False, compression="gzip")
    print(f"[theta] wrote {clean_path}")
    print(f"[theta] wrote {pred_path} ({len(PREDICTION_ROWS)} rows)")
    print(clean[["fold", "model", "AUPRC", "AUROC", "Brier",
                 "recall_at_5pct_nominal_fpr"]].round(4).to_string(index=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
