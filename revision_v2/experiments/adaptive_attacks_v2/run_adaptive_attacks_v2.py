#!/usr/bin/env python3
"""Query-budgeted adaptive bytecode attacks against every v2 model family.

Extends revision_v2/experiments/adaptive_attacks/ (which targets only the feature-based
model on the v1 corpus) to the corrected AuthGuardBench-7702 v2 primary task and to the
neural screeners, so attack-success rate is measured per architecture under one protocol.

Protocol per outer fold f: validation = (f+1) mod 5, training = the other three folds.
Temperature scaling and the nominal 5% FPR operating point are fit on validation only.
Attack sources are the held-out positives of fold f. Flooding donors come from the
external benign control through partition-isolated pools; a donor never shares the
recipient's bytecode family.

Each model is attacked as the target in turn (score-guided beam search plus seeded random
search under an identical query budget), and every target's best candidate is additionally
scored by the other models to give transfer rates.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "adaptive_attacks_v2")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")

sys.path.insert(0, HERE)
sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(RV2, "experiments", "donor_pools"))
sys.path.insert(0, os.path.join(RV2, "experiments", "adaptive_attacks"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves annotations via sys.modules[cls.__module__].
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fusion = _load("fusion_run", os.path.join(
    RV2, "experiments", "authguard_fusion", "run_authguard_fusion.py"))
sanity = _load("run_sanity_v2", os.path.join(RV2, "audit", "scripts", "run_sanity_v2.py"))
baseline = _load("run_baseline_v2", os.path.join(
    RV2, "experiments", "baseline_v2", "run_baseline_v2.py"))

from ag_common import normalize_bytecode, disasm  # noqa: E402
from authguard7702.model import FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402
from pools import DonorPools, make_variant_isolated, mut  # noqa: E402
from search import ACTIONS, FLOOD_ACTIONS, beam_search, random_search  # noqa: E402
from ag_features import featurize, build_sensitive_selector_set  # noqa: E402
from scorers import (AuthGuardSeqScorer, ControlledCNNScorer,  # noqa: E402
                     EmulatorLogRegScorer, FlatCNNScorer, HistNgramXGBScorer,
                     logit_from_proba, tokens_of)
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

SENS = build_sensitive_selector_set()
SEED = 7702
SEEDS = [7702, 7703, 7704]
QUERY_BUDGET = 64
BEAM_WIDTH = 4
MAX_DEPTH = 4
MAX_OVERHEAD = 2.0
FIXED = ["M1", "M2", "M3", "F25", "F50", "F100", "F200"]
FLOODS = ["F25", "F50", "F100", "F200"]
MODELS = ["authguard_seq", "flat_cnn", "hist_ngram_xgb"]
NBOOT = 10_000
EXPERIMENT_ID = "ADAPTIVE_ATTACK_V2"


def blake_text(*parts):
    return hashlib.blake2b(":".join(map(str, parts)).encode(), digest_size=12,
                           salt=SEED.to_bytes(8, "little")).hexdigest()


# ------------------------------------------------------------------ candidate construction
def safe_addr_immediate_rewrite(raw, seed_material):
    """Width-preserving PUSH20 rewrite that skips a truncated final immediate."""
    out = bytearray(raw)
    metadata_start = mut.find_metadata_split(out)
    rng = mut.det_rng("addr:" + seed_material)
    for _pc, size, start, end in mut.push_positions(out, metadata_start):
        if size == 20 and end <= len(out):
            for index in range(start, end):
                out[index] = int(rng.integers(0, 256))
    return out


def safe_selector_immediate_rewrite(raw, seed_material):
    """Width-preserving sensitive PUSH4 rewrite with truncated-tail protection."""
    out = bytearray(raw)
    metadata_start = mut.find_metadata_split(out)
    rng = mut.det_rng("sel:" + seed_material)
    for _pc, size, start, end in mut.push_positions(out, metadata_start):
        if size == 4 and end <= len(out) and out[start:end].hex() in mut.SENS:
            for index in range(start, end):
                out[index] = int(rng.integers(0, 256))
    return out


class AttackContext:
    """Applies action sequences to one source and enforces the validity budget."""

    def __init__(self, pools, row, fold):
        self.pools = pools
        self.row = dict(row)
        self.fold = int(fold)
        self.original = normalize_bytecode(self.row["bytecode"])
        self.original_bytes = mut.to_bytes(self.original)
        self.original_size = len(self.original_bytes)

    def _apply_action(self, current_hex, action, sequence):
        current = mut.to_bytes(current_hex)
        key = f"adaptive_v2:{self.row['sid']}:{'/'.join(sequence)}"
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
            condition = f"ADAPTV2_{action}_{blake_text(*sequence)}"
            out = self.pools.flood(current, self.row, self.fold, "test", condition,
                                   fraction, "adaptive_v2_test")
        else:
            raise ValueError(action)
        return normalize_bytecode(bytes(out).hex())

    def valid(self, candidate):
        try:
            raw = bytes.fromhex(candidate)
        except ValueError:
            return False
        overhead = (len(raw) - self.original_size) / max(self.original_size, 1)
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


# ----------------------------------------------------------------------------- data setup
def load_primary():
    bench = pd.read_csv(BENCH)
    frame = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    assert not frame["bytecode_repaired"].any()
    assert len(frame) == 2190 and int(frame["label"].sum()) == 727
    return bench, frame


def donor_frame(bench):
    """Shim giving DonorPools the v1 column names over the v2 corpus.

    Recipient partitions follow the v2 primary `fold_id`; donors are the external benign
    control, whose families fall back to their stored `outer_fold_secondary`.
    """
    keep = bench[bench["population"].isin(
        ["PRIMARY_EVALUATION", "EXTERNAL_BENIGN_CONTROL"])].copy()
    is_primary = keep["population"] == "PRIMARY_EVALUATION"
    keep["class"] = np.where(
        keep["population"] == "EXTERNAL_BENIGN_CONTROL", "benign_general",
        np.where(keep["label"] == 1, "malicious", "benign_cleared"))
    keep["bc"] = keep["runtime_bytecode"]
    keep["bytecode"] = keep["runtime_bytecode"]
    keep["sid"] = keep["sample_id"].astype(str)
    keep["fold_primary"] = np.where(is_primary, keep["fold_id"], np.nan)
    keep["y"] = (keep["class"] == "malicious").astype(int)
    return keep.reset_index(drop=True)


ablation = _load("long_context_v3", os.path.join(
    RV2, "experiments", "long_context_ablation_v3", "run_long_context_ablation_v3.py"))

# Parameter-matched controls from the mechanism ablation, so the same variants can be
# attacked adaptively rather than only under fixed transformations.
CONTROLLED_SPECS = {
    "flat_control_16384": ("flat", 16_384),
    "chunk_mean_16384": ("mean", 16_384),
    "chunk_attention_16384": ("attention", 16_384),
}
AUG_FRACTIONS = ["F25", "F50", "F100", "F200"]


class ExtendedTokenStore:
    """Token store over the corpus plus appended augmented rows."""

    def __init__(self, base, extra_tokens, extra_auxiliary):
        self.base = base
        self.extra = list(extra_tokens)
        self.n_base = len(base.offsets) - 1
        self.auxiliary = np.vstack([base.auxiliary, np.asarray(extra_auxiliary)])

    def row(self, index):
        index = int(index)
        return (self.base.row(index) if index < self.n_base
                else self.extra[index - self.n_base])


def augmentation_variants(frame, indices, pools, fold, sids, families, y):
    """One flooded variant per training row, drawn only from train-role donor pools.

    Fractions are cycled deterministically so the augmented set spans the flooding range
    rather than a single magnitude, which gives the augmented baseline its strongest form.
    """
    hexes = []
    for position, index in enumerate(indices):
        source = frame.iloc[int(index)]
        row = dict(sid=sids[index], family_id=families[index],
                   address=source["address"], chain=source["chain"],
                   bytecode=source["runtime_bytecode"], y=int(y[index]))
        condition = AUG_FRACTIONS[position % len(AUG_FRACTIONS)]
        hexes.append(make_variant_isolated(pools, row, fold, "train", condition,
                                           "adaptive_v2_augment"))
    return hexes


_EMULATOR_CACHE = {}


def emulator_feature_matrix(frame):
    """15-feature rule-emulator matrix for the corpus, built once per process.

    CFG reconstruction is the expensive part, so this is cached rather than recomputed
    for every outer fold.
    """
    key = id(frame)
    if key not in _EMULATOR_CACHE:
        sys.path.insert(0, os.path.join(RV2, "experiments", "gate_0a_rule_emulator"))
        import emulator_features
        hexes = [normalize_bytecode(b) for b in frame["runtime_bytecode"]]
        _EMULATOR_CACHE[key] = emulator_features.featurize(hexes)
    return _EMULATOR_CACHE[key]


def build_pools(bench):
    pools = DonorPools(donor_frame(bench), "benign_general", "fold_primary", EXPERIMENT_ID)
    return pools


# -------------------------------------------------------------------------- model fitting
def _controlled_batches(indices, store, labels, aggregation, budget, batch_size,
                        shuffle, rng):
    """Yield padded chunk batches for the parameter-matched controls."""
    order = np.array(indices, dtype=int)
    if shuffle:
        order = order[rng.permutation(len(order))]
    spec = ablation.SPECS[{"flat": "flat_control_16384",
                           "mean": "chunk_mean_control_16384",
                           "attention": "chunk_attention_control_16384"}[aggregation]]
    for start in range(0, len(order), batch_size):
        picked = order[start:start + batch_size]
        rows = [ablation.select_representation(store.row(int(i)), spec) for i in picked]
        width = max(r.shape[1] for r in rows)
        depth = max(len(r) for r in rows)
        chunks = np.full((len(rows), depth, width), 0, dtype=np.int64)
        mask = np.zeros((len(rows), depth), dtype=bool)
        for i, r in enumerate(rows):
            chunks[i, :len(r), :r.shape[1]] = r
            mask[i, :len(r)] = True
        yield (picked, torch.from_numpy(chunks).long(), torch.from_numpy(mask).bool(),
               torch.tensor([float(labels[int(i)]) for i in picked], dtype=torch.float32))


def train_controlled(aggregation, budget, store, labels, train_idx, val_idx, device,
                     seed, epochs, patience=5, batch_size=16):
    """Train a parameter-matched ablation control under the shared protocol."""
    ablation.set_seed(seed)
    model = ablation.ControlledSequenceCNN(aggregation).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    pos_weight = float((labels[train_idx] == 0).sum() /
                       max((labels[train_idx] == 1).sum(), 1))
    loss_fn = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], device=device, dtype=torch.float32))
    rng = np.random.default_rng(seed)

    def infer(indices):
        model.eval()
        out_idx, out_y, out_logit = [], [], []
        with torch.no_grad():
            for picked, chunks, mask, lab in _controlled_batches(
                    indices, store, labels, aggregation, budget, 32, False, rng):
                logits = model(chunks=chunks.to(device), chunk_mask=mask.to(device),
                               dense=None, ngram=None)["risk_logit"]
                out_idx.extend(picked.tolist())
                out_y.extend(lab.tolist())
                out_logit.extend(logits.cpu().numpy().tolist())
        return np.asarray(out_y), np.asarray(out_logit)

    best_ap, best_state, stale = -np.inf, None, 0
    for _epoch in range(1, epochs + 1):
        model.train()
        for _picked, chunks, mask, lab in _controlled_batches(
                train_idx, store, labels, aggregation, budget, batch_size, True, rng):
            logits = model(chunks=chunks.to(device), chunk_mask=mask.to(device),
                           dense=None, ngram=None)["risk_logit"]
            loss = loss_fn(logits, lab.to(device))
            if not torch.isfinite(loss):
                raise FloatingPointError("non-finite loss in controlled variant")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        y_val, val_logits = infer(val_idx)
        from sklearn.metrics import average_precision_score
        ap = float(average_precision_score(y_val, val_logits))
        if ap > best_ap + 1e-5:
            best_ap, stale = ap, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    y_val, val_logits = infer(val_idx)
    return model, val_logits, y_val


def fit_fold_models(frame, features, token_store, y, folds, fold, seed, device, args):
    """Train the three architectures on one outer fold and calibrate on validation only."""
    val_fold = (fold + 1) % 5
    train_idx = np.flatnonzero((folds != fold) & (folds != val_fold))
    val_idx = np.flatnonzero(folds == val_fold)
    test_idx = np.flatnonzero(folds == fold)
    Xd, Xn = features["dense"], features["ngram"]
    mean = Xd[train_idx].mean(0)
    scale = Xd[train_idx].std(0)
    scale[scale < 1e-6] = 1.0
    pos_weight = float((y[train_idx] == 0).sum() / max((y[train_idx] == 1).sum(), 1))
    source_indices = np.arange(len(frame))
    scorers, policies = {}, {}

    # Flooding-augmented training arrays, built once per fold if any model requests them.
    aug = None
    if any(name.endswith("_aug") for name in args.models):
        aug_hexes = augmentation_variants(frame, train_idx, args.pools, fold,
                                          args.sids, args.families, y)
        aug_tokens = [tokens_of(h) for h in aug_hexes]
        aug_dense, aug_ngram, _ = featurize(aug_hexes, sens=SENS)
        aug_aux = np.zeros((len(aug_hexes), token_store.auxiliary.shape[1]),
                           dtype=np.float32)
        n_base = len(frame)
        aug = dict(
            hexes=aug_hexes,
            y=np.concatenate([y, y[train_idx]]),
            Xd=np.vstack([Xd, aug_dense.astype(np.float32)]),
            Xn=np.vstack([Xn, aug_ngram.astype(np.float32)]),
            store=ExtendedTokenStore(token_store, aug_tokens, aug_aux),
            train_idx=np.concatenate([train_idx,
                                      np.arange(n_base, n_base + len(aug_hexes))]),
            source_indices=np.arange(n_base + len(aug_hexes)))
        print(f"[adaptive-v2] fold {fold}: augmented training set "
              f"{len(train_idx)} -> {len(aug['train_idx'])} rows", flush=True)

    for name in args.models:
        augmented = name.endswith("_aug")
        base_name = name[:-4] if augmented else name
        a = aug if augmented else None
        A_y = a["y"] if a else y
        A_Xd = a["Xd"] if a else Xd
        A_Xn = a["Xn"] if a else Xn
        A_store = a["store"] if a else token_store
        A_train = a["train_idx"] if a else train_idx
        A_src = a["source_indices"] if a else source_indices
        A_rows = len(A_y)

        if base_name in CONTROLLED_SPECS:
            aggregation, budget = CONTROLLED_SPECS[base_name]
            net, val_logits, y_val = train_controlled(
                aggregation, budget, A_store, A_y, A_train, val_idx, device,
                seed + fold, args.epochs)
            temperature = fusion.fit_temperature(val_logits, y_val)
            scorers[name] = ControlledCNNScorer(
                net, device, temperature,
                "flat" if aggregation == "flat" else "chunk", budget, name)
        elif base_name == "authguard_seq":
            config = replace(FusionConfig(), active_views=(True, False, False))
            loaders = [fusion.make_loaders(idx, A_src, A_store, A_Xd, A_Xn, A_y,
                                           mean, scale, 256, 64, 16, shuffle=shuffle)
                       for idx, shuffle in ((A_train, True), (val_idx, False))]
            net, _, _ = fusion.train_model(config, loaders[0], loaders[1], device,
                                           seed + fold, args.epochs, 5, 1e-3, 0.0, 0.0)
            _, y_val, val_logits, _, _ = fusion.predict_logits(net, loaders[1], device)
            temperature = fusion.fit_temperature(val_logits, y_val)
            scorers[name] = AuthGuardSeqScorer(net, device, temperature)
        elif base_name == "flat_cnn":
            matrix, lengths = baseline.build_flat_matrix(A_store, A_rows, 2048)
            train_loader = baseline.flat_loader(A_train, matrix, lengths, A_y, 32, True)
            val_loader = baseline.flat_loader(val_idx, matrix, lengths, A_y, 32, False)
            net, _ = baseline.train_flat(baseline.FLAT_CTORS["flat_cnn"], train_loader,
                                         val_loader, device, seed + fold, pos_weight)
            _, y_val, val_logits = baseline.predict_flat(net, val_loader, device)
            temperature = fusion.fit_temperature(val_logits, y_val)
            scorers[name] = FlatCNNScorer(net, device, temperature)
        elif base_name == "emulator_logreg":
            emulator_matrix = emulator_feature_matrix(frame)
            if a is not None:
                import emulator_features
                emulator_matrix = np.vstack([
                    emulator_matrix, emulator_features.featurize(a["hexes"])])
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(penalty="l2", C=1.0, max_iter=5000,
                                   random_state=seed, class_weight="balanced"))
            model.fit(emulator_matrix[A_train], A_y[A_train])
            val_logits = logit_from_proba(model.predict_proba(emulator_matrix[val_idx])[:, 1])
            y_val = A_y[val_idx]
            temperature = fusion.fit_temperature(val_logits, y_val)
            scorers[name] = EmulatorLogRegScorer(model, temperature)
        elif base_name == "hist_ngram_xgb":
            hist_ngram = np.hstack([A_Xd[:, :225], A_Xn]).astype(np.float32)
            model = XGBClassifier(random_state=seed, **fusion.XGB_HP)
            model.fit(hist_ngram[A_train], A_y[A_train])
            val_logits = logit_from_proba(model.predict_proba(hist_ngram[val_idx])[:, 1])
            y_val = A_y[val_idx]
            temperature = fusion.fit_temperature(val_logits, y_val)
            scorers[name] = HistNgramXGBScorer(model, temperature)
        else:
            raise ValueError(name)
        val_probs = fusion.probabilities(val_logits, scorers[name].temperature)
        policies[name] = WarningPolicy.from_validation_negatives(val_probs[y_val == 0])
    return scorers, policies, test_idx


# --------------------------------------------------------------------------- attack driver
def attack_record(row, fold, seed, target, method, candidate, sequence, queries,
                  first_success, overhead, scores, clean_scores, thresholds,
                  structural_valid=True):
    clean = float(clean_scores[target])
    adversarial = float(scores[target])
    threshold = float(thresholds[target])
    record = dict(
        seed=seed, fold=int(fold), sid=row["sid"], family_id=row["family_id"],
        target_model=target, method=method,
        sequence="+".join(sequence) if sequence else "clean_noop",
        queries=int(queries),
        queries_to_first_success=None if first_success is None else int(first_success),
        byte_overhead=float(overhead), structural_valid=bool(structural_valid),
        candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        clean_score=clean, adversarial_score=adversarial, threshold=threshold,
        score_reduction=clean - adversarial,
        clean_detected=bool(clean >= threshold),
        attack_success=bool(clean >= threshold and adversarial < threshold),
        unconditional_evasion=bool(adversarial < threshold))
    for other in scores:
        if other == target:
            continue
        other_clean = float(clean_scores[other])
        other_adv = float(scores[other])
        other_threshold = float(thresholds[other])
        record.update({
            f"transfer_{other}_clean": other_clean,
            f"transfer_{other}_adversarial": other_adv,
            f"transfer_{other}_clean_detected": bool(other_clean >= other_threshold),
            f"transfer_{other}_success": bool(other_clean >= other_threshold
                                              and other_adv < other_threshold)})
    return record


def summarize(group):
    eligible = group[group["clean_detected"]]
    successful = eligible[eligible["attack_success"]]
    out = dict(
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
        structural_validity_rate=float(group["structural_valid"].mean()))
    for column in group.columns:
        if not (column.startswith("transfer_") and column.endswith("_success")):
            continue
        other = column[len("transfer_"):-len("_success")]
        detected_column = f"transfer_{other}_clean_detected"
        # A group's own model has no transfer column, so its cells are all missing.
        if detected_column not in group or group[detected_column].isna().all():
            continue
        detected = group[group[detected_column].fillna(False).astype(bool)]
        out[f"transfer_to_{other}_ASR"] = (float(detected[column].mean())
                                           if len(detected) else None)
    return out


def family_bootstrap_asr(group, seed_material):
    """Family-clustered percentile CI for a single model's ASR."""
    eligible = group[group["clean_detected"]]
    if not len(eligible):
        return None
    families = eligible["family_id"].to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([index[f] for f in families])
    success = eligible["attack_success"].to_numpy(dtype=float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        seed_material.encode(), digest_size=8).digest(), "little"))
    draws = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)),
                             minlength=len(unique))
        weights = counts[row_family]
        total = weights.sum()
        draws[replicate] = (weights * success).sum() / total if total else np.nan
    draws = draws[np.isfinite(draws)]
    return dict(point=float(success.mean()),
                CI95=[float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
                replicates=int(len(draws)))


def paired_family_bootstrap(rows, target_a, target_b, method):
    """Paired family-clustered CI on ASR difference between two targets, same sources."""
    a = rows[(rows["target_model"] == target_a) & (rows["method"] == method)]
    b = rows[(rows["target_model"] == target_b) & (rows["method"] == method)]
    a = a.set_index("sid").sort_index()
    b = b.set_index("sid").sort_index()
    shared = a.index.intersection(b.index)
    a, b = a.loc[shared], b.loc[shared]
    eligible = (a["clean_detected"].to_numpy(dtype=bool) &
                b["clean_detected"].to_numpy(dtype=bool))
    if not eligible.any():
        return None
    families = a["family_id"].to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([index[f] for f in families])
    success_a = a["attack_success"].to_numpy(dtype=float)
    success_b = b["attack_success"].to_numpy(dtype=float)
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        f"{SEED}:adaptive_v2:{target_a}:{target_b}:{method}".encode(),
        digest_size=8).digest(), "little"))
    draws = np.empty(NBOOT)
    for replicate in range(NBOOT):
        counts = np.bincount(rng.integers(0, len(unique), len(unique)),
                             minlength=len(unique))
        weights = counts[row_family] * eligible
        total = weights.sum()
        draws[replicate] = ((weights * (success_a - success_b)).sum() / total
                            if total else np.nan)
    draws = draws[np.isfinite(draws)]
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(point=float((success_a[eligible] - success_b[eligible]).mean()),
                CI95=ci, excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
                n_paired_eligible=int(eligible.sum()))


def run_fold(frame, features, token_store, y, folds, families, sids, pools,
             fold, seed, device, args, rows):
    scorers, policies, test_idx = fit_fold_models(
        frame, features, token_store, y, folds, fold, seed, device, args)
    thresholds = {name: policies[name].threshold_05 for name in scorers}
    test_positive = np.asarray([i for i in test_idx if y[i] == 1], dtype=int)
    if args.limit and args.limit < len(test_positive):
        # Evenly spaced, not the head: positives are family-ordered, so a contiguous
        # prefix is a single near-duplicate block and misrepresents the fold.
        chosen = np.linspace(0, len(test_positive) - 1, args.limit).round().astype(int)
        test_positive = test_positive[np.unique(chosen)]

    hexes = [normalize_bytecode(frame["runtime_bytecode"].iloc[int(i)]) for i in test_positive]
    clean_by_model = {name: scorers[name].score_hexes(hexes) for name in scorers}

    for position, index in enumerate(test_positive):
        source = frame.iloc[int(index)]
        row = dict(sid=sids[index], family_id=families[index],
                   address=source["address"], chain=source["chain"],
                   bytecode=source["runtime_bytecode"], y=1)
        context = AttackContext(pools, row, fold)
        clean_scores = {name: float(clean_by_model[name][position]) for name in scorers}

        fixed_candidates = {}
        for condition in FIXED:
            fixed_candidates[condition] = make_variant_isolated(
                pools, row, fold, "test", condition, "adaptive_v2_fixed_test")
        fixed_scores = {name: scorers[name].score_hexes(list(fixed_candidates.values()))
                        for name in scorers}

        for target in args.models:
            for offset, (condition, candidate) in enumerate(fixed_candidates.items()):
                scores = {name: float(fixed_scores[name][offset]) for name in scorers}
                rows.append(attack_record(
                    row, fold, seed, target, condition, candidate, (condition,), 1,
                    1 if scores[target] < thresholds[target] else None,
                    context.overhead(candidate), scores, clean_scores, thresholds,
                    context.valid(candidate)))

            best_fixed = min(FIXED, key=lambda c: (fixed_scores[target][FIXED.index(c)], c))
            offset = FIXED.index(best_fixed)
            scores = {name: float(fixed_scores[name][offset]) for name in scorers}
            candidate = fixed_candidates[best_fixed]
            rows.append(attack_record(
                row, fold, seed, target, "fixed_oracle_best", candidate,
                (f"selected:{best_fixed}",), len(FIXED),
                len(FIXED) if scores[target] < thresholds[target] else None,
                context.overhead(candidate), scores, clean_scores, thresholds,
                context.valid(candidate)))

            def score_batch(bytecodes, _target=target):
                return scorers[_target].score_hexes(list(bytecodes))

            searches = [
                ("random_search", random_search(
                    context.original, clean_scores[target], thresholds[target],
                    f"{seed}:{fold}:{row['sid']}:random", context.apply_sequence,
                    score_batch, args.budget, MAX_DEPTH)),
                ("beam_search", beam_search(
                    context.original, clean_scores[target], thresholds[target],
                    context.apply_from_state, score_batch, args.budget,
                    BEAM_WIDTH, MAX_DEPTH)),
            ]
            for method, (best, queried, first_success) in searches:
                scores = {name: float(scorers[name].score_hexes([best.bytecode])[0])
                          for name in scorers}
                rows.append(attack_record(
                    row, fold, seed, target, method, best.bytecode, best.sequence,
                    len(queried), first_success, context.overhead(best.bytecode),
                    scores, clean_scores, thresholds, context.valid(best.bytecode)))

        if (position + 1) % 10 == 0 or position + 1 == len(test_positive):
            print(f"[adaptive-v2 seed={seed} fold={fold}] "
                  f"{position + 1}/{len(test_positive)} sources", flush=True)
    return thresholds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[SEED])
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--budget", type=int, default=QUERY_BUDGET)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--limit", type=int, default=0,
                        help="cap attacked sources per fold (smoke testing only)")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()

    started = time.time()
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(OUT, exist_ok=True)

    bench, frame = load_primary()
    features = sanity.build_features(frame, os.path.join(
        RV2, "experiments", "baseline_v2", "features_v2.npz"))
    token_store = sanity.LocalTokenStore(features["tokens"], features["offsets"],
                                         features["auxiliary"])
    y = frame["label"].to_numpy(dtype=int)
    folds = frame["fold_id"].to_numpy(dtype=int)
    families = frame["family_id"].astype(str).to_numpy()
    sids = frame["sample_id"].astype(str).to_numpy()
    pools = build_pools(bench)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[adaptive-v2] device={device} models={args.models} budget={args.budget}",
          flush=True)

    rows, threshold_rows = [], []
    for seed in args.seeds:
        for fold in args.folds:
            pools.assert_disjoint(fold)
            args.pools, args.sids, args.families = pools, sids, families
            thresholds = run_fold(frame, features, token_store, y, folds, families, sids,
                                  pools, fold, seed, device, args, rows)
            for name, value in thresholds.items():
                threshold_rows.append(dict(seed=seed, fold=fold, model=name,
                                           threshold_05=value))
            print(f"[adaptive-v2] fold {fold} seed {seed} done "
                  f"({time.time() - started:.0f}s elapsed)", flush=True)

    attacks = pd.DataFrame(rows)
    suffix = f"_{args.tag}" if args.tag else ""
    attacks_path = os.path.join(OUT, f"attack_per_row{suffix}.csv.gz")
    attacks.to_csv(attacks_path, index=False, compression="gzip")
    pd.DataFrame(threshold_rows).to_csv(
        os.path.join(OUT, f"thresholds{suffix}.csv"), index=False)
    ledger = pools.write_ledger(os.path.join(OUT, f"donor_ledger{suffix}.csv.gz"))

    summary = {}
    for (target, method), group in attacks.groupby(["target_model", "method"]):
        summary.setdefault(target, {})[method] = summarize(group)
    for target in args.models:
        for method in ("beam_search", "random_search", "fixed_oracle_best", "F200"):
            group = attacks[(attacks["target_model"] == target) &
                            (attacks["method"] == method)]
            if len(group):
                summary[target][method]["ASR_family_CI"] = family_bootstrap_asr(
                    group, f"{SEED}:adaptive_v2:{target}:{method}")
    paired = {}
    for method in ("beam_search", "F200"):
        for other in args.models:
            if other == "authguard_seq" or "authguard_seq" not in args.models:
                continue
            key = f"{other}_minus_authguard_seq::{method}"
            paired[key] = paired_family_bootstrap(attacks, other, "authguard_seq", method)

    payload = dict(
        protocol="adaptive_attack_v2",
        corpus="revision_v2/data/authguardbench_7702_v2.csv.gz (PRIMARY_EVALUATION)",
        operating_point="nominal 5% FPR from validation negatives",
        seeds=args.seeds, folds=args.folds, models=args.models,
        query_budget=args.budget, beam_width=BEAM_WIDTH, max_depth=MAX_DEPTH,
        max_byte_overhead=MAX_OVERHEAD, fixed_comparators=FIXED, actions=list(ACTIONS),
        sources_attacked=int(attacks["sid"].nunique()),
        donor_ledger_rows=int(len(ledger)),
        summary=summary, paired_family_clustered=paired)
    with open(os.path.join(OUT, f"adaptive_attack_v2_results{suffix}.json"), "w") as handle:
        json.dump(payload, handle, indent=2)

    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(json.dumps({target: {method: {k: data[k] for k in
                                        ("ASR", "unconditional_evasion_rate",
                                         "score_reduction_mean", "byte_overhead_mean")}
                               for method, data in methods.items()
                               if method in ("beam_search", "random_search",
                                             "fixed_oracle_best", "F200")}
                      for target, methods in summary.items()}, indent=2))
    print(f"[adaptive-v2] done in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
