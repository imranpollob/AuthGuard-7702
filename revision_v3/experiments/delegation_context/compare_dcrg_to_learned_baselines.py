#!/usr/bin/env python3
"""Compare full DCRG to frozen sequence and classical bytecode baselines."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from evaluation.bootstrap_v2 import seed_aware_paired_bootstrap_ci  # noqa: E402
from evaluation.metrics import auprc  # noqa: E402


def model_frame(path: str, model: str, score: str, *, model_filter: str | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if model_filter is not None:
        frame = frame[frame["model"] == model_filter]
    return frame[["seed", "sample_id", score]].rename(columns={score: "score"}).assign(model=model)


def evaluate(long: pd.DataFrame, metadata: pd.DataFrame, status: str) -> dict:
    models = sorted(long["model"].unique())
    arrays = {}
    for model in models:
        frame = long[long["model"] == model]
        pivot = frame.pivot(index="sample_id", columns="seed", values="score").sort_index()
        pivot = pivot.loc[metadata.index]
        if pivot.isna().any().any():
            raise ValueError(f"missing prediction for {model}")
        arrays[model] = {
            int(seed): pivot[seed].to_numpy(dtype=np.float64) for seed in pivot.columns
        }
    labels = metadata["label"].to_numpy(dtype=np.int64)
    families = metadata["family_id"].to_numpy()
    means = {
        model: float(np.mean([auprc(labels, scores) for scores in seeds.values()]))
        for model, seeds in arrays.items()
    }
    comparisons = []
    for baseline in models:
        if baseline == "dcrg_full":
            continue
        comparisons.append({
            "candidate": "dcrg_full", "baseline": baseline,
            "auprc": seed_aware_paired_bootstrap_ci(
                family_ids=families, y_true=labels,
                scores_a_by_seed=arrays["dcrg_full"], scores_b_by_seed=arrays[baseline],
                metric_fn=auprc, n_replicates=10000, seed=77032026,
            ),
        })
    return {"status": status, "mean_seed_auprc": means, "paired_family_bootstrap": comparisons}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dcrg", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--classical", required=True)
    parser.add_argument("--proxy-labels", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    dcrg_raw = pd.read_csv(args.dcrg)
    dcrg_full = dcrg_raw[dcrg_raw["model"] == "dcrg_full"]
    metadata = (
        dcrg_full[["sample_id", "family_id", "label"]].drop_duplicates("sample_id")
        .set_index("sample_id").sort_index()
    )
    long = pd.concat([
        model_frame(args.dcrg, "dcrg_full", "score", model_filter="dcrg_full"),
        model_frame(args.sequence, "sequence", "calibrated_score"),
        model_frame(args.classical, "hist_ngram_xgb", "calibrated_score",
                    model_filter="hist_ngram_xgb"),
    ], ignore_index=True)
    inherited = evaluate(long, metadata, "INHERITED_LABEL_BASELINE_COMPARISON")

    payload = json.load(open(args.proxy_labels))
    proxy = pd.DataFrame(payload["records"])
    proxy = proxy[proxy["llm_provisional_label"].isin({"SAFE", "UNSAFE"})].copy()
    label_map = proxy.set_index("item_id")["llm_provisional_label"].map(
        {"SAFE": 0, "UNSAFE": 1}
    )
    proxy_metadata = metadata.loc[sorted(label_map.index)].copy()
    proxy_metadata["label"] = label_map.loc[proxy_metadata.index].astype(int)
    proxy_result = evaluate(
        long[long["sample_id"].isin(proxy_metadata.index)], proxy_metadata,
        "DEVELOPMENT_ONLY_CURRENT_LABEL_PROXY_BASELINE_COMPARISON",
    )
    output = {
        "status": "MIXED_EVIDENCE_BASELINE_COMPARISON",
        "inherited_labels": inherited,
        "current_label_proxy": proxy_result,
        "fatal_validity_warning": (
            "The proxy-label comparison is development-only and cannot become final evidence. "
            "The inherited labels are not independent semantic judgments."
        ),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
