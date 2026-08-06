"""Stage 5: LLM preliminary review. Loads each screenable contract's evidence package (no
labels/splits/predictions ever included -- see FORBIDDEN_FIELDS enforcement in Stage 4's
packet_builder) and produces the required structured JSON verdict. See
dataset_pipeline/lib/llm_review_rubric.py for what "sending to an LLM" means in this workflow
and why (no live Anthropic API key configured here). Cached per contract by evidence-hash: a
completed review is not regenerated unless the underlying evidence package changes.
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
from lib.llm_review_rubric import MODEL_ID, PROMPT_VERSION, review_evidence_packet  # noqa: E402

VALID_LABELS = {"R1", "R2", "B", "U"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def validate_response(resp: dict) -> None:
    assert resp["proposed_label"] in VALID_LABELS, resp
    assert resp["confidence"] in VALID_CONFIDENCE, resp
    assert isinstance(resp["risk_categories"], list)
    assert isinstance(resp["evidence"], list)
    assert isinstance(resp["uncertainties"], list)
    assert isinstance(resp["summary"], str) and resp["summary"]


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    index_path = os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv")
    index = pd.read_csv(index_path)
    out_dir = os.path.join(cfg["_resolved_paths"]["llm_reviews"], run_id)
    os.makedirs(out_dir, exist_ok=True)

    review_rows = []
    n_cached, n_new = 0, 0
    for _, r in index.iterrows():
        with open(r["evidence_path"]) as f:
            packet = json.load(f)
        evidence_hash = hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()

        out_path = os.path.join(out_dir, f"{r['chain']}_{r['address']}.json")
        if os.path.exists(out_path):
            with open(out_path) as f:
                existing = json.load(f)
            if existing.get("evidence_hash") == evidence_hash:
                n_cached += 1
                review_rows.append({
                    "chain": r["chain"], "address": r["address"],
                    "proposed_label": existing["parsed_response"]["proposed_label"],
                    "confidence": existing["parsed_response"]["confidence"],
                    "review_path": out_path,
                })
                continue

        parsed = review_evidence_packet(packet)
        validate_response(parsed)
        record = {
            "chain": r["chain"],
            "address": r["address"],
            "evidence_hash": evidence_hash,
            "evidence_path": r["evidence_path"],
            "prompt_version": PROMPT_VERSION,
            "model_id": MODEL_ID,
            "raw_response": json.dumps(parsed),
            "parsed_response": parsed,
        }
        with open(out_path, "w") as f:
            json.dump(record, f, indent=2)
        n_new += 1
        review_rows.append({
            "chain": r["chain"], "address": r["address"],
            "proposed_label": parsed["proposed_label"], "confidence": parsed["confidence"],
            "review_path": out_path,
        })

    reviews_df = pd.DataFrame(review_rows)
    reviews_index_path = os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index.csv")
    reviews_df.to_csv(reviews_index_path, index=False)

    summary = {
        "n_total": len(review_rows), "n_cached_reused": n_cached, "n_newly_reviewed": n_new,
        "label_counts": reviews_df["proposed_label"].value_counts().to_dict(),
        "confidence_counts": reviews_df["confidence"].value_counts().to_dict(),
        "reviews_index_csv": reviews_index_path,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
