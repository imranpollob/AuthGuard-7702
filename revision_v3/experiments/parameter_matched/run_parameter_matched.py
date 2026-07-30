"""Phase 2, Part 2: trains the parameter-matched Flat CNN at 3 token budgets under the
identical canonical protocol used for every Phase 1 model. Writes to
revision_v3/results/parameter_matched/ (Phase 1 outputs untouched).
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
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "parameter_matched"))

from data.loader import load_primary_dataset  # noqa: E402
from training.dataset import build_token_cache, flat_array_for_spec  # noqa: E402
from training.harness import run_full_protocol  # noqa: E402
from model_specs import PARAMETER_MATCHED_SPECS  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "parameter_matched")
CHECKPOINT_DIR = os.path.join(RESULTS_DIR, "checkpoints")
LOG_PATH = os.path.join(REPO_ROOT, "revision_v3", "logs", "parameter_matched_progress.jsonl")


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[parameter_matched] device={device}", flush=True)

    df = load_primary_dataset()
    token_cache = build_token_cache(df)

    summaries = []
    for spec in PARAMETER_MATCHED_SPECS:
        fold_seed_path = os.path.join(RESULTS_DIR, f"{spec['name']}_fold_seed.csv")
        if os.path.exists(fold_seed_path) and len(pd.read_csv(fold_seed_path)) == 15:
            print(f"[parameter_matched] {spec['name']} already complete -- skipping", flush=True)
            continue
        t0 = time.time()
        tensors = flat_array_for_spec(df, token_cache, spec["budget"])
        print(f"[parameter_matched] training {spec['name']} ...", flush=True)
        summary = run_full_protocol(
            model_name=spec["name"], build_model_fn=spec["build"], forward_fn=spec["forward"],
            tensors=tensors, results_dir=RESULTS_DIR, device=device, checkpoint_dir=CHECKPOINT_DIR,
        )
        summary["wall_seconds_this_model"] = time.time() - t0
        summaries.append(summary)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(summary) + "\n")
        print(f"[parameter_matched] {spec['name']}: AUPRC={summary['auprc_mean']:.4f}"
              f" Recall@5%={summary['recall_at_5pct_mean']:.4f} ({summary['wall_seconds_this_model']:.1f}s)", flush=True)

    # rebuild complete summary from all fold_seed files (robust to partial/resumed runs)
    all_rows = []
    for spec in PARAMETER_MATCHED_SPECS:
        fs = pd.read_csv(os.path.join(RESULTS_DIR, f"{spec['name']}_fold_seed.csv"))
        metric_cols = [c for c in fs.columns if c not in
                       ("model", "seed", "test_fold", "val_fold", "n_train", "n_val", "n_test", "wall_seconds")]
        per_seed = fs.groupby("seed")[metric_cols].mean()
        row = {"model": spec["name"]}
        for col in metric_cols:
            row[f"{col}_mean"] = float(per_seed[col].mean())
            row[f"{col}_std"] = float(per_seed[col].std(ddof=1))
        all_rows.append(row)
    pd.DataFrame(all_rows).to_csv(os.path.join(RESULTS_DIR, "parameter_matched_summary.csv"), index=False)

    fold_seed_frames = [pd.read_csv(os.path.join(RESULTS_DIR, f"{s['name']}_fold_seed.csv")) for s in PARAMETER_MATCHED_SPECS]
    pred_frames = [pd.read_csv(os.path.join(RESULTS_DIR, f"{s['name']}_predictions.csv.gz")) for s in PARAMETER_MATCHED_SPECS]
    pd.concat(fold_seed_frames, ignore_index=True).to_csv(os.path.join(RESULTS_DIR, "parameter_matched_fold_seed.csv"), index=False)
    pd.concat(pred_frames, ignore_index=True).to_csv(os.path.join(RESULTS_DIR, "parameter_matched_predictions.csv.gz"), index=False, compression="gzip")

    print("[parameter_matched] ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
