#!/usr/bin/env python3
"""Label-free audit of how often real EIP-7702 authority context changes DCRG evidence."""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.features)
    matched = frame["n_hardcoded_authority_matches"] > 0
    mismatched = frame["n_hardcoded_authority_mismatches"] > 0
    status = pd.Series("NO_FIXED_ADDRESS_GUARD", index=frame.index)
    status[matched & ~mismatched] = "AUTHORITY_MATCH_ONLY"
    status[~matched & mismatched] = "AUTHORITY_MISMATCH_ONLY"
    status[matched & mismatched] = "BOTH_MATCH_AND_MISMATCH"

    grouped = frame.groupby("bytecode_sha256").agg(
        n_pairs=("authority_address", "size"),
        n_authorities=("authority_address", "nunique"),
        match_min=("n_hardcoded_authority_matches", "min"),
        match_max=("n_hardcoded_authority_matches", "max"),
        mismatch_min=("n_hardcoded_authority_mismatches", "min"),
        mismatch_max=("n_hardcoded_authority_mismatches", "max"),
    )
    varies = (
        (grouped["match_min"] != grouped["match_max"])
        | (grouped["mismatch_min"] != grouped["mismatch_max"])
    )
    report = {
        "status": "LABEL_FREE_AUTHORITY_CONTEXT_AUDIT",
        "n_pairs": int(len(frame)),
        "n_unique_runtimes": int(frame["bytecode_sha256"].nunique()),
        "pair_guard_relation_counts": {
            str(key): int(value) for key, value in status.value_counts().sort_index().items()
        },
        "n_pairs_with_any_authority_relative_fixed_guard_evidence": int((matched | mismatched).sum()),
        "fraction_pairs_with_any_authority_relative_fixed_guard_evidence": float(
            (matched | mismatched).mean()
        ),
        "n_runtimes_observed_with_multiple_authorities": int((grouped["n_authorities"] > 1).sum()),
        "n_runtimes_whose_match_features_vary_across_observed_authorities": int(varies.sum()),
        "interpretation": (
            "Actual signer recovery makes fixed-address guard relations decidable for many "
            "pairs, but this label-free audit cannot show that they improve classification. "
            "The observed multi-authority runtimes do not vary in these aggregate match counts."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
