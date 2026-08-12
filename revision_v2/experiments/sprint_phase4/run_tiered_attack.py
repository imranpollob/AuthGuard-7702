#!/usr/bin/env python3
"""Phase 4 — tiered adaptive attack against FROZEN regenerated checkpoints.

No training happens here. Checkpoints produced by Phase 3 are loaded and every attack
tier for a given (model, seed, fold) is evaluated against the exact same frozen weights,
so tier differences cannot be confounded by retraining.

Tiers (membership fixed by the sprint specification and the execution audit, not by code
inspection):
  A  flooding only                      -- audit-supported (100/100 preserved)
  B  flooding + metadata + neutral25    -- audit-supported plus plausible-but-weaker
  C  all eight primitives               -- full stress test, includes address/selector

Tier A permits only one flooding action, so it is evaluated as a fixed oracle over the
four flooding levels rather than being dressed up as a 64-query compositional search.
Tiers B and C run the unchanged random and beam searches at the same 64-query budget.

EVERY evaluated candidate is persisted, not only winners, together with all parameters
needed to reconstruct it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "sprint_phase4")
CKPT = os.path.join(RV2, "results", "sprint_phase3", "checkpoints")

sys.path.insert(0, os.path.join(RV2, "experiments", "adaptive_attacks_v2"))
sys.path.insert(0, os.path.join(RV2, "experiments", "adaptive_attacks"))
sys.path.insert(0, os.path.join(RV2, "experiments", "gate_0a_rule_emulator"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("run_adaptive_attacks_v2", os.path.join(
    RV2, "experiments", "adaptive_attacks_v2", "run_adaptive_attacks_v2.py"))
fusion, sanity = runner.fusion, runner.sanity
search = _load("search_mod", os.path.join(
    RV2, "experiments", "adaptive_attacks", "search.py"))

from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from scorers import (AuthGuardSeqScorer, EmulatorLogRegScorer,  # noqa: E402
                     FlatCNNScorer, HistNgramXGBScorer)

PRIMARY = ["authguard_seq", "emulator_logreg", "flat_cnn", "hist_ngram_xgb"]
FLOOD_ACTIONS = {"flood25", "flood50", "flood100", "flood200"}
TIER_ACTIONS = {
    "A": tuple(sorted(FLOOD_ACTIONS)),
    "B": ("metadata", "neutral25") + tuple(sorted(FLOOD_ACTIONS)),
    "C": search.ACTIONS,
}
FLOODS_FIXED = ["F25", "F50", "F100", "F200"]


def load_scorer(name, seed, fold, device):
    path = os.path.join(CKPT, f"{name}_s{seed}_f{fold}.pt")
    if name in ("emulator_logreg", "hist_ngram_xgb"):
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        est = payload["estimator"]
        scorer = (EmulatorLogRegScorer(est, payload["temperature"])
                  if name == "emulator_logreg"
                  else HistNgramXGBScorer(est, payload["temperature"]))
    else:
        payload = torch.load(path, map_location=device, weights_only=False)
        if name == "authguard_seq":
            from dataclasses import replace
            net = AuthGuardFusion(replace(FusionConfig(),
                                          active_views=(True, False, False)))
            net.load_state_dict(payload["state_dict"])
            scorer = AuthGuardSeqScorer(net, device, payload["temperature"])
        else:
            net = runner.baseline.FLAT_CTORS["flat_cnn"]()
            net.load_state_dict(payload["state_dict"])
            scorer = FlatCNNScorer(net, device, payload["temperature"],
                                   max_len=payload.get("max_len", 2048))
    policy = WarningPolicy(threshold_01=payload["threshold_01"],
                           threshold_05=payload["threshold_05"],
                           threshold_10=payload["threshold_10"])
    return scorer, policy, payload


class RecordingContext(runner.AttackContext):
    """AttackContext that records every candidate it builds, with its parameters."""

    def __init__(self, pools, row, fold, log):
        super().__init__(pools, row, fold)
        self.log = log
        self.ledger_mark = len(pools.ledger_rows)

    def _apply_action(self, current_hex, action, sequence):
        before = len(self.pools.ledger_rows)
        out = super()._apply_action(current_hex, action, sequence)
        donors = self.pools.ledger_rows[before:]
        self.log.append(dict(
            action=action, sequence="+".join(sequence),
            flooding_fraction=({"flood25": 0.25, "flood50": 0.5, "flood100": 1.0,
                                "flood200": 2.0}.get(action)),
            donor_families=[d["donor_family"] for d in donors] or None,
            donor_sids=[d["donor_sid"] for d in donors] or None,
            donor_segment_sha256=[d["copied_segment_sha256"] for d in donors] or None,
            byte_offsets=[d["byte_offset"] for d in donors] or None,
            byte_lengths=[d["byte_length"] for d in donors] or None,
            transformation_seed=(donors[0]["transformation_seed"] if donors else None),
            candidate_sha256=hashlib.sha256(out.encode()).hexdigest(),
            candidate_bytes=len(out) // 2))
        return out


def evaluate_source(scorer, policy, context, row, tier, seed, fold, budget,
                    clean_score, fixed_scores, query_rows, attack_rows):
    threshold = policy.threshold_05
    clean_detected = bool(clean_score >= threshold)
    actions = TIER_ACTIONS[tier]

    def record_attack(method, candidate, sequence, queries, first_success, valid):
        adv = float(scorer.score_hexes([candidate])[0]) if candidate else clean_score
        attack_rows.append(dict(
            seed=seed, fold=fold, sid=row["sid"], family_id=row["family_id"],
            target_model=scorer.name, tier=tier, method=method,
            sequence="+".join(sequence) if sequence else "clean_noop",
            queries=int(queries),
            queries_to_first_success=None if first_success is None else int(first_success),
            byte_overhead=context.overhead(candidate),
            structural_valid=bool(valid),
            candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
            clean_score=clean_score, adversarial_score=adv, threshold=threshold,
            score_reduction=clean_score - adv,
            clean_detected=clean_detected,
            attack_success=bool(clean_detected and adv < threshold),
            unconditional_evasion=bool(adv < threshold)))
        return adv

    if tier == "A":
        # Only one flooding action is permitted, so the strongest Tier-A attacker is the
        # per-source best of the four flooding levels: a fixed oracle, not a search.
        best_name = min(FLOODS_FIXED, key=lambda c: (fixed_scores[c][1], c))
        cand, sc = fixed_scores[best_name]
        attack_rows.append(dict(
            seed=seed, fold=fold, sid=row["sid"], family_id=row["family_id"],
            target_model=scorer.name, tier=tier, method="fixed_flood_oracle",
            sequence=f"selected:{best_name}", queries=len(FLOODS_FIXED),
            queries_to_first_success=(len(FLOODS_FIXED) if sc < threshold else None),
            byte_overhead=context.overhead(cand), structural_valid=context.valid(cand),
            candidate_sha256=hashlib.sha256(cand.encode()).hexdigest(),
            clean_score=clean_score, adversarial_score=sc, threshold=threshold,
            score_reduction=clean_score - sc, clean_detected=clean_detected,
            attack_success=bool(clean_detected and sc < threshold),
            unconditional_evasion=bool(sc < threshold)))
        return

    # Tiers B and C: unchanged random and beam search over the tier's action space.
    original_actions = search.ACTIONS
    search.ACTIONS = actions
    try:
        for method, fn in (("random_search", "random"), ("beam_search", "beam")):
            log = []
            ctx = RecordingContext(context.pools, row, fold, log)
            counter = {"n": 0}

            def score_batch(bytecodes):
                counter["n"] += len(bytecodes)
                return scorer.score_hexes(list(bytecodes))

            if fn == "random":
                best, queried, first = search.random_search(
                    ctx.original, clean_score, threshold,
                    f"{seed}:{fold}:{row['sid']}:random", ctx.apply_sequence,
                    score_batch, budget, runner.MAX_DEPTH)
            else:
                best, queried, first = search.beam_search(
                    ctx.original, clean_score, threshold, ctx.apply_from_state,
                    score_batch, budget, runner.BEAM_WIDTH, runner.MAX_DEPTH)
            for cand in queried:
                query_rows.append(dict(
                    seed=seed, fold=fold, sid=row["sid"], family_id=row["family_id"],
                    target_model=scorer.name, tier=tier, method=method,
                    query_index=cand.query_index, depth=len(cand.sequence),
                    sequence="+".join(cand.sequence), score=float(cand.score),
                    clean_score=clean_score, threshold=threshold,
                    structural_valid=bool(cand.structural_valid),
                    byte_overhead=ctx.overhead(cand.bytecode),
                    candidate_sha256=hashlib.sha256(cand.bytecode.encode()).hexdigest(),
                    selected_as_winner=bool(cand.bytecode == best.bytecode)))
            record_attack(method, best.bytecode, best.sequence, len(queried), first,
                          ctx.valid(best.bytecode))
            # candidate-construction parameters for exact reconstruction
            for entry in log:
                entry.update(seed=seed, fold=fold, sid=row["sid"],
                             target_model=scorer.name, tier=tier, method=method)
            query_rows.extend([])  # construction log written separately
            evaluate_source.construction.extend(log)
    finally:
        search.ACTIONS = original_actions


evaluate_source.construction = []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7702)
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--models", nargs="+", default=PRIMARY)
    parser.add_argument("--tiers", nargs="+", default=["A", "B", "C"])
    parser.add_argument("--budget", type=int, default=runner.QUERY_BUDGET)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    started = time.time()
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(OUT, exist_ok=True)

    bench, frame = runner.load_primary()
    features = sanity.build_features(frame, os.path.join(
        RV2, "experiments", "baseline_v2", "features_v2.npz"))
    y = frame["label"].to_numpy(dtype=int)
    folds = frame["fold_id"].to_numpy(dtype=int)
    families = frame["family_id"].astype(str).to_numpy()
    sids = frame["sample_id"].astype(str).to_numpy()
    pools = runner.build_pools(bench)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[phase4] device={device} seed={args.seed} tiers={args.tiers} "
          f"models={args.models}", flush=True)

    attack_rows, query_rows = [], []
    evaluate_source.construction = []
    for fold in args.folds:
        pools.assert_disjoint(fold)
        test_idx = np.flatnonzero(folds == fold)
        pos = np.asarray([i for i in test_idx if y[i] == 1], dtype=int)
        if args.limit and args.limit < len(pos):
            pick = np.linspace(0, len(pos) - 1, args.limit).round().astype(int)
            pos = pos[np.unique(pick)]
        for name in args.models:
            scorer, policy, payload = load_scorer(name, args.seed, fold, device)
            scorer.name = name
            hexes = [runner.normalize_bytecode(frame["runtime_bytecode"].iloc[int(i)])
                     for i in pos]
            clean = scorer.score_hexes(hexes)
            for position, index in enumerate(pos):
                src = frame.iloc[int(index)]
                row = dict(sid=sids[index], family_id=families[index],
                           address=src["address"], chain=src["chain"],
                           bytecode=src["runtime_bytecode"], y=1)
                ctx = runner.AttackContext(pools, row, fold)
                fixed = {}
                for cond in FLOODS_FIXED:
                    cand = runner.make_variant_isolated(
                        pools, row, fold, "test", cond, "phase4_fixed_test")
                    fixed[cond] = (cand, float(scorer.score_hexes([cand])[0]))
                for tier in args.tiers:
                    evaluate_source(scorer, policy, ctx, row, tier, args.seed, fold,
                                    args.budget, float(clean[position]), fixed,
                                    query_rows, attack_rows)
                if (position + 1) % 25 == 0:
                    print(f"[phase4 f{fold} {name}] {position + 1}/{len(pos)}", flush=True)
            print(f"[phase4] fold {fold} {name} done ({time.time() - started:.0f}s)",
                  flush=True)

    suffix = f"_s{args.seed}{('_' + args.tag) if args.tag else ''}"
    pd.DataFrame(attack_rows).to_csv(
        os.path.join(OUT, f"tiered_attack_rows{suffix}.csv.gz"),
        index=False, compression="gzip")
    pd.DataFrame(query_rows).to_csv(
        os.path.join(OUT, f"tiered_query_trace{suffix}.csv.gz"),
        index=False, compression="gzip")
    pd.DataFrame(evaluate_source.construction).to_csv(
        os.path.join(OUT, f"tiered_construction_log{suffix}.csv.gz"),
        index=False, compression="gzip")
    pools.write_ledger(os.path.join(OUT, f"tiered_donor_ledger{suffix}.csv.gz"))
    with open(os.path.join(OUT, f"tiered_run_meta{suffix}.json"), "w") as fh:
        json.dump(dict(
            phase="4 tiered attack on frozen regenerated checkpoints",
            script="revision_v2/experiments/sprint_phase4/run_tiered_attack.py",
            provenance="regenerated_experiment",
            checkpoint_dir=os.path.relpath(CKPT, RV2),
            seed=args.seed, folds=args.folds, models=args.models, tiers=args.tiers,
            budget=args.budget, tier_actions={k: list(v) for k, v in TIER_ACTIONS.items()},
            n_attack_rows=len(attack_rows), n_query_rows=len(query_rows),
            wall_seconds=time.time() - started), fh, indent=2)
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(f"[phase4] {len(attack_rows)} attack rows, {len(query_rows)} query rows "
          f"in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
