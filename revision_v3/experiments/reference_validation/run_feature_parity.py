"""Standalone feature-parity check (v3 independent pipeline vs. frozen v2 pipeline),
200 sampled canonical contracts. Writes revision_v3/results/feature_parity_report.json.
Imports revision_v2 code read-only, as a comparison oracle only.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v2"))

from features.encode import encode_bytecode as v3_encode  # noqa: E402
from data.loader import load_primary_dataset  # noqa: E402

N_SAMPLE = 200
SEED = 7702
RESULTS_PATH = os.path.join(REPO_ROOT, "revision_v3", "results", "feature_parity_report.json")


def main() -> int:
    from authguard7702 import features as v2_features

    df = load_primary_dataset()
    sample = df.sample(n=N_SAMPLE, random_state=SEED).reset_index(drop=True)

    token_matches = 0
    opcode_count_matches = 0
    dense_max_abs = 0.0
    ngram_max_abs = 0.0
    mismatches = []

    for _, row in sample.iterrows():
        bc = row["runtime_bytecode"]
        v3_enc = v3_encode(bc, chunk_size=256, max_chunks=None)
        v2_enc = v2_features.encode_bytecode(bc, chunk_size=256, max_chunks=None)
        v2_ops, _, _ = v2_features.disasm(v2_features.normalize_bytecode(bc))
        v3_ops = v3_enc.tokens

        tok_match = (v2_ops == v3_ops)
        token_matches += int(tok_match)
        opcode_count_matches += int(len(v2_ops) == len(v3_ops))

        d_diff = float(np.max(np.abs(v3_enc.dense - v2_enc.dense)))
        n_diff = float(np.max(np.abs(v3_enc.ngram - v2_enc.ngram)))
        dense_max_abs = max(dense_max_abs, d_diff)
        ngram_max_abs = max(ngram_max_abs, n_diff)

        if not tok_match:
            mismatches.append({
                "sample_id": row["sample_id"],
                "v2_n_ops": len(v2_ops),
                "v3_n_ops": len(v3_ops),
            })

    n = len(sample)
    results = {
        "n_sample": n,
        "sample_seed": SEED,
        "token_sequence_equality_rate": token_matches / n,
        "opcode_count_equality_rate": opcode_count_matches / n,
        "dense_feature_max_abs_diff": dense_max_abs,
        "ngram_feature_max_abs_diff": ngram_max_abs,
        "intentional_differences": [
            "v3 UNK_xx opcode names, module layout, and code structure are independently "
            "written (see revision_v3/src/features/); v3 reuses the same public EVM "
            "opcode->mnemonic mapping and the same PUSH1..PUSH32-collapse rule required for "
            "the model's own token vocabulary, and the same blake2b-seeded hashing scheme "
            "required for 4-gram feature identity. No source file was copied.",
        ],
        "mismatches": mismatches,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps({k: v for k, v in results.items() if k not in ("mismatches",)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
