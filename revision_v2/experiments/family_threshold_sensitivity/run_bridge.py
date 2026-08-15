#!/usr/bin/env python3
"""Bridge condition: theta=0.85 evaluated on the FROZEN benchmark fold_id.

The frozen benchmark's family_id is already the theta=0.85 assignment (verified: 0 of
2,190 rows differ from the recomputed theta=0.85 families), so this entry point performs
NO data patching whatsoever -- it calls the unmodified runner, which reads the frozen
fold_id and family_id straight from revision_v2/data/authguardbench_7702_v2.csv.gz.

The single intended difference from the theta=0.85 sensitivity run is therefore exact:

    regenerated theta=0.85 folds  ->  frozen benchmark fold_id

Tier-B restriction is applied through the same wrapper used by the RQ4 Tier-B replication
and the sensitivity runs, so the action space is identical. Clean metrics are recorded
internally from the same trained scorers (not the focus of this bridge).
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
OUT = os.path.join(RV2, "results", "family_threshold_sensitivity_bridge")
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


def verify_input(frame):
    """Step 1 checks, re-asserted inside the run against what the runner actually loaded."""
    split = pd.read_csv(os.path.join(RV2, "results", "family_threshold_sensitivity",
                                     "split_manifest_theta085.csv"))
    fam085 = dict(zip(split.sample_id, split.family_id_theta))
    rec = frame.sample_id.map(fam085).astype(str)
    checks = dict(
        primary_rows=int(len(frame)),
        source_flagged=int((frame.label == 1).sum()),
        unflagged=int((frame.label == 0).sum()),
        families=int(frame.family_id.nunique()),
        folds=sorted(int(v) for v in frame.fold_id.unique()),
        families_spanning_folds=int(
            frame.groupby("family_id").fold_id.nunique().gt(1).sum()),
        exact_bytecode_groups=int(frame.bytecode_sha256.nunique()),
        exact_groups_spanning_folds=int(
            frame.groupby("bytecode_sha256").fold_id.nunique().gt(1).sum()),
        family_ids_match_theta085=bool((rec == frame.family_id.astype(str)).all()),
        fold_source="frozen benchmark fold_id, unmodified")
    expect = dict(primary_rows=2190, source_flagged=727, unflagged=1463, families=790,
                  families_spanning_folds=0, exact_groups_spanning_folds=0,
                  family_ids_match_theta085=True)
    bad = {k: (checks[k], v) for k, v in expect.items() if checks[k] != v}
    if bad:
        raise SystemExit(f"bridge input verification FAILED: {bad}")
    return checks


def wrap_clean_metrics(runner, seed):
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
            PREDICTION_ROWS.extend(
                dict(seed=seed, fold=int(fold), model=name, sid=sids[i],
                     family_id=fams[i], label=int(y_test[i]), score=float(scores[i]),
                     threshold_05=float(thr))
                for i in range(len(scores)))
            CLEAN_ROWS.append(dict(
                condition="bridge_frozen_folds", seed=seed, fold=int(fold), model=name,
                n_test=int(len(y_test)), n_positive=int(pos.sum()),
                AUPRC=float(average_precision_score(y_test, scores)),
                AUROC=float(roc_auc_score(y_test, scores)),
                Brier=float(np.mean((scores - y_test) ** 2)),
                threshold_05=float(thr),
                recall_at_5pct_nominal_fpr=float((scores[pos] >= thr).mean()),
                realized_fpr_at_threshold=float((scores[~pos] >= thr).mean())))
        return scorers, policies, test_idx

    runner.fit_fold_models = wrapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    runner = _load("run_adaptive_attacks_v2", RUNNER)
    tierb = _load("run_rq4_tierb", TIERB)

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

    # No patching: the runner reads the frozen benchmark directly.
    _, frame = runner.load_primary()
    verified = verify_input(frame)
    print("=== bridge input verification ===")
    for k, v in verified.items():
        print(f"  {k}: {v}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"bridge_audit_s{args.seed}.json"), "w") as fh:
        json.dump(dict(seed=args.seed, audit=audit, checks=checks,
                       input_verification=verified, query_budget=args.budget,
                       beam_width=runner.BEAM_WIDTH, max_depth=runner.MAX_DEPTH,
                       max_byte_overhead=runner.MAX_OVERHEAD,
                       load_primary_patched=False), fh, indent=2)
    if args.validate_only:
        print("[bridge] validate-only: not running")
        return 0

    wrap_clean_metrics(runner, args.seed)
    tag = f"bridge085_s{args.seed}"
    sys.argv = ["run_adaptive_attacks_v2.py",
                "--seeds", str(args.seed),
                "--folds", *[str(f) for f in args.folds],
                "--budget", str(args.budget),
                "--epochs", str(args.epochs),
                "--models", *MODELS,
                "--tag", tag]
    print(f"[bridge] delegating to runner with tag={tag}", flush=True)
    rc = runner.main()

    pd.DataFrame(CLEAN_ROWS).to_csv(
        os.path.join(OUT, f"bridge_clean_per_fold_s{args.seed}.csv"), index=False)
    pd.DataFrame(PREDICTION_ROWS).to_csv(
        os.path.join(OUT, f"bridge_clean_predictions_s{args.seed}.csv.gz"),
        index=False, compression="gzip")
    print(f"[bridge] wrote clean artifacts for seed {args.seed}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
