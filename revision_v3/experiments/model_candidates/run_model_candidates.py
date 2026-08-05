"""Trains the exploratory model-strengthening candidates under the identical canonical
protocol (chunk_size=256, max_chunks=64 -- the full uncapped budget, since no clean contract
exceeds it) and writes the combined summary/fold-seed/predictions files.

One common predefined training configuration is used for all four candidates (per the audit
brief: model-specific hyperparameters are not tuned against test results in this pass).
"""
from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "model_candidates"))

from data.loader import load_primary_dataset  # noqa: E402
from training.dataset import build_token_cache, chunks_array_for_spec  # noqa: E402
from training.harness import run_full_protocol  # noqa: E402
from model_specs import CANDIDATE_SPECS  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
LOG_PATH = os.path.join(REPO_ROOT, "revision_v3", "logs", "model_candidates_progress.jsonl")


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[model_candidates] device={device}", flush=True)

    df = load_primary_dataset()
    token_cache = build_token_cache(df)
    tensors = chunks_array_for_spec(df, token_cache, chunk_size=256, max_chunks=64)

    summaries = []
    for spec in CANDIDATE_SPECS:
        t0 = time.time()
        print(f"[model_candidates] training {spec['name']} ...", flush=True)
        summary = run_full_protocol(
            model_name=spec["name"],
            build_model_fn=spec["build"],
            forward_fn=spec["forward"],
            tensors=tensors,
            results_dir=RESULTS_DIR,
            device=device,
        )
        summary["wall_seconds_this_model"] = time.time() - t0
        summaries.append(summary)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(summary) + "\n")
        print(f"[model_candidates] {spec['name']}: AUPRC={summary['auprc_mean']:.4f}"
              f" Recall@5%={summary['recall_at_5pct_mean']:.4f}"
              f" ({summary['wall_seconds_this_model']:.1f}s)", flush=True)

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(os.path.join(RESULTS_DIR, "model_candidate_summary.csv"), index=False)

    fold_seed_frames = [pd.read_csv(os.path.join(RESULTS_DIR, f"{s['name']}_fold_seed.csv")) for s in CANDIDATE_SPECS]
    prediction_frames = [pd.read_csv(os.path.join(RESULTS_DIR, f"{s['name']}_predictions.csv.gz")) for s in CANDIDATE_SPECS]
    pd.concat(fold_seed_frames, ignore_index=True).to_csv(
        os.path.join(RESULTS_DIR, "model_candidate_fold_seed.csv"), index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        os.path.join(RESULTS_DIR, "model_candidate_predictions.csv.gz"), index=False, compression="gzip")

    print("[model_candidates] ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
