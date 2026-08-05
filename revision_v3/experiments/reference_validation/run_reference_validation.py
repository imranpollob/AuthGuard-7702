"""authguard_reference_v3: independent reimplementation of the AuthGuard-Seq architecture,
run through the full canonical protocol and compared against the frozen Revision v2 results
(0.924 AUPRC, 0.833 Recall@5% FPR). This is the Phase 1 go/no-go gate — see
revision_v3/reports/REFERENCE_VALIDATION_REPORT.md for the acceptance decision.
"""
from __future__ import annotations

import json
import os
import sys

import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from data.loader import load_primary_dataset  # noqa: E402
from models.chunk_model import ChunkModel, ChunkModelConfig  # noqa: E402
from models.forward_fns import chunk_forward  # noqa: E402
from training.dataset import build_token_cache, chunks_array_for_spec  # noqa: E402
from training.harness import run_full_protocol  # noqa: E402
from features.encode import VOCAB_SIZE  # noqa: E402

RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results")
CHECKPOINT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "checkpoints")
V2_REFERENCE = {"auprc_mean": 0.924447943, "recall_at_5pct_mean": 0.832667663}
ACCEPTANCE = {"auprc_abs_diff_max": 0.015, "recall_5pct_abs_diff_max": 0.025}


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[reference_validation] device={device}")

    df = load_primary_dataset()
    token_cache = build_token_cache(df)
    tensors = chunks_array_for_spec(df, token_cache, chunk_size=256, max_chunks=64)

    def build_model():
        return ChunkModel(ChunkModelConfig(
            vocab_size=VOCAB_SIZE, chunk_size=256, max_chunks=64,
            embedding_dim=32, channel_dim=64, dropout=0.15, aggregation="attention",
        ))

    summary = run_full_protocol(
        model_name="authguard_reference_v3",
        build_model_fn=build_model,
        forward_fn=chunk_forward,
        tensors=tensors,
        results_dir=RESULTS_DIR,
        device=device,
        checkpoint_dir=CHECKPOINT_DIR,
    )

    auprc_diff = abs(summary["auprc_mean"] - V2_REFERENCE["auprc_mean"])
    recall_diff = abs(summary["recall_at_5pct_mean"] - V2_REFERENCE["recall_at_5pct_mean"])
    passed = (auprc_diff <= ACCEPTANCE["auprc_abs_diff_max"]
              and recall_diff <= ACCEPTANCE["recall_5pct_abs_diff_max"])

    verdict = {
        "v3_auprc_mean": summary["auprc_mean"],
        "v3_auprc_std": summary["auprc_std"],
        "v3_recall_at_5pct_mean": summary["recall_at_5pct_mean"],
        "v3_recall_at_5pct_std": summary["recall_at_5pct_std"],
        "v2_auprc_mean": V2_REFERENCE["auprc_mean"],
        "v2_recall_at_5pct_mean": V2_REFERENCE["recall_at_5pct_mean"],
        "auprc_abs_diff": auprc_diff,
        "recall_at_5pct_abs_diff": recall_diff,
        "acceptance_criteria": ACCEPTANCE,
        "PASSED": passed,
        "total_wall_seconds": summary["total_wall_seconds"],
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "reference_validation_verdict.json"), "w") as f:
        json.dump(verdict, f, indent=2)
    with open(os.path.join(RESULTS_DIR, "reference_validation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(verdict, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
