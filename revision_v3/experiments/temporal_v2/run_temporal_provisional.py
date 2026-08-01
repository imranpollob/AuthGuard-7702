"""Part 12: builds a provisional temporal evaluation sample from the real (partial, still
running in background at the time this was run) Part 11 collection, prioritizing previously
unseen families, high-usage delegates, multiple chains, and varied code sizes, enriches each
sampled delegate with the same evidence pipeline used for Gold-Dev/Gold-Test, generates
provisional labels with the same protocol, and evaluates the frozen provisional model plus
authguard_sequence_dense against them. Temporal data is NOT used for training anywhere in
this pipeline.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/temporal_v2/run_temporal_provisional.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "excel_review"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "llm_provisional"))

import evidence_pipeline as ep  # noqa: E402
from generate_provisional_labels import label_item  # noqa: E402
from evaluation import model_runtime  # noqa: E402
from evaluation.metrics_extra import expected_calibration_error  # noqa: E402
from evaluation.metrics import auprc, auroc  # noqa: E402
from temporal.rpc_client import ChainClient  # noqa: E402

RAW_DIR = os.path.join(REPO_ROOT, "revision_v3", "temporal", "raw")
ENRICHED_DIR = os.path.join(REPO_ROOT, "revision_v3", "temporal", "enriched")
OUT_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "temporal")
os.makedirs(OUT_DIR, exist_ok=True)

SOURCES = [
    ("ethereum", os.path.join(RAW_DIR, "v2_window_ethereum_authorizations.csv"),
     os.path.join(ENRICHED_DIR, "v2_window_ethereum_enriched.csv")),
    ("bnb", os.path.join(RAW_DIR, "pilot_v2_bnb_authorizations.csv"),
     os.path.join(ENRICHED_DIR, "pilot_v2_bnb_enriched.csv")),
]
MAX_SAMPLE = 40


def build_sample() -> pd.DataFrame:
    frames = []
    for chain, raw_path, enriched_path in SOURCES:
        if not (os.path.exists(raw_path) and os.path.exists(enriched_path)):
            continue
        raw = pd.read_csv(raw_path)
        usage = raw["delegate_address"].str.lower().value_counts().rename("authorization_count")
        enriched = pd.read_csv(enriched_path)
        enriched = enriched.join(usage, on="address")
        enriched["authorization_count"] = enriched["authorization_count"].fillna(0).astype(int)
        enriched["chain"] = chain
        frames.append(enriched)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["fetch_error"].isna()]

    unseen = combined[combined["is_previously_unseen_family"]].sort_values("authorization_count", ascending=False)
    seen = combined[~combined["is_previously_unseen_family"]].sort_values("authorization_count", ascending=False)

    n_unseen = min(len(unseen), int(MAX_SAMPLE * 0.7))
    n_seen = min(len(seen), MAX_SAMPLE - n_unseen)
    sample = pd.concat([unseen.head(n_unseen), seen.head(n_seen)])
    return sample.reset_index(drop=True)


def main() -> int:
    sample = build_sample()
    print(f"[temporal_provisional] sample size: {len(sample)}")
    if len(sample) == 0:
        print("[temporal_provisional] no enriched temporal data available yet; nothing to do")
        with open(os.path.join(OUT_DIR, "temporal_report.json"), "w") as f:
            json.dump({"LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
                       "n_items": 0, "note": "collection incomplete at time of this pipeline pass"}, f, indent=2)
        return 0

    ep.init_selector_cache(os.path.join(OUT_DIR, "_selector_cache.json"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    records = []
    bytecodes = {}
    evidence_dir = os.path.join(OUT_DIR, "code_evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    for _, row in sample.iterrows():
        chain, address = row["chain"], row["address"]
        item_id = f"{chain}:{address}"
        print(f"[temporal_provisional] enriching {item_id} (unseen_family={row['is_previously_unseen_family']}, "
              f"authorizations={row['authorization_count']})", flush=True)
        client = ChainClient(chain)
        code = client.get_code(address)
        if not code or code == "0x":
            continue
        bytecodes[item_id] = code

        result = ep.enrich_item(chain, address, code)
        folder = os.path.join(evidence_dir, item_id.replace(":", "_"))
        os.makedirs(os.path.join(folder, "decompiled"), exist_ok=True)
        with open(os.path.join(folder, "verification_status.json"), "w") as f:
            json.dump(result["verification"], f, indent=2, default=str)
        with open(os.path.join(folder, "decompiled", "guard_trace.json"), "w") as f:
            json.dump(result["guard_trace"], f, indent=2)
        with open(os.path.join(folder, "decompiled", "functions.json"), "w") as f:
            json.dump({"dispatched_functions": result["analysis"]["functions"]}, f, indent=2)

        item_evidence = {
            "verification": result["verification"],
            "guard_trace_summary": {
                "overall_status": result["guard_trace"]["overall_status"],
                "any_sensitive_open": result["guard_trace"]["any_sensitive_open"],
                "any_ambiguous": result["guard_trace"]["any_ambiguous"],
                "per_function": [
                    {k: v for k, v in fn.items() if k in
                     ("selector", "resolved_signature", "bytecode_offset", "guard_status",
                      "guard_opcode", "guard_constant", "state_mutability")}
                    for fn in result["guard_trace"]["per_function"]
                ],
            },
            "structural": {
                "n_dispatched_functions": len(result["analysis"]["functions"]),
                "has_delegatecall": result["analysis"]["has_delegatecall"],
                "has_selfdestruct": result["analysis"]["has_selfdestruct"],
                "has_create": result["analysis"]["has_create"],
                "runtime_bytecode_length_bytes": result["analysis"]["runtime_bytecode_length_bytes"],
            },
            "implementation": result.get("implementation"),
        }
        rec = label_item(item_id, chain, address, item_evidence)
        rec.update({
            "chain": chain, "address": address,
            "is_previously_unseen_family": bool(row["is_previously_unseen_family"]),
            "is_exact_historical_duplicate": bool(row["is_exact_historical_duplicate"]),
            "authorization_count": int(row["authorization_count"]),
            "code_bytes": int(row["code_bytes"]),
        })
        records.append(rec)
    ep.save_selector_cache()

    with open(os.path.join(OUT_DIR, "temporal_labels.json"), "w") as f:
        json.dump({"LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
                   "n_items": len(records), "records": records}, f, indent=2, default=str)

    binary_ids = [r["item_id"] for r in records if r["llm_provisional_label"] in ("SAFE", "UNSAFE")]
    y_true = np.array([1 if r["llm_provisional_label"] == "UNSAFE" else 0
                        for r in records if r["item_id"] in binary_ids])
    bc_list = [bytecodes[iid] for iid in binary_ids]

    eval_report = {"LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
                    "n_total_temporal_items": len(records),
                    "n_previously_unseen_family": sum(1 for r in records if r["is_previously_unseen_family"]),
                    "n_exact_historical_duplicate": sum(1 for r in records if r["is_exact_historical_duplicate"]),
                    "n_uncertain": sum(1 for r in records if r["llm_provisional_label"] == "UNCERTAIN"),
                    "n_evaluated_binary": len(binary_ids), "models": {}}

    if len(binary_ids) >= 5 and len(np.unique(y_true)) > 1:
        for model_name in ["authguard_sequence_dense"]:
            scores_by_seed = model_runtime.score_dataset_with_ensemble(model_name, bc_list, device=device)
            point_scores = np.mean(list(scores_by_seed.values()), axis=0)
            eval_report["models"][model_name] = {
                "auprc": auprc(y_true, point_scores), "auroc": auroc(y_true, point_scores),
                "calibration_error": expected_calibration_error(y_true, point_scores),
                "n_evaluated": len(binary_ids),
            }
    else:
        eval_report["note"] = "Sample too small or single-class for a meaningful AUPRC/AUROC estimate; reporting counts only."

    with open(os.path.join(OUT_DIR, "temporal_report.json"), "w") as f:
        json.dump(eval_report, f, indent=2, default=str)

    from collections import Counter
    print(f"\n[temporal_provisional] {len(records)} items enriched+labeled")
    print("  label distribution:", Counter(r["llm_provisional_label"] for r in records))
    print(f"  unseen families: {eval_report['n_previously_unseen_family']}/{len(records)}")
    if eval_report["models"]:
        for name, m in eval_report["models"].items():
            print(f"  {name}: AUPRC={m['auprc']:.3f} AUROC={m['auroc']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
