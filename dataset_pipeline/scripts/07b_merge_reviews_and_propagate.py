"""Task 4 (propagation): validate completed review queues and expand one reviewed row into the
delegate addresses it speaks for.

Propagation rule -- deliberately narrow:
    A human decision propagates ONLY to contracts whose runtime bytecode SHA-256 is IDENTICAL
    to the reviewed representative. Identical runtime bytecode means the reviewed evidence is
    the same evidence, byte for byte.

    It NEVER propagates across `bytecode_family_id`. Family membership is opcode-similarity
    (Jaccard >= 0.85), and similar-but-not-identical bytecode can differ in exactly the
    constant or guard that determines the label. Family ids are carried through for
    split-disjointness only.

Every propagated row records `label_origin` = REVIEWED (the human looked at this bytecode) or
PROPAGATED_EXACT_BYTECODE (inherited from an identical-bytecode representative), so provenance
is never lost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402

VALID_DECISIONS = {"ACCEPT_LLM_LABEL", "CHANGE_LABEL", "UNRESOLVED"}
VALID_LABELS = {"R1", "R2", "B", "U"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def resolve_row(r: pd.Series) -> tuple[dict | None, str | None]:
    decision = str(r.get("decision", "")).strip()
    if decision == "":
        return None, "no decision recorded"
    if decision not in VALID_DECISIONS:
        return None, f"unknown decision {decision!r}"

    final_confidence = str(r.get("final_confidence", "")).strip()
    if decision == "ACCEPT_LLM_LABEL":
        final_label = str(r["llm_label"]).strip()
        final_confidence = final_confidence or str(r["llm_confidence"]).strip()
    elif decision == "CHANGE_LABEL":
        final_label = str(r.get("final_label", "")).strip()
        if final_label not in VALID_LABELS:
            return None, f"CHANGE_LABEL requires final_label in {sorted(VALID_LABELS)}"
        if final_confidence not in VALID_CONFIDENCE:
            return None, f"CHANGE_LABEL requires final_confidence in {sorted(VALID_CONFIDENCE)}"
    else:  # UNRESOLVED
        final_label = "U"
        final_confidence = final_confidence or "low"
    if final_confidence not in VALID_CONFIDENCE:
        return None, f"final_confidence {final_confidence!r} invalid"
    return {"final_label": final_label, "final_confidence": final_confidence, "decision": decision}, None


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    hr_dir = cfg["_resolved_paths"]["human_reviews"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--queues", nargs="*", default=[
        os.path.join(hr_dir, f"{run_id}_representative_gold_queue.csv"),
        os.path.join(hr_dir, f"{run_id}_diagnostic_queue.csv"),
    ])
    args = ap.parse_args()

    reviewed, incomplete, invalid = [], [], []
    for queue_path in args.queues:
        if not os.path.exists(queue_path):
            print(f"[merge] queue not found, skipping: {queue_path}")
            continue
        queue_name = os.path.basename(queue_path).replace(f"{run_id}_", "").replace(".csv", "")
        q = pd.read_csv(queue_path, keep_default_na=False)
        for r in q.to_dict("records"):
            resolved, err = resolve_row(pd.Series(r))
            if err == "no decision recorded":
                incomplete.append({"queue": queue_name, "review_id": r["review_id"]})
                continue
            if err:
                invalid.append({"queue": queue_name, "review_id": r["review_id"], "error": err})
                continue
            reviewed.append({
                "queue": queue_name,
                "review_id": r["review_id"],
                "representative_address": r["contract_address"],
                "exact_bytecode_hash": r["exact_bytecode_hash"],
                "bytecode_family_id": r["bytecode_family_id"],
                "represented_contract_count": int(r["represented_contract_count"]),
                "represented_addresses": r["represented_addresses"],
                "coverage_status": r["coverage_status"],
                "verified_project_name": r.get("verified_project_name", ""),
                "llm_label": r["llm_label"],
                "llm_confidence": r["llm_confidence"],
                "llm_explanation": r["llm_explanation"],
                "corrected_risk_categories": r.get("corrected_risk_categories", ""),
                "comment": r.get("comment", ""),
                **resolved,
            })

    if not reviewed:
        print(json.dumps({
            "n_reviewed_rows": 0, "n_incomplete_rows": len(incomplete), "n_invalid_rows": len(invalid),
            "message": "No completed review rows found. Fill in `decision` (and final_label/"
                       "final_confidence for CHANGE_LABEL) in the queue CSVs, then re-run.",
            "invalid_examples": invalid[:10],
        }, indent=2))
        return

    reviewed_df = pd.DataFrame(reviewed)
    dupes = reviewed_df[reviewed_df.duplicated("exact_bytecode_hash", keep=False)]
    conflicting = []
    for h, sub in dupes.groupby("exact_bytecode_hash"):
        if sub["final_label"].nunique() > 1:
            conflicting.append({"exact_bytecode_hash": h,
                                "labels": sorted(sub["final_label"].unique().tolist()),
                                "review_ids": sub["review_id"].tolist()})

    # ---- expand to one row per delegate address ----
    expanded = []
    for r in reviewed_df.to_dict("records"):
        addresses = [a for a in str(r["represented_addresses"]).split(";") if a]
        for addr in addresses:
            expanded.append({
                "address": addr,
                "exact_bytecode_hash": r["exact_bytecode_hash"],
                "bytecode_family_id": r["bytecode_family_id"],
                "final_label": r["final_label"],
                "final_confidence": r["final_confidence"],
                "human_decision": r["decision"],
                "llm_label": r["llm_label"],
                "llm_confidence": r["llm_confidence"],
                "llm_explanation": r["llm_explanation"],
                "corrected_risk_categories": r["corrected_risk_categories"],
                "comment": r["comment"],
                "coverage_status": r["coverage_status"],
                "verified_project_name": r["verified_project_name"],
                "review_id": r["review_id"],
                "review_queue": r["queue"],
                "label_origin": ("REVIEWED" if addr == r["representative_address"]
                                 else "PROPAGATED_EXACT_BYTECODE"),
                "propagated_from": r["representative_address"],
            })
    expanded_df = pd.DataFrame(expanded).drop_duplicates("address")

    out_path = os.path.join(hr_dir, f"{run_id}_completed.jsonl")
    with open(out_path, "w") as f:
        for rec in expanded_df.to_dict("records"):
            f.write(json.dumps(rec) + "\n")

    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    n_screenable = int((families["retrieval_status"] == "OK").sum())

    summary = {
        "n_reviewed_rows": int(len(reviewed_df)),
        "n_incomplete_rows": len(incomplete),
        "n_invalid_rows": len(invalid),
        "n_delegate_addresses_labeled": int(len(expanded_df)),
        "n_labeled_by_direct_review": int((expanded_df["label_origin"] == "REVIEWED").sum()),
        "n_labeled_by_exact_bytecode_propagation": int((expanded_df["label_origin"] == "PROPAGATED_EXACT_BYTECODE").sum()),
        "n_screenable_total": n_screenable,
        "coverage_of_screenable_population": round(len(expanded_df) / n_screenable, 4) if n_screenable else None,
        "final_label_counts": expanded_df["final_label"].value_counts().to_dict(),
        "decision_counts": reviewed_df["decision"].value_counts().to_dict(),
        "llm_human_agreement_rate": round(
            float((reviewed_df["llm_label"] == reviewed_df["final_label"]).mean()), 4),
        "conflicting_identical_bytecode_reviews": conflicting,
        "completed_jsonl": out_path,
        "invalid_examples": invalid[:10],
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(hr_dir, f"{run_id}_merge_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    if conflicting:
        print(f"\nWARNING: {len(conflicting)} identical-bytecode hash(es) received conflicting "
              "human labels across queues; resolve before building the gold dataset.")
    if incomplete:
        print(f"\n{len(incomplete)} rows still need a decision.")


if __name__ == "__main__":
    main()
