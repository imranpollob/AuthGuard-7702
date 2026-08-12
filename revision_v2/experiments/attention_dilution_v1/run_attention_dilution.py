#!/usr/bin/env python3
"""Direct mechanistic test of the attention-dilution hypothesis.

The paper argues that learned chunk attention resists bytecode flooding because it can
concentrate on the informative region regardless of how much padding surrounds it, whereas
mean pooling necessarily dilutes evidence in proportion to appended content. That claim is
so far an inference from attack-success rates. This measures it directly.

For each source contract and each flooding level, we record what fraction of the model's
attention mass falls on chunks that are entirely appended donor content. Mean pooling has
no learned weights, so its dilution is the analytic baseline: attention mass on appended
chunks equals their share of the chunk count. Any gap between the two is the mechanism.

Outputs per-row attention mass plus a summary suitable for plotting.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "attention_dilution_v1")
BENCH = os.path.join(RV2, "data", "authguardbench_7702_v2.csv.gz")
MODELS = os.path.join(RV2, "experiments", "robustness_operational_v2", "models")

sys.path.insert(0, RV2)
sys.path.insert(0, os.path.join(RV2, "experiments", "common"))
sys.path.insert(0, os.path.join(RV2, "experiments", "donor_pools"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from ag_common import normalize_bytecode  # noqa: E402
from authguard7702.features import PAD_ID, opcode_chunks  # noqa: E402
from authguard7702.model import AuthGuardFusion, FusionConfig  # noqa: E402
from frozen import verify as verify_frozen  # noqa: E402
from pools import DonorPools  # noqa: E402

CHUNK_SIZE = 256
MAX_CHUNKS = 64
FRACTIONS = [0.0, 0.25, 0.5, 1.0, 2.0]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fusion = _load("fusion_run", os.path.join(
    RV2, "experiments", "authguard_fusion", "run_authguard_fusion.py"))


def donor_frame(bench):
    keep = bench[bench["population"].isin(
        ["PRIMARY_EVALUATION", "EXTERNAL_BENIGN_CONTROL"])].copy()
    is_primary = keep["population"] == "PRIMARY_EVALUATION"
    keep["class"] = np.where(
        keep["population"] == "EXTERNAL_BENIGN_CONTROL", "benign_general",
        np.where(keep["label"] == 1, "malicious", "benign_cleared"))
    keep["bc"] = keep["runtime_bytecode"]
    keep["sid"] = keep["sample_id"].astype(str)
    keep["fold_primary"] = np.where(is_primary, keep["fold_id"], np.nan)
    keep["y"] = (keep["class"] == "malicious").astype(int)
    return keep.reset_index(drop=True)


def n_original_chunks(bytecode_hex):
    chunks, _ = opcode_chunks(bytecode_hex, CHUNK_SIZE, None)
    tokens = chunks.reshape(-1)
    return int(np.ceil(max((tokens != PAD_ID).sum(), 1) / CHUNK_SIZE))


def attention_profile(model, device, bytecode_hex, mean, scale):
    """Return (attention weights, n_chunks) for one contract."""
    chunks, _ = opcode_chunks(bytecode_hex, CHUNK_SIZE, MAX_CHUNKS)
    n = len(chunks)
    views = {
        "chunks": torch.from_numpy(chunks[None, ...]).long().to(device),
        "chunk_mask": torch.ones(1, n, dtype=torch.bool, device=device),
        "dense": torch.zeros(1, 261, device=device),
        "ngram": torch.zeros(1, 512, device=device),
    }
    with torch.no_grad():
        out = model(**views)
    weights = out["chunk_attention"].squeeze(0).detach().cpu().numpy()
    return weights[:n], n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--n-sources", type=int, default=120)
    parser.add_argument("--seed", type=int, default=7702)
    parser.add_argument("--fold", type=int, default=0)
    args = parser.parse_args()
    started = time.time()
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(OUT, exist_ok=True)
    device = torch.device(args.device)

    bench = pd.read_csv(BENCH)
    primary = bench[bench["population"] == "PRIMARY_EVALUATION"].reset_index(drop=True)
    pools = DonorPools(donor_frame(bench), "benign_general", "fold_primary",
                       "ATTENTION_DILUTION_V1")
    pools.assert_disjoint(args.fold)

    artifact = torch.load(os.path.join(
        MODELS, f"model_authguard_seq_s{args.seed}_f{args.fold}.pt"),
        map_location=device, weights_only=False)
    model = AuthGuardFusion(FusionConfig(**artifact["config"])).to(device)
    model.load_state_dict(artifact["model"])
    model.eval()
    mean = artifact["dense_mean"].numpy()
    scale = artifact["dense_scale"].numpy()

    # Held-out positives of the fold, evenly spaced so one family cannot dominate.
    test_pos = primary[(primary.fold_id == args.fold) & (primary.label == 1)]
    if len(test_pos) > args.n_sources:
        pick = np.linspace(0, len(test_pos) - 1, args.n_sources).round().astype(int)
        test_pos = test_pos.iloc[np.unique(pick)]
    print(f"[dilution] {len(test_pos)} sources, fold {args.fold}, seed {args.seed}",
          flush=True)

    rows = []
    for count, (_, source) in enumerate(test_pos.iterrows()):
        clean_hex = normalize_bytecode(source["runtime_bytecode"])
        base_chunks = n_original_chunks(clean_hex)
        row_meta = dict(sid=source["sample_id"], family_id=source["family_id"])
        for fraction in FRACTIONS:
            if fraction == 0.0:
                variant = clean_hex
            else:
                recipient = dict(sid=source["sample_id"], family_id=source["family_id"],
                                 address=source["address"], chain=source["chain"], y=1)
                flooded = pools.flood(bytearray(bytes.fromhex(clean_hex)), recipient,
                                      args.fold, "test", f"DILUTION_F{int(fraction*100)}",
                                      fraction, "attention_dilution")
                variant = normalize_bytecode(bytes(flooded).hex())
            weights, n_chunks = attention_profile(model, device, variant, mean, scale)
            # Chunks beyond the original program are entirely appended content.
            original_span = min(base_chunks, n_chunks)
            appended_share_of_chunks = 1.0 - original_span / max(n_chunks, 1)
            attention_on_appended = float(weights[original_span:].sum()) if n_chunks > original_span else 0.0
            rows.append(dict(
                **row_meta, flood_fraction=fraction, n_chunks=n_chunks,
                n_original_chunks=original_span,
                appended_chunk_share=appended_share_of_chunks,
                attention_mass_on_appended=attention_on_appended,
                attention_mass_on_original=1.0 - attention_on_appended,
                # Mean pooling weights every valid chunk equally, so its mass on appended
                # content is exactly the appended share of chunks. This is the analytic
                # comparison the ablation's chunk-mean control realises empirically.
                mean_pool_mass_on_appended=appended_share_of_chunks))
        if (count + 1) % 25 == 0:
            print(f"[dilution] {count + 1}/{len(test_pos)}", flush=True)

    frame = pd.DataFrame(rows)
    tag = f"_s{args.seed}_f{args.fold}"
    frame.to_csv(os.path.join(OUT, f"attention_dilution_per_row{tag}.csv.gz"),
                 index=False, compression="gzip")
    summary = (frame.groupby("flood_fraction")
               .agg(n=("sid", "size"),
                    appended_chunk_share=("appended_chunk_share", "mean"),
                    attention_on_appended=("attention_mass_on_appended", "mean"),
                    attention_on_appended_sd=("attention_mass_on_appended", "std"),
                    mean_pool_on_appended=("mean_pool_mass_on_appended", "mean"))
               .reset_index())
    summary["dilution_resisted"] = (summary.mean_pool_on_appended
                                    - summary.attention_on_appended)
    summary.to_csv(os.path.join(OUT, f"attention_dilution_summary{tag}.csv"), index=False)
    print(summary.round(4).to_string(index=False))

    with open(os.path.join(OUT, f"attention_dilution_results{tag}.json"), "w") as handle:
        json.dump(dict(
            seed=args.seed, fold=args.fold, n_sources=int(len(test_pos)),
            fractions=FRACTIONS,
            note=("attention_mass_on_appended is measured; mean_pool_on_appended is the "
                  "analytic value for uniform chunk weighting, equal to the appended "
                  "share of chunks"),
            summary=summary.to_dict(orient="records")), handle, indent=2)
    if verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(f"[dilution] done in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
