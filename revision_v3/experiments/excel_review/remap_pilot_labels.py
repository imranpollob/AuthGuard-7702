"""Converts the already-completed, hand-traced Pilot code-review content
(pilot_code_review_content.json, produced by careful manual disassembly reading -- higher
rigor than the automated guard-tracer used for Gold-Dev/Gold-Test) into the unified
16-field + 8-field-label-separation schema defined in LLM_PROVISIONAL_LABELING_PROTOCOL.md,
so all three sample sets (Pilot/Gold-Dev/Gold-Test) share one output format under
revision_v3/results/llm_provisional/.

Does not modify pilot_code_review_content.json or any other Phase 3A file.

Usage:
    python3 revision_v3/experiments/excel_review/remap_pilot_labels.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional")

# Old (Phase 3A/3B) reason categories -> new protocol's categories, where a closer-fitting
# new category exists (see LLM_PROVISIONAL_LABELING_PROTOCOL.md).
REASON_REMAP = {
    "ACCESS_CONTROL_APPEARS_APPROPRIATE": "ACCESS_CONTROL_APPEARS_APPROPRIATE",
    "ARBITRARY_EXTERNAL_CALL": "ARBITRARY_EXTERNAL_CALL",
    "OTHER_UNSAFE": "OTHER_UNSAFE",
    "AUTHORIZATION_SPECIFIC_MISUSE": "AUTHORIZATION_SPECIFIC_MISUSE",
}


def infer_reason_category(label: str, reasoning_text: str) -> str:
    text = reasoning_text.lower()
    if label == "SAFE":
        if "self" in text and ("caller" in text or "address()" in text.lower()):
            return "OWNER_OR_SELF_CALL_RESTRICTED"
        if "owner" in text or "gated" in text:
            return "ACCESS_CONTROL_APPEARS_APPROPRIATE"
        return "NO_CONCRETE_DANGEROUS_PATH_FOUND"
    if label == "UNSAFE":
        if "tx.origin" in text or "swc-115" in text:
            return "TX_ORIGIN_AUTHORIZATION_RISK"
        if "create" in text and "deploy" in text:
            return "UNRESTRICTED_CONTRACT_CREATION"
        if "arbitrary" in text and "call" in text:
            return "ARBITRARY_EXTERNAL_CALL"
        return "OTHER_UNSAFE"
    if "proxy" in text or "implementation" in text:
        return "UNRESOLVED_PROXY"
    if "atypical" in text or "decompil" in text:
        return "DECOMPILATION_AMBIGUITY"
    return "INSUFFICIENT_EVIDENCE"


def main() -> int:
    with open(os.path.join(HUMAN_EVAL_DIR, "llm_reviews", "pilot_code_review_content.json")) as f:
        content = json.load(f)["reviews"]
    with open(os.path.join(HUMAN_EVAL_DIR, "pilot_manifest.csv"), newline="") as f:
        manifest = {r["item_id"]: r for r in csv.DictReader(f)}

    records = []
    for item_id, rec in content.items():
        row = manifest[item_id]
        label = rec["ai_proposed_label"]
        reasoning_text = rec["concrete_security_finding"] + " " + rec["access_control_summary"] if "access_control_summary" in rec else rec.get("concrete_finding", "")
        # pilot_code_review_content.json's field names differ slightly from the new schema's
        access_control = rec.get("access_control_explanation", "")
        reason_category = infer_reason_category(label, access_control + " " + rec.get("concrete_security_finding", ""))
        records.append({
            "item_id": item_id,
            "llm_provisional_label": label,
            "llm_provisional_reason_category": reason_category,
            "llm_provisional_confidence": rec["ai_confidence"],
            "contract_purpose": rec["contract_purpose"],
            "sensitive_functions": rec["sensitive_function_names"],
            "access_control_analysis": rec["access_control_explanation"],
            "initialization_analysis": rec["initialization_explanation"],
            "proxy_and_upgrade_analysis": rec["proxy_and_upgrade_explanation"],
            "asset_operation_analysis": rec["asset_transfer_or_approval_explanation"],
            "authorization_specific_analysis": (
                "Self-call / tx.origin authorization pattern discussed in access_control_analysis "
                "and concrete_finding (Pilot items were hand-traced; see relevant_code_snippet "
                "in Pilot_Code_Review.xlsx for the exact guard opcode sequence)."
            ),
            "concrete_finding": rec["concrete_security_finding"],
            "evidence_references": rec["code_source_or_decompiler_reference"],
            "unresolved_questions": rec["unresolved_questions"],
            "alternative_plausible_label": None,
            "alternative_label_condition": None,
            "source_rule_label": row.get("source_label", ""),
            "human_final_label": "", "human_final_confidence": "", "human_final_reason": "",
            "human_review_status": "NOT_REVIEWED",
            "chain": row["chain"], "address": row["address"],
        })

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "pilot_labels.json"), "w") as f:
        json.dump({"LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
                   "sample_set": "pilot", "n_items": len(records), "records": records,
                   "note": "Remapped from the hand-traced pilot_code_review_content.json "
                           "(higher-rigor manual disassembly reading), not the automated "
                           "guard-tracer used for Gold-Dev/Gold-Test."}, f, indent=2, default=str)

    fieldnames = ["item_id", "chain", "address", "source_rule_label", "llm_provisional_label",
                  "llm_provisional_confidence", "llm_provisional_reason_category",
                  "human_final_label", "human_final_confidence", "human_final_reason",
                  "human_review_status"]
    with open(os.path.join(RESULTS_DIR, "pilot_labels.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, "") for k in fieldnames})

    from collections import Counter
    print(f"[pilot] {len(records)} items remapped")
    print("  label distribution:", Counter(r["llm_provisional_label"] for r in records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
