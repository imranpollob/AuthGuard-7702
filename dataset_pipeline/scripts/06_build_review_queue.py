"""Stage 6a: build the human-review queue CSV. One row per screenable contract, with the
LLM's proposed label/confidence/summary shown for reference and blank columns for the human
reviewer to fill in. This does not perform any review itself -- it hands off to the user.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    reviews_index_path = os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index.csv")
    reviews = pd.read_csv(reviews_index_path)

    rows = []
    for _, r in reviews.iterrows():
        with open(r["review_path"]) as f:
            rec = json.load(f)
        parsed = rec["parsed_response"]
        rows.append({
            "chain": r["chain"],
            "address": r["address"],
            "evidence_path": rec["evidence_path"],
            "llm_proposed_label": parsed["proposed_label"],
            "llm_confidence": parsed["confidence"],
            "llm_risk_categories": "; ".join(parsed["risk_categories"]),
            "llm_summary": parsed["summary"],
            "llm_uncertainties": " | ".join(parsed["uncertainties"]),
            "explorer_link": None,  # filled in below from evidence packet
            "decision": "",  # ACCEPT_LLM_LABEL | CHANGE_LABEL | UNRESOLVED
            "final_label": "",  # R1 | R2 | B | U, required if CHANGE_LABEL
            "final_confidence": "",  # high | medium | low
            "corrected_risk_categories": "",
            "comment": "",
        })
        with open(rec["evidence_path"]) as f:
            packet = json.load(f)
        rows[-1]["explorer_link"] = packet.get("explorer_link")

    queue = pd.DataFrame(rows)
    out_dir = cfg["_resolved_paths"]["human_reviews"]
    os.makedirs(out_dir, exist_ok=True)
    queue_path = os.path.join(out_dir, f"{run_id}_queue.csv")
    queue.to_csv(queue_path, index=False)
    print(f"[queue] wrote {len(queue)} rows to {queue_path}")
    print("[queue] fill in decision/final_label/final_confidence/comment for each row, then run "
          "07_merge_human_reviews.py")


if __name__ == "__main__":
    main()
