#!/usr/bin/env python3
"""Temporal holdout evaluation on the live post-benchmark EIP-7702 delegate population.

The benchmark carries no timestamp, so temporal generalisation was previously untestable.
The independently collected live sweep does: 752 screenable Ethereum delegates first
observed 2026-07-23..2026-08-06, strictly later than the benchmark corpus and with zero
bytecode-hash overlap against any benchmark population.

No labels are asserted for this population. What is measured is operating-point behaviour:
the fraction of a real delegate stream that each frozen cross-validation checkpoint would
flag at its own validation-derived 1/5/10% FPR thresholds, and the same figure weighted by
observed authorisation volume, which is what a wallet actually experiences.

A leakage gate runs first: any live bytecode whose MinHash similarity to a checkpoint's
training bytecode reaches the benchmark's 0.85 family threshold would have joined a
training family, and is reported separately rather than silently scored.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "temporal_holdout_v1")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
LIVE = os.path.join(ROOT, "data", "collected_delegates", "v2_ethereum_population.csv")
MODELS = os.path.join(RV2, "experiments", "robustness_operational_v2", "models")

sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from ag_common import normalize_bytecode, disasm, minhash_signature  # noqa: E402
from authguard7702.features import encode_bytecode  # noqa: E402
from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from authguard7702.policy import WarningPolicy  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402

FAMILY_THRESHOLD = 0.85
N_PERM = 128


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fusion = _load("fusion_run", os.path.join(
    RV2, "experiments", "authguard_fusion", "run_authguard_fusion.py"))


def load_live():
    frame = pd.read_csv(LIVE)
    frame = frame[frame["retrieval_status"] == "OK"].reset_index(drop=True)
    frame["runtime_bytecode"] = frame["runtime_bytecode"].map(normalize_bytecode)
    return frame


def signatures(bytecodes):
    out = []
    for value in bytecodes:
        ops, _, _ = disasm(value)
        out.append(minhash_signature(ops, num_perm=N_PERM))
    return np.asarray(out)


def max_similarity(live_sig, train_sig, block=256):
    """Max MinHash signature agreement of each live row against any training row."""
    best = np.zeros(len(live_sig))
    for start in range(0, len(train_sig), block):
        chunk = train_sig[start:start + block]
        agree = (live_sig[:, None, :] == chunk[None, :, :]).mean(axis=2)
        best = np.maximum(best, agree.max(axis=1))
    return best


def score_with_artifact(path, bytecodes, device, batch_size=32):
    artifact = torch.load(path, map_location=device, weights_only=False)
    config = FusionConfig(**artifact["config"])
    model = AuthGuardFusion(config).to(device)
    model.load_state_dict(artifact["model"])
    model.eval()
    mean = artifact["dense_mean"].numpy()
    scale = artifact["dense_scale"].numpy()
    temperature = float(artifact["temperature"])
    stored = artifact["policy"]
    if isinstance(stored, dict):
        # WarningPolicy.to_dict() emits fpr_* keys; the constructor takes threshold_*.
        policy = WarningPolicy(threshold_01=float(stored["fpr_01"]),
                               threshold_05=float(stored["fpr_05"]),
                               threshold_10=float(stored["fpr_10"]))
    else:
        policy = stored
    chunk_size = artifact["preprocessing"]["chunk_size"]
    max_chunks = artifact["preprocessing"]["max_chunks"]

    logits = []
    with torch.no_grad():
        for start in range(0, len(bytecodes), batch_size):
            rows = [encode_bytecode(value, chunk_size, max_chunks)
                    for value in bytecodes[start:start + batch_size]]
            views = fusion._pad_views([{
                "chunks": row.chunks,
                "dense": ((row.dense - mean) / scale).astype(np.float32),
                "ngram": row.ngram.astype(np.float32),
                "auxiliary": row.auxiliary.astype(np.float32),
            } for row in rows])
            output = model(**fusion.to_device(views, device))
            logits.extend(output["risk_logit"].cpu().numpy().tolist())
    scores = fusion.probabilities(np.asarray(logits), temperature)
    return scores, policy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--skip-leakage", action="store_true")
    args = parser.parse_args()
    started = time.time()
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(OUT, exist_ok=True)
    device = torch.device(args.device)

    live = load_live()
    bench = pd.read_csv(BENCH)
    primary = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    primary["runtime_bytecode"] = primary["runtime_bytecode"].map(normalize_bytecode)
    print(f"[temporal] live={len(live)} unique_bytecode={live.bytecode_sha256.nunique()} "
          f"blocks={live.first_observed_block.min()}..{live.first_observed_block.max()}",
          flush=True)

    overlap = set(live.bytecode_sha256.str.lower()) & set(bench.bytecode_sha256.str.lower())
    print(f"[temporal] exact bytecode-hash overlap with full benchmark: {len(overlap)}",
          flush=True)

    leakage = None
    if not args.skip_leakage:
        print("[temporal] computing MinHash signatures for leakage gate...", flush=True)
        live_sig = signatures(live["runtime_bytecode"].tolist())
        train_sig = signatures(primary["runtime_bytecode"].tolist())
        best = max_similarity(live_sig, train_sig)
        live["max_minhash_sim_to_primary"] = best
        n_family_join = int((best >= FAMILY_THRESHOLD).sum())
        leakage = dict(threshold=FAMILY_THRESHOLD,
                       n_at_or_above=n_family_join,
                       fraction=float(n_family_join / len(live)),
                       max_similarity=float(best.max()),
                       median_similarity=float(np.median(best)),
                       p95_similarity=float(np.percentile(best, 95)))
        print(f"[temporal] leakage gate: {n_family_join}/{len(live)} live delegates reach "
              f"the {FAMILY_THRESHOLD} family threshold against primary training bytecode "
              f"(max sim {best.max():.3f}, median {np.median(best):.3f})", flush=True)

    clean_mask = (live["max_minhash_sim_to_primary"] < FAMILY_THRESHOLD
                  if not args.skip_leakage else np.ones(len(live), dtype=bool))
    bytecodes = live["runtime_bytecode"].tolist()
    weights = live["authorization_frequency"].to_numpy(dtype=float)

    rows = []
    artifacts = sorted(f for f in os.listdir(MODELS) if f.endswith(".pt"))
    for name in artifacts:
        # "model_authguard_seq_s7702_f0.pt" -- a plain "_s" split also matches "_seq".
        match = re.search(r"_s(\d+)_f(\d+)\.pt$", name)
        seed, fold = int(match.group(1)), int(match.group(2))
        scores, policy = score_with_artifact(os.path.join(MODELS, name), bytecodes, device)
        live[f"score_s{seed}_f{fold}"] = scores
        for label, threshold in (("01", policy.threshold_01), ("05", policy.threshold_05),
                                 ("10", policy.threshold_10)):
            flagged = scores >= threshold
            rows.append(dict(
                seed=seed, fold=fold, operating_point=label, threshold=float(threshold),
                n=len(scores),
                flag_rate=float(flagged.mean()),
                flag_rate_leakage_clean=float(flagged[clean_mask].mean()),
                flag_rate_authorization_weighted=float(
                    (weights * flagged).sum() / weights.sum()),
                alerts_per_1000_authorizations=float(
                    1000.0 * (weights * flagged).sum() / weights.sum()),
                mean_score=float(scores.mean()), median_score=float(np.median(scores))))
        print(f"[temporal] {name}: flag@5%={rows[-2]['flag_rate']:.3f} "
              f"weighted={rows[-2]['flag_rate_authorization_weighted']:.3f}", flush=True)

    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(OUT, "temporal_flag_rates.csv"), index=False)
    live.to_csv(os.path.join(OUT, "temporal_live_scores.csv.gz"), index=False,
                compression="gzip")

    summary = {}
    for label, group in table.groupby("operating_point"):
        per_seed = group.groupby("seed")[
            ["flag_rate", "flag_rate_leakage_clean",
             "flag_rate_authorization_weighted"]].mean()
        summary[label] = {
            column: dict(mean=float(per_seed[column].mean()),
                         sd=float(per_seed[column].std(ddof=0)))
            for column in per_seed.columns}
    payload = dict(
        population="live Ethereum EIP-7702 delegates, blocks 25595134-25695421",
        window_utc="2026-07-23T11:27:59Z..2026-08-06T10:50:47Z",
        n_screenable=int(len(live)),
        n_unique_bytecode=int(live.bytecode_sha256.nunique()),
        exact_bytecode_overlap_with_benchmark=len(overlap),
        leakage_gate=leakage, artifacts=len(artifacts),
        note=("No labels are asserted for this population; these are operating-point "
              "transfer statistics, not detection metrics."),
        summary=summary)
    with open(os.path.join(OUT, "temporal_holdout_results.json"), "w") as handle:
        json.dump(payload, handle, indent=2)
    print(json.dumps(summary, indent=2))
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(f"[temporal] done in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
