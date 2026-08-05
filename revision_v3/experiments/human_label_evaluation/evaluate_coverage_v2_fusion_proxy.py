#!/usr/bin/env python3
"""Development-only proxy evaluation of coverage-v2 DCRG/sequence fusion."""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from evaluate_against_human_labels import evaluate_dcrg_predictions  # noqa: E402
from run_current_label_oracle_what_if import human_view, load_proxy_labels  # noqa: E402


PREDICTIONS = os.path.join(
    V3, "results", "delegation_context_coverage_v2", "dcrg_fusion_predictions.csv.gz"
)
OUTPUT = os.path.join(
    V3, "results", "delegation_context_coverage_v2", "fusion_proxy_what_if.json"
)


def main() -> int:
    proxy = load_proxy_labels()
    predictions = pd.read_csv(PREDICTIONS)
    output = {
        "status": "DEVELOPMENT_ONLY_CURRENT_LABEL_PROXY_NOT_FINAL_EVIDENCE",
        "fatal_validity_warning": (
            "These proxy labels have already informed development. A newly collected, untouched "
            "human-labeled test set is required for any final fusion claim."
        ),
        "assumption": "SAFE/UNSAFE provisional labels act as human-label proxy; UNCERTAIN is excluded.",
        "evaluation": evaluate_dcrg_predictions(
            human_view(proxy, None), predictions, bootstrap_replicates=10000
        ),
        "prediction_sha256": hashlib.sha256(open(PREDICTIONS, "rb").read()).hexdigest(),
    }
    with open(OUTPUT, "w") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
