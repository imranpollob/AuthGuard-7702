"""Simulate the final Gold-Test analysis using provisional labels as an oracle.

This is a planning diagnostic, not human evidence. It cannot write the annotation database,
agreement reports, scoring lock, or any human-final evaluation artifact. The provisional labels
were produced with static-analyzer evidence visible and therefore do not satisfy the blinded,
independent review protocol.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from analysis.dcrg_feature_groups import FEATURE_GROUPS  # noqa: E402
from evaluate_against_human_labels import (  # noqa: E402
    evaluate_dcrg_ablation_predictions,
    evaluate_dcrg_predictions,
)
from evaluation.gold_test_provenance import (  # noqa: E402
    validate_gold_test_scoring_provenance,
)

LABELS = os.path.join(V3, "results", "llm_provisional_opus5", "gold_test_labels.json")
MANIFEST = os.path.join(V3, "human_eval", "gold_test_manifest.csv")
FUSION = os.path.join(V3, "results", "human_final", "gold_test_frozen_predictions.csv.gz")
ABLATION = os.path.join(
    V3, "results", "human_final", "gold_test_frozen_ablation_predictions.csv.gz"
)
LOCK = os.path.join(V3, "results", "human_final", "gold_test_scoring_lock.json")
OUT_DIR = os.path.join(V3, "results", "what_if_current_labels_as_human")
OUTPUT = os.path.join(OUT_DIR, "current_label_oracle_what_if.json")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_proxy_labels() -> pd.DataFrame:
    with open(LABELS) as handle:
        payload = json.load(handle)
    if payload.get("LABEL_SOURCE") != "LLM_PROVISIONAL_OPUS5":
        raise ValueError("unexpected proxy-label source")
    if payload.get("STATUS") != "PROVISIONAL_PENDING_HUMAN_REVIEW":
        raise ValueError("proxy labels are not the expected provisional artifact")
    frame = pd.DataFrame(payload.get("records", []))
    required = {
        "item_id", "llm_provisional_label", "llm_provisional_confidence",
        "source_rule_label", "human_final_label", "human_review_status",
    }
    if missing := required - set(frame.columns):
        raise ValueError(f"proxy label artifact is missing columns: {sorted(missing)}")
    if len(frame) != 150 or frame["item_id"].duplicated().any():
        raise ValueError("proxy labels do not cover exactly 150 unique Gold-Test items")
    if frame["human_final_label"].fillna("").astype(str).str.strip().ne("").any():
        raise ValueError("human-final labels already exist; this pre-review diagnostic is invalid")
    if set(frame["human_review_status"].astype(str)) != {"NOT_REVIEWED"}:
        raise ValueError("some proxy items have already entered human review")
    allowed = {"SAFE", "UNSAFE", "UNCERTAIN"}
    if unknown := set(frame["llm_provisional_label"].astype(str)) - allowed:
        raise ValueError(f"unknown proxy labels: {sorted(unknown)}")
    return frame


def human_view(proxy: pd.DataFrame, uncertain_assignment: int | None) -> pd.DataFrame:
    labels = proxy["llm_provisional_label"].map({"SAFE": 0, "UNSAFE": 1})
    if uncertain_assignment is not None:
        labels = labels.fillna(uncertain_assignment)
    return pd.DataFrame({
        "item_id": proxy["item_id"].astype(str),
        "binary_label": labels,
        "excluded_from_binary": labels.isna(),
    })


def mean_seed_auprc_deltas(
    human: pd.DataFrame,
    fusion: pd.DataFrame,
    ablation: pd.DataFrame,
) -> dict:
    binary = human[~human["excluded_from_binary"]][["item_id", "binary_label"]]
    fusion_eval = fusion.merge(
        binary, left_on="sample_id", right_on="item_id", validate="many_to_one"
    )
    ablation_eval = ablation.merge(
        binary, left_on="sample_id", right_on="item_id", validate="many_to_one"
    )
    model_columns = {
        "sequence": "sequence_score",
        "dcrg_full": "dcrg_score",
        "fusion": "fusion_score",
    }
    means = {
        name: float(np.mean([
            average_precision_score(rows["binary_label"], rows[column])
            for _, rows in fusion_eval.groupby("seed")
        ]))
        for name, column in model_columns.items()
    }
    for model, rows in ablation_eval.groupby("model"):
        means[str(model)] = float(np.mean([
            average_precision_score(seed_rows["binary_label"], seed_rows["score"])
            for _, seed_rows in rows.groupby("seed")
        ]))
    return {
        "mean_seed_auprc": means,
        "deltas": {
            "fusion_minus_sequence": means["fusion"] - means["sequence"],
            "fusion_minus_dcrg_full": means["fusion"] - means["dcrg_full"],
            **{
                f"dcrg_full_minus_{baseline}": means["dcrg_full"] - means[baseline]
                for baseline in FEATURE_GROUPS if baseline != "dcrg_full"
            },
        },
    }


def _support_decisions(report: dict) -> dict[str, dict]:
    decisions = {}
    for comparison in report["paired_family_bootstrap"]:
        interval = comparison["auprc"]
        lower = float(interval["ci_low"])
        upper = float(interval["ci_high"])
        decisions[comparison["baseline"]] = {
            "mean_delta": float(interval["point_delta"]),
            "ci_95": [lower, upper],
            "supports_full_dcrg_superiority": lower > 0,
            "supports_equivalence": False,
            "interpretation": (
                "SUPPORTED_DIRECTIONALLY" if lower > 0
                else "NOT_SUPPORTED_BY_TWO_SIDED_95PCT_INTERVAL"
            ),
        }
    return decisions


def main() -> int:
    proxy = load_proxy_labels()
    fusion, ablation, scoring_provenance = validate_gold_test_scoring_provenance(
        manifest_path=MANIFEST,
        fusion_predictions_path=FUSION,
        ablation_predictions_path=ABLATION,
        lock_path=LOCK,
        artifact_root=REPO_ROOT,
    )
    proxy_human = human_view(proxy, uncertain_assignment=None)
    dcrg_report = evaluate_dcrg_predictions(
        proxy_human, fusion, bootstrap_replicates=10000
    )
    ablation_report = evaluate_dcrg_ablation_predictions(
        proxy_human, ablation, bootstrap_replicates=10000
    )
    sensitivity = {
        "exclude_uncertain": mean_seed_auprc_deltas(proxy_human, fusion, ablation),
        "all_uncertain_as_bounded_negative": mean_seed_auprc_deltas(
            human_view(proxy, uncertain_assignment=0), fusion, ablation
        ),
        "all_uncertain_as_unsafe": mean_seed_auprc_deltas(
            human_view(proxy, uncertain_assignment=1), fusion, ablation
        ),
    }
    counts = proxy["llm_provisional_label"].value_counts().sort_index().to_dict()
    binary_proxy = proxy[proxy["llm_provisional_label"].isin({"SAFE", "UNSAFE"})]
    source_positive = binary_proxy["source_rule_label"].astype(str).isin({"1", "positive"})
    proxy_positive = binary_proxy["llm_provisional_label"].eq("UNSAFE")
    output = {
        "status": "WHAT_IF_ONLY_NOT_HUMAN_EVIDENCE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assumption": (
            "Treat SAFE/UNSAFE provisional Opus-5 labels as final binary human labels and "
            "exclude UNCERTAIN exactly as an indeterminate human outcome."
        ),
        "fatal_validity_warning": (
            "The proxy reviewers saw static-analyzer evidence and are not independent humans. "
            "These results forecast a possible endpoint but cannot support submission claims."
        ),
        "label_counts": {str(key): int(value) for key, value in counts.items()},
        "n_binary": int(len(binary_proxy)),
        "n_excluded_uncertain": int((proxy["llm_provisional_label"] == "UNCERTAIN").sum()),
        "binary_proxy_source_rule_agreement": float((source_positive == proxy_positive).mean()),
        "scoring_provenance": scoring_provenance,
        "fusion_and_selective_evaluation": dcrg_report,
        "dcrg_representation_ablation": ablation_report,
        "dcrg_novelty_support": _support_decisions(ablation_report),
        "uncertain_label_sensitivity": sensitivity,
        "artifact_sha256": {
            "proxy_labels": sha256_file(LABELS),
            "gold_test_scoring_lock": sha256_file(LOCK),
            "frozen_fusion": sha256_file(FUSION),
            "frozen_ablation": sha256_file(ABLATION),
        },
        "submission_decision_rule": (
            "Proceed to real blinded review only if the proxy endpoint supports at least one "
            "DCRG-specific contribution and the conclusion is not reversed by plausible handling "
            "of uncertain items. Never report this what-if as human evaluation."
        ),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUTPUT, "w") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
    print(json.dumps(output, indent=2, sort_keys=True))
    print(f"wrote {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
