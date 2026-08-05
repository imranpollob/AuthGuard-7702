"""Trains all controlled ablation models (flat CNN x3 budgets, chunk mean/attention/max x
budgets) under the identical canonical protocol, then writes the combined summary/fold-seed/
predictions files required by the audit brief.
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
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "controlled_ablation"))

from data.loader import load_primary_dataset  # noqa: E402
from training.dataset import build_token_cache, chunks_array_for_spec, flat_array_for_spec  # noqa: E402
from training.harness import run_full_protocol  # noqa: E402
from model_specs import CONTROLLED_SPECS  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
CHECKPOINT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "checkpoints")
LOG_PATH = os.path.join(REPO_ROOT, "revision_v3", "logs", "controlled_ablation_progress.jsonl")


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[controlled_ablation] device={device}", flush=True)

    df = load_primary_dataset()
    token_cache = build_token_cache(df)

    tensor_cache = {}
    summaries = []

    for spec in CONTROLLED_SPECS:
        fold_seed_path = os.path.join(RESULTS_DIR, f"{spec['name']}_fold_seed.csv")
        if os.path.exists(fold_seed_path):
            existing = pd.read_csv(fold_seed_path)
            if len(existing) == 15:
                print(f"[controlled_ablation] {spec['name']} already complete (15 rows) -- skipping", flush=True)
                continue

        t0 = time.time()
        key = (spec["kind"], spec["budget"], spec.get("aggregation"))
        if spec["kind"] == "flat":
            cache_key = ("flat", spec["budget"])
            if cache_key not in tensor_cache:
                tensor_cache[cache_key] = flat_array_for_spec(df, token_cache, spec["budget"])
            tensors = tensor_cache[cache_key]
        else:
            cache_key = ("chunk", spec["max_chunks"])
            if cache_key not in tensor_cache:
                tensor_cache[cache_key] = chunks_array_for_spec(df, token_cache, 256, spec["max_chunks"])
            tensors = tensor_cache[cache_key]

        print(f"[controlled_ablation] training {spec['name']} ...", flush=True)
        summary = run_full_protocol(
            model_name=spec["name"],
            build_model_fn=spec["build"],
            forward_fn=spec["forward"],
            tensors=tensors,
            results_dir=RESULTS_DIR,
            device=device,
            checkpoint_dir=CHECKPOINT_DIR,
        )
        summary["wall_seconds_this_model"] = time.time() - t0
        summaries.append(summary)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(summary) + "\n")
        print(f"[controlled_ablation] {spec['name']}: AUPRC={summary['auprc_mean']:.4f}"
              f" Recall@5%={summary['recall_at_5pct_mean']:.4f}"
              f" ({summary['wall_seconds_this_model']:.1f}s)", flush=True)

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(os.path.join(RESULTS_DIR, "controlled_ablation_summary.csv"), index=False)

    fold_seed_frames = []
    prediction_frames = []
    for spec in CONTROLLED_SPECS:
        fold_seed_frames.append(pd.read_csv(os.path.join(RESULTS_DIR, f"{spec['name']}_fold_seed.csv")))
        prediction_frames.append(pd.read_csv(os.path.join(RESULTS_DIR, f"{spec['name']}_predictions.csv.gz")))
    pd.concat(fold_seed_frames, ignore_index=True).to_csv(
        os.path.join(RESULTS_DIR, "controlled_ablation_fold_seed.csv"), index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        os.path.join(RESULTS_DIR, "controlled_ablation_predictions.csv.gz"), index=False, compression="gzip")

    print("[controlled_ablation] ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
