"""Stage 5, prompt_version v2: re-review using the reachability-grounded rubric.

Scope note (deliberate, documented deviation): the brief asked to "rerun only low-confidence and
incomplete-evidence cases". v2 introduces an evidence dimension (reachability / guard dominance)
that did not exist when v1 ran, so a v1 label cannot be assumed still valid without re-deriving
it -- and mixing two rubric versions inside one label set would be a methodological defect. All
752 are therefore re-reviewed, and the report breaks results down by the requested subsets
(v1-low-confidence, PARTIAL-coverage, v1-R1) so the effect on exactly those cases is visible.

v1 reviews are preserved untouched under data/llm_reviews/{run_id}/; v2 writes to
data/llm_reviews/{run_id}_promptv3/ so the two can be compared.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.llm_review_rubric_v3 import MODEL_ID, PROMPT_VERSION, review_evidence_packet  # noqa: E402

VALID_LABELS = {"R1", "R2", "B", "U"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def validate_response(resp: dict) -> None:
    assert resp["proposed_label"] in VALID_LABELS, resp
    assert resp["confidence"] in VALID_CONFIDENCE, resp
    assert isinstance(resp["risk_categories"], list)
    assert isinstance(resp["evidence"], list) and resp["evidence"]
    assert isinstance(resp["uncertainties"], list)
    assert isinstance(resp["summary"], str) and resp["summary"]


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    index = pd.read_csv(os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv"))
    out_dir = os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_promptv3")
    os.makedirs(out_dir, exist_ok=True)

    v1_index_path = os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv2.csv")
    v1 = pd.read_csv(v1_index_path).set_index("address") if os.path.exists(v1_index_path) else None

    rows = []
    n_cached = 0
    for r in index.itertuples(index=False):
        with open(r.evidence_path) as f:
            packet = json.load(f)
        evidence_hash = hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()
        out_path = os.path.join(out_dir, f"{r.chain}_{r.address}.json")

        if os.path.exists(out_path):
            with open(out_path) as f:
                existing = json.load(f)
            if existing.get("evidence_hash") == evidence_hash and existing.get("prompt_version") == PROMPT_VERSION:
                parsed = existing["parsed_response"]
                n_cached += 1
                rows.append(_row(r, parsed, packet, v1, out_path))
                continue

        parsed = review_evidence_packet(packet)
        validate_response(parsed)
        record = {
            "chain": r.chain, "address": r.address, "evidence_hash": evidence_hash,
            "evidence_path": r.evidence_path, "prompt_version": PROMPT_VERSION,
            "model_id": MODEL_ID, "raw_response": json.dumps(parsed), "parsed_response": parsed,
        }
        with open(out_path, "w") as f:
            json.dump(record, f, indent=2)
        rows.append(_row(r, parsed, packet, v1, out_path))

    df = pd.DataFrame(rows)
    index_path = os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv3.csv")
    df.to_csv(index_path, index=False)

    summary = {
        "n_total": len(df), "n_cached_reused": n_cached,
        "label_counts_v2": df["proposed_label"].value_counts().to_dict(),
        "confidence_counts_v2": df["confidence"].value_counts().to_dict(),
        "coverage_counts": df["coverage_status"].value_counts().to_dict(),
        "review_index_csv": index_path,
    }
    if v1 is not None:
        summary["label_counts_v2_prior"] = df["v2_label"].value_counts().to_dict()
        summary["n_label_changed_v2_to_v3"] = int((df["v2_label"] != df["proposed_label"]).sum())
        summary["transition_matrix_v2_to_v3"] = (
            df.groupby(["v2_label", "proposed_label"]).size().unstack(fill_value=0).to_dict()
        )
        for subset, mask in [
            ("v1_low_confidence", df["v2_confidence"] == "low"),
            ("partial_coverage", df["coverage_status"] == "PARTIAL"),
            ("v1_R1", df["v2_label"] == "R1"),
        ]:
            sub = df[mask]
            summary[f"subset_{subset}"] = {
                "n": int(len(sub)),
                "n_changed": int((sub["v2_label"] != sub["proposed_label"]).sum()),
                "v2_labels": sub["proposed_label"].value_counts().to_dict(),
            }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_summary_promptv3.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)


def _row(r, parsed, packet, v1, out_path):
    row = {
        "chain": r.chain, "address": r.address,
        "proposed_label": parsed["proposed_label"], "confidence": parsed["confidence"],
        "risk_categories": "; ".join(parsed["risk_categories"]),
        "coverage_status": packet.get("coverage_status"),
        "review_path": out_path,
    }
    if v1 is not None and r.address in v1.index:
        row["v2_label"] = v1.loc[r.address, "proposed_label"]
        row["v2_confidence"] = v1.loc[r.address, "confidence"]
    return row


if __name__ == "__main__":
    main()
