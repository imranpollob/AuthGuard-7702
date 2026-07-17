#!/usr/bin/env python3
"""Adaptive random/beam bytecode attacks against held-out AuthGuard models."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from search import ACTIONS, FLOOD_ACTIONS, beam_search, random_search  # noqa: E402
from harness import (load_corpus, task_arrays, feature_views, oof_threshold, featurize, SENS,
                     XGB_HP, SEED, RV2, DH, normalize_bytecode, disasm,
                     verify_frozen_or_die, write_manifest)  # noqa: E402
from pools import DonorPools, make_variant_isolated, mut  # noqa: E402

OUT = os.path.join(RV2, "results", "adaptive_attacks")
FIXED = ["M1", "M2", "M3", "F25", "F50", "F100", "F200"]
FLOODS = ["F25", "F50", "F100", "F200"]
QUERY_BUDGET = 64
BEAM_WIDTH = 4
MAX_DEPTH = 4
MAX_OVERHEAD = 2.0
NBOOT = 10_000
TARGET = "authguard_seed7702"
TRANSFER_ALT = "authguard_seed7703"
TRANSFER_HIST = "hist_ngram_seed7702"
CHECKPOINT_STATE = os.path.join(OUT, "checkpoint_state.json")
CHECKPOINT_ATTACKS = os.path.join(OUT, "checkpoint_attack_rows.csv.gz")
CHECKPOINT_QUERIES = os.path.join(OUT, "checkpoint_query_rows.csv.gz")
CHECKPOINT_THRESHOLDS = os.path.join(OUT, "checkpoint_thresholds.csv")
CHECKPOINT_DONORS = os.path.join(OUT, "checkpoint_donor_ledger.csv.gz")


def blake_text(*parts):
    return hashlib.blake2b(":".join(map(str, parts)).encode(), digest_size=12,
                           salt=SEED.to_bytes(8, "little")).hexdigest()


def make_method(columns):
    columns = list(columns)

    def fit(X, y, seed):
        model = XGBClassifier(random_state=seed, **XGB_HP)
        model.fit(X[:, columns], y)
        return model

    def score(model, X):
        return model.predict_proba(X[:, columns])[:, 1]

    return dict(fit=fit, score=score, columns=columns)


def candidate_matrix(hexes):
    dense, ngram, _ = featurize(hexes, sens=SENS)
    return np.hstack([dense, ngram]).astype(np.float32)


def safe_addr_immediate_rewrite(raw, seed_material):
    """Width-preserving PUSH20 rewrite that skips a truncated final immediate.

    Donor chunks may end at an arbitrary byte and therefore may end inside PUSH data. The frozen
    v1 helper assumes complete immediates; adaptive compositions need an explicit bounds check.
    """
    out = bytearray(raw)
    metadata_start = mut.find_metadata_split(out)
    rng = mut.det_rng("addr:" + seed_material)
    for _opcode_pc, size, start, end in mut.push_positions(out, metadata_start):
        if size == 20 and end <= len(out):
            for index in range(start, end):
                out[index] = int(rng.integers(0, 256))
    return out


def safe_selector_immediate_rewrite(raw, seed_material):
    """Width-preserving sensitive PUSH4 rewrite with truncated-tail protection."""
    out = bytearray(raw)
    metadata_start = mut.find_metadata_split(out)
    rng = mut.det_rng("sel:" + seed_material)
    for _opcode_pc, size, start, end in mut.push_positions(out, metadata_start):
        if size == 4 and end <= len(out) and out[start:end].hex() in mut.SENS:
            for index in range(start, end):
                out[index] = int(rng.integers(0, 256))
    return out


class AttackContext:
    def __init__(self, pools, row, fold):
        self.pools = pools
        self.row = dict(row)
        self.fold = int(fold)
        self.original = normalize_bytecode(self.row["bytecode"])
        self.original_bytes = mut.to_bytes(self.original)
        self.original_size = len(self.original_bytes)

    def _apply_action(self, current_hex, action, sequence):
        current = mut.to_bytes(current_hex)
        key = f"adaptive:{self.row['sid']}:{'/'.join(sequence)}"
        if action == "metadata":
            out = mut.mut_metadata(current, key)
        elif action == "address":
            out = safe_addr_immediate_rewrite(current, key)
        elif action == "selector":
            out = safe_selector_immediate_rewrite(current, key)
        elif action == "neutral25":
            want = max(2, int(max(self.original_size, 1) * 0.25))
            payload = (bytes([0x5F, 0x50]) * ((want + 1) // 2))[:want]
            out = bytearray(current) + bytearray([0x00]) + bytearray(payload)
        elif action in FLOOD_ACTIONS:
            fraction = {"flood25": 0.25, "flood50": 0.50,
                        "flood100": 1.0, "flood200": 2.0}[action]
            condition = f"ADAPT_{action}_{blake_text(*sequence)}"
            out = self.pools.flood(current, self.row, self.fold, "test", condition,
                                   fraction, "adaptive_test")
        else:
            raise ValueError(action)
        return normalize_bytecode(bytes(out).hex())

    def valid(self, candidate):
        try:
            raw = bytes.fromhex(candidate)
        except ValueError:
            return False
        overhead = (len(raw) - self.original_size) / max(self.original_size, 1)
        # A nominal F200 candidate appends 2x source bytes plus its required one-byte STOP guard.
        if len(raw) > self.original_size * (1 + MAX_OVERHEAD) + 1 or overhead < -1e-9:
            return False
        if not mut.verify_preservation(self.original, bytearray(raw)):
            return False
        ops, _, _ = disasm(candidate)
        return bool(ops) and len(candidate) % 2 == 0

    def apply_sequence(self, sequence):
        current = self.original
        for index, action in enumerate(sequence):
            current = self._apply_action(current, action, sequence[:index + 1])
        return current if self.valid(current) else None

    def apply_from_state(self, prefix, current_hex, action):
        sequence = prefix + (action,)
        candidate = self._apply_action(current_hex, action, sequence)
        return candidate if self.valid(candidate) else None

    def overhead(self, candidate):
        return (len(candidate) // 2 - self.original_size) / max(self.original_size, 1)


def fit_fold_models(X, y, groups, train, full_cols, hist_ngram_cols):
    specifications = {
        TARGET: (make_method(full_cols), SEED),
        TRANSFER_ALT: (make_method(full_cols), 7703),
        TRANSFER_HIST: (make_method(hist_ngram_cols), SEED),
    }
    fitted = {}
    thresholds = {}
    splitters = {}
    for name, (method, seed) in specifications.items():
        threshold, splitter, _ = oof_threshold(method, X[train], y[train], groups[train], seed)
        fitted[name] = method["fit"](X[train], y[train], seed)
        thresholds[name] = float(threshold)
        splitters[name] = splitter
    return specifications, fitted, thresholds, splitters


def score_models(matrix, specifications, fitted):
    return {name: method["score"](fitted[name], matrix)
            for name, (method, _seed) in specifications.items()}


def attack_row(row, fold, method, candidate, sequence, queries, first_success,
               overhead, scores, clean_scores, thresholds, structural_valid=True):
    target_clean = float(clean_scores[TARGET])
    target_adv = float(scores[TARGET])
    output = dict(
        sid=row["sid"], family_id=row["family_id"], fold=int(fold), method=method,
        sequence="+".join(sequence) if sequence else "clean_noop",
        queries=int(queries), queries_to_first_success=(None if first_success is None
                                                        else int(first_success)),
        byte_overhead=float(overhead), structural_valid=bool(structural_valid),
        candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        candidate_hex=candidate,
        clean_score=target_clean, adversarial_score=target_adv,
        threshold=float(thresholds[TARGET]), score_reduction=target_clean - target_adv,
        clean_detected=bool(target_clean >= thresholds[TARGET]),
        attack_success=bool(target_clean >= thresholds[TARGET] and
                            target_adv < thresholds[TARGET]),
        unconditional_evasion=bool(target_adv < thresholds[TARGET]))
    for label, model_name in [("alt", TRANSFER_ALT), ("hist_ngram", TRANSFER_HIST)]:
        clean = float(clean_scores[model_name]); adversarial = float(scores[model_name])
        threshold = float(thresholds[model_name])
        output.update({
            f"{label}_clean_score": clean, f"{label}_adversarial_score": adversarial,
            f"{label}_threshold": threshold,
            f"{label}_score_reduction": clean - adversarial,
            f"{label}_clean_detected": bool(clean >= threshold),
            f"{label}_transfer_success": bool(clean >= threshold and adversarial < threshold)})
    return output


def summarize_method(group):
    eligible = group[group["clean_detected"]]
    alt = group[group["alt_clean_detected"]]
    hist = group[group["hist_ngram_clean_detected"]]
    successful = eligible[eligible["attack_success"]]
    return dict(
        sources=int(len(group)), clean_detected_sources=int(len(eligible)),
        attack_successes=int(eligible["attack_success"].sum()),
        ASR=float(eligible["attack_success"].mean()) if len(eligible) else None,
        unconditional_evasion_rate=float(group["unconditional_evasion"].mean()),
        score_reduction_mean=float(group["score_reduction"].mean()),
        score_reduction_median=float(group["score_reduction"].median()),
        queries_mean=float(group["queries"].mean()),
        successful_queries_to_first_mean=(float(successful["queries_to_first_success"].mean())
                                          if len(successful) else None),
        byte_overhead_mean=float(group["byte_overhead"].mean()),
        byte_overhead_p95=float(group["byte_overhead"].quantile(0.95)),
        structural_validity_rate=float(group["structural_valid"].mean()),
        alternate_seed_transfer_ASR=(float(alt["alt_transfer_success"].mean())
                                     if len(alt) else None),
        alternate_seed_score_reduction_mean=float(group["alt_score_reduction"].mean()),
        hist_ngram_transfer_ASR=(float(hist["hist_ngram_transfer_success"].mean())
                                 if len(hist) else None),
        hist_ngram_score_reduction_mean=float(group["hist_ngram_score_reduction"].mean()))


def paired_family_bootstrap(rows, method_a, method_b):
    a = rows[rows["method"] == method_a].set_index("sid").sort_index()
    b = rows[rows["method"] == method_b].set_index("sid").loc[a.index]
    assert (a["family_id"].to_numpy() == b["family_id"].to_numpy()).all()
    eligible = a["clean_detected"].to_numpy(dtype=bool)
    families = a["family_id"].to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    family_index = {family: index for index, family in enumerate(unique)}
    row_family = np.asarray([family_index[family] for family in families])
    seed = int.from_bytes(hashlib.blake2b(
        f"{SEED}:adaptive:{method_a}:{method_b}".encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(seed)
    success_a = a["attack_success"].to_numpy(dtype=float)
    success_b = b["attack_success"].to_numpy(dtype=float)
    reduction_a = a["score_reduction"].to_numpy(dtype=float)
    reduction_b = b["score_reduction"].to_numpy(dtype=float)
    asr_delta = np.empty(NBOOT); reduction_delta = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)),
                             minlength=len(unique))
        weights = counts[row_family]
        denominator = (weights * eligible).sum()
        asr_delta[replicate] = ((weights * eligible * (success_a - success_b)).sum() /
                                denominator if denominator else np.nan)
        reduction_delta[replicate] = np.average(reduction_a - reduction_b, weights=weights)

    def summary(values, point):
        values = values[np.isfinite(values)]
        ci = [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]
        return dict(point=float(point), CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                    boot_mean=float(values.mean()), boot_std=float(values.std()),
                    replicates=int(len(values)))

    point_asr = float((success_a[eligible] - success_b[eligible]).mean())
    point_reduction = float((reduction_a - reduction_b).mean())
    return dict(ASR_delta=summary(asr_delta, point_asr),
                score_reduction_delta=summary(reduction_delta, point_reduction))


def _atomic_csv(frame, path, compression=None):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, compression=compression)
    os.replace(temporary, path)


def save_checkpoint(completed_folds, attack_rows, query_rows, threshold_rows,
                    donor_rows, leakage_lines):
    """Commit complete-fold state; the JSON marker is replaced last."""
    _atomic_csv(pd.DataFrame(attack_rows), CHECKPOINT_ATTACKS, compression="gzip")
    _atomic_csv(pd.DataFrame(query_rows), CHECKPOINT_QUERIES, compression="gzip")
    _atomic_csv(pd.DataFrame(threshold_rows), CHECKPOINT_THRESHOLDS)
    _atomic_csv(pd.DataFrame(donor_rows), CHECKPOINT_DONORS, compression="gzip")
    temporary = CHECKPOINT_STATE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(dict(completed_folds=sorted(completed_folds),
                       leakage_lines=leakage_lines,
                       attack_rows=len(attack_rows), query_rows=len(query_rows),
                       donor_rows=len(donor_rows)), handle, indent=2)
    os.replace(temporary, CHECKPOINT_STATE)


def load_checkpoint():
    if not os.path.exists(CHECKPOINT_STATE):
        return set(), [], [], [], [], []
    state = json.load(open(CHECKPOINT_STATE))
    attacks = pd.read_csv(CHECKPOINT_ATTACKS).to_dict(orient="records")
    queries = pd.read_csv(CHECKPOINT_QUERIES).to_dict(orient="records")
    thresholds = pd.read_csv(CHECKPOINT_THRESHOLDS).to_dict(orient="records")
    donors = pd.read_csv(CHECKPOINT_DONORS).to_dict(orient="records")
    assert len(attacks) == state["attack_rows"]
    assert len(queries) == state["query_rows"]
    assert len(donors) == state["donor_rows"]
    return (set(map(int, state["completed_folds"])), attacks, queries, thresholds,
            donors, list(state["leakage_lines"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from the last atomically committed complete fold")
    args = parser.parse_args()
    started = time.time()
    verify_frozen_or_die()
    os.makedirs(OUT, exist_ok=True)
    df, Xd, Xn, meta = load_corpus()
    sub, y, folds, Xds, Xns = task_arrays(df, Xd, Xn, "primary")
    sub = sub.copy(); sub["y"] = y
    X = np.hstack([Xds, Xns]).astype(np.float32)
    groups = sub["family_id"].to_numpy()
    views = feature_views(meta)
    full_cols = list(range(X.shape[1]))
    hist_ngram_cols = views["hist"] + list(range(views["n_dense"], X.shape[1]))
    pools = DonorPools(df.assign(y=(df["class"] == "malicious").astype(int)),
                       "benign_general", "outer_fold_primary", "ADAPTIVE_ATTACK")

    if args.validate_only:
        sample = sub[(sub["y"] == 1)].iloc[0]
        context = AttackContext(pools, sample.to_dict(), int(sample["outer_fold_primary"]))
        built = {action: context.apply_sequence((action,)) for action in ACTIONS}
        assert all(value is not None and context.valid(value) for value in built.values())
        composed = {}
        for flood in sorted(FLOOD_ACTIONS):
            for rewrite in ("address", "selector"):
                for sequence in ((flood, rewrite), (rewrite, flood)):
                    value = context.apply_sequence(sequence)
                    composed["+".join(sequence)] = value
                    assert value is None or context.valid(value)
        fake_score = lambda values: np.asarray([1.0 / max(len(v), 1) for v in values])
        random_best, random_queries, _ = random_search(
            context.original, 1.0, 0.5, "validate", context.apply_sequence, fake_score, budget=12)
        beam_best, beam_queries, _ = beam_search(
            context.original, 1.0, 0.5, context.apply_from_state, fake_score, budget=12)
        assert len(random_queries) <= 12 and len(beam_queries) <= 12
        assert context.valid(random_best.bytecode) and context.valid(beam_best.bytecode)
        print("[validate] actions", {k: round(context.overhead(v), 3) for k, v in built.items()})
        print("[validate] composed rewrite/flood candidates", sum(v is not None for v in composed.values()))
        print("[validate] random/beam queries", len(random_queries), len(beam_queries))
        verify_frozen_or_die()
        return

    if args.resume:
        (completed_folds, attack_rows, query_rows, threshold_rows,
         restored_donors, leakage_lines) = load_checkpoint()
        pools.ledger_rows = restored_donors
        if completed_folds:
            print(f"[resume] completed folds: {sorted(completed_folds)} | "
                  f"attack rows={len(attack_rows)} query rows={len(query_rows)}", flush=True)
    else:
        completed_folds, attack_rows, query_rows, threshold_rows, leakage_lines = \
            set(), [], [], [], []
    for fold in range(5):
        if fold in completed_folds:
            print(f"[resume] skip completed fold {fold}", flush=True)
            continue
        pools.assert_disjoint(fold)
        train = np.flatnonzero(folds != fold)
        test_mal = np.flatnonzero((folds == fold) & (y == 1))
        specifications, fitted, thresholds, splitters = fit_fold_models(
            X, y, groups, train, full_cols, hist_ngram_cols)
        for name in specifications:
            threshold_rows.append(dict(fold=fold, model=name, threshold=thresholds[name],
                                       splitter=splitters[name], train_rows=len(train)))
        clean_model_scores = score_models(X[test_mal], specifications, fitted)

        # Fixed baselines are batched per condition and later combined into strong query-charged
        # oracles. Every source remains held out and uses test-role donor pools.
        fixed_by_sid = {sub["sid"].iloc[index]: {} for index in test_mal}
        for condition in FIXED:
            hexes = [make_variant_isolated(pools, sub.iloc[index].to_dict(), fold, "test",
                                            condition, "adaptive_fixed_test")
                     for index in test_mal]
            scores_by_model = score_models(candidate_matrix(hexes), specifications, fitted)
            for position, (index, candidate) in enumerate(zip(test_mal, hexes)):
                row = sub.iloc[index]
                clean_scores = {name: clean_model_scores[name][position] for name in specifications}
                scores = {name: scores_by_model[name][position] for name in specifications}
                context = AttackContext(pools, row.to_dict(), fold)
                structural_valid = context.valid(candidate)
                record = attack_row(row, fold, condition, candidate, (condition,), 1,
                                    1 if scores[TARGET] < thresholds[TARGET] else None,
                                    context.overhead(candidate), scores, clean_scores,
                                    thresholds, structural_valid)
                attack_rows.append(record)
                fixed_by_sid[row["sid"]][condition] = record

        for position, index in enumerate(test_mal):
            row = sub.iloc[index]
            context = AttackContext(pools, row.to_dict(), fold)
            clean_scores = {name: clean_model_scores[name][position] for name in specifications}

            # Best random flooding and best fixed transform are source-wise oracle comparators.
            for oracle_name, members, queries in [
                ("random_flood_best", FLOODS, len(FLOODS)),
                ("fixed_oracle_best", FIXED, len(FIXED)),
            ]:
                selected = min((fixed_by_sid[row["sid"]][name] for name in members),
                               key=lambda item: (item["adversarial_score"], item["method"]))
                copied = dict(selected)
                copied.update(method=oracle_name, queries=queries,
                              sequence=f"selected:{selected['method']}",
                              queries_to_first_success=(queries if copied["attack_success"] else None))
                attack_rows.append(copied)

            def target_score_batch(bytecodes):
                if not bytecodes:
                    return np.asarray([], dtype=float)
                matrix = candidate_matrix(bytecodes)
                return specifications[TARGET][0]["score"](fitted[TARGET], matrix)

            random_best, random_queries, random_first = random_search(
                context.original, clean_scores[TARGET], thresholds[TARGET],
                f"{SEED}:{fold}:{row['sid']}:random", context.apply_sequence,
                target_score_batch, QUERY_BUDGET, MAX_DEPTH)
            beam_best, beam_queries, beam_first = beam_search(
                context.original, clean_scores[TARGET], thresholds[TARGET],
                context.apply_from_state, target_score_batch, QUERY_BUDGET,
                BEAM_WIDTH, MAX_DEPTH)

            for search_name, best, queried, first_success in [
                ("random_search", random_best, random_queries, random_first),
                ("beam_search", beam_best, beam_queries, beam_first),
            ]:
                best_matrix = candidate_matrix([best.bytecode])
                best_scores = {name: float(values[0]) for name, values in
                               score_models(best_matrix, specifications, fitted).items()}
                attack_rows.append(attack_row(
                    row, fold, search_name, best.bytecode, best.sequence, len(queried),
                    first_success, context.overhead(best.bytecode), best_scores,
                    clean_scores, thresholds, context.valid(best.bytecode)))
                for candidate in queried:
                    query_rows.append(dict(
                        sid=row["sid"], family_id=row["family_id"], fold=fold,
                        method=search_name, query_index=candidate.query_index,
                        sequence="+".join(candidate.sequence), score=candidate.score,
                        threshold=thresholds[TARGET],
                        byte_overhead=context.overhead(candidate.bytecode),
                        candidate_sha256=hashlib.sha256(candidate.bytecode.encode()).hexdigest()))
            if (position + 1) % 25 == 0 or position + 1 == len(test_mal):
                print(f"[adaptive fold {fold}] {position + 1}/{len(test_mal)} malicious sources",
                      flush=True)
        leakage_lines.append(
            f"fold {fold}: test sources={len(test_mal)}; train/test families disjoint=True; "
            "donor train/val/test pools family+executable-hash disjoint=True")
        completed_folds.add(fold)
        save_checkpoint(completed_folds, attack_rows, query_rows, threshold_rows,
                        pools.ledger_rows, leakage_lines)
        print(f"[checkpoint] committed fold {fold}", flush=True)

    attacks = pd.DataFrame(attack_rows)
    queries = pd.DataFrame(query_rows)
    assert attacks.groupby("method")["sid"].nunique().eq(int((y == 1).sum())).all()
    summary = {method: summarize_method(group) for method, group in attacks.groupby("method")}
    paired = {
        "beam_minus_random": paired_family_bootstrap(attacks, "beam_search", "random_search"),
        "beam_minus_fixed_oracle": paired_family_bootstrap(attacks, "beam_search",
                                                            "fixed_oracle_best"),
        "random_minus_fixed_oracle": paired_family_bootstrap(attacks, "random_search",
                                                              "fixed_oracle_best"),
    }

    attacks_path = os.path.join(OUT, "attack_per_row.csv.gz")
    queries_path = os.path.join(OUT, "attack_query_trace.csv.gz")
    threshold_path = os.path.join(OUT, "thresholds.csv")
    ledger_path = os.path.join(OUT, "donor_ledger.csv.gz")
    assertions_path = os.path.join(OUT, "leakage_assertions.txt")
    attacks.to_csv(attacks_path, index=False)
    queries.to_csv(queries_path, index=False)
    pd.DataFrame(threshold_rows).to_csv(threshold_path, index=False)
    ledger = pools.write_ledger(ledger_path)
    with open(assertions_path, "w") as handle:
        handle.write("ALL ADAPTIVE-ATTACK FAMILY/DONOR ISOLATION ASSERTIONS PASSED\n")
        handle.write("\n".join(leakage_lines) + f"\nledger rows: {len(ledger)}\n")

    payload = dict(
        protocol="revision_v2/protocols/adaptive_attack_protocol.md",
        target_model=TARGET, transfer_models=[TRANSFER_ALT, TRANSFER_HIST],
        query_budget=QUERY_BUDGET, beam_width=BEAM_WIDTH, max_depth=MAX_DEPTH,
        max_byte_overhead=MAX_OVERHEAD, fixed_comparators=FIXED,
        actions=list(ACTIONS), sources=int((y == 1).sum()),
        summary=summary, family_clustered_paired_comparisons=paired,
        bounded_execution_validation="pending run_attack_execution_audit.py",
        donor_ledger_rows=int(len(ledger)))
    results_path = os.path.join(OUT, "adaptive_attack_results.json")
    with open(results_path, "w") as handle:
        json.dump(payload, handle, indent=2)
    outputs = [results_path, attacks_path, queries_path, threshold_path, ledger_path,
               assertions_path]
    write_manifest(OUT, dict(protocol="adaptive_attack_protocol", seed=SEED,
                             query_budget=QUERY_BUDGET, beam_width=BEAM_WIDTH,
                             max_depth=MAX_DEPTH, actions=list(ACTIONS)),
                   outputs, started, inputs=[os.path.join(DH, "task_aligned_dataset_v1.csv")])
    verify_frozen_or_die()
    print(json.dumps({method: {key: value for key, value in data.items()
                              if key in ("ASR", "score_reduction_mean", "queries_mean",
                                         "byte_overhead_mean", "alternate_seed_transfer_ASR",
                                         "hist_ngram_transfer_ASR")}
                      for method, data in summary.items()}, indent=2))
    print(f"[adaptive-attacks] done in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
