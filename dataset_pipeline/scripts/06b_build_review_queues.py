"""Tasks 4-6: deduplicate review work by exact runtime bytecode, then emit two queues.

Deduplication (Task 4)
    One review row per exact runtime-bytecode SHA-256. The representative is deterministic
    (earliest first-observed block, then lowest address). `represented_contract_count` says how
    many deployed delegate addresses that row speaks for, and `represented_addresses` lists
    them. A human decision propagates ONLY across identical runtime bytecode -- never across
    merely-similar family members, which is why `bytecode_family_id` is shown but never used
    for propagation.

Queue A -- representative_gold_queue.csv (Task 5A)
    A uniform random sample of unique runtime representatives drawn from the full unfiltered
    screenable population. The sample is drawn with a fixed seed BEFORE any LLM label is
    joined, so selection cannot depend on the model's opinion. Supports the main representative
    evaluation.

Queue B -- diagnostic_queue.csv (Task 5B)
    Targeted set for error and risk-category analysis: R1 cases, U cases, low-confidence cases,
    verified/documented projects, analyzer disagreements, proxy cases, and unusual evidence.
    Rows already in Queue A are excluded so no contract is reviewed twice. Every row carries
    `diagnostic_reasons`. This queue is NOT a prevalence sample and must not be used as one.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402

GOLD_SAMPLE_SIZE = 300

REQUIRED_COLUMNS = [
    "review_id", "contract_address", "exact_bytecode_hash", "bytecode_family_id",
    "represented_contract_count", "verified_project_name", "coverage_status",
    "llm_label", "llm_confidence", "llm_explanation", "evidence_summary",
    "decision", "final_label", "final_confidence", "comment",
]


def build_dedup_table(cfg: dict, run_id: str) -> pd.DataFrame:
    families = pd.read_csv(os.path.join(cfg["_resolved_paths"]["bytecode_families"], f"{run_id}_family_assignment.csv"))
    screenable = families[families["retrieval_status"] == "OK"].copy()
    screenable["first_observed_block"] = screenable["first_observed_block"].astype(int)

    ordered = screenable.sort_values(["bytecode_sha256", "first_observed_block", "delegate_address"])
    grouped = ordered.groupby("bytecode_sha256", sort=True)
    reps = grouped.first().reset_index()
    reps["represented_contract_count"] = grouped.size().values
    reps["represented_addresses"] = grouped["delegate_address"].apply(lambda s: ";".join(sorted(s))).values
    return reps


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    out_dir = cfg["_resolved_paths"]["human_reviews"]
    os.makedirs(out_dir, exist_ok=True)

    reps = build_dedup_table(cfg, run_id)
    n_unique = len(reps)
    print(f"[queues] {reps['represented_contract_count'].sum()} screenable contracts -> "
          f"{n_unique} unique runtime bytecodes")

    # ---- Queue A selection happens BEFORE any label is joined (label-blind by construction) ----
    seed = cfg.get("seed", 7702)
    sample_size = min(GOLD_SAMPLE_SIZE, n_unique)
    gold_hashes = set(
        reps["bytecode_sha256"].sample(n=sample_size, random_state=seed).tolist()
    )

    # ---- now join evidence + LLM review for display only ----
    reviews = pd.read_csv(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv2.csv"))
    ev_index = pd.read_csv(os.path.join(cfg["_resolved_paths"]["evidence_packages"], f"{run_id}_evidence_index.csv"))
    merged = reps.merge(reviews, left_on="delegate_address", right_on="address", how="left")
    merged = merged.merge(ev_index[["address", "evidence_path", "verified_source_status"]], on="address", how="left")

    rows = []
    for i, r in enumerate(merged.itertuples(index=False), start=1):
        with open(r.evidence_path) as f:
            packet = json.load(f)
        review_path = r.review_path
        with open(review_path) as f:
            review = json.load(f)["parsed_response"]
        reach = packet.get("reachability", {}) or {}
        known = packet.get("known_project")

        diagnostic_reasons = []
        if review["proposed_label"] == "R1":
            diagnostic_reasons.append("r1_case")
        if review["proposed_label"] == "U":
            diagnostic_reasons.append("u_case")
        if review["confidence"] == "low":
            diagnostic_reasons.append("low_confidence")
        if known is not None:
            diagnostic_reasons.append("documented_project")
        if r.verified_source_status == "VERIFIED":
            diagnostic_reasons.append("verified_source")
        if reach.get("sensitive_present_but_never_reached"):
            diagnostic_reasons.append("analyzer_disagreement_present_but_unreached")
        if str(r.v1_label) != review["proposed_label"]:
            diagnostic_reasons.append(f"label_changed_v1_{r.v1_label}_to_v2_{review['proposed_label']}")
        if reach.get("reachable_delegatecall_with_unresolved_target") or packet["proxy_evidence"]["has_delegatecall"]:
            diagnostic_reasons.append("proxy_or_delegatecall")
        if packet["proxy_evidence"]["is_eip7702_designator"]:
            diagnostic_reasons.append("unresolved_designator")
        if reach.get("analysis_error"):
            diagnostic_reasons.append("analysis_error")
        if reach.get("metadata_recognized") is False and reach.get("metadata_bytes", 0) == 0:
            diagnostic_reasons.append("no_recognizable_solidity_metadata")

        evidence_summary = (
            f"exec={reach.get('executable_bytes')}B meta={reach.get('metadata_bytes')}B; "
            f"reachable={reach.get('sensitive_reachable') or 'none'}; "
            f"unguarded={reach.get('sensitive_reachable_without_caller_guard') or 'none'}; "
            f"guards={reach.get('n_guards')}; ecrecover={reach.get('reaches_ecrecover')}; "
            f"unresolved_jumps={reach.get('unresolved_dynamic_jumps')}; "
            f"coverage={reach.get('coverage_status')}"
            + (f"; coverage_reasons={'; '.join(reach.get('coverage_reasons', [])[:2])}"
               if reach.get("coverage_reasons") else "")
        )

        rows.append({
            "review_id": f"{run_id.upper()}-{i:04d}",
            "contract_address": r.delegate_address,
            "exact_bytecode_hash": r.bytecode_sha256,
            "bytecode_family_id": r.bytecode_family_id,
            "represented_contract_count": int(r.represented_contract_count),
            "verified_project_name": known["project"] if known else (
                "SOURCIFY_VERIFIED_UNNAMED" if r.verified_source_status == "VERIFIED" else ""),
            "coverage_status": reach.get("coverage_status"),
            "llm_label": review["proposed_label"],
            "llm_confidence": review["confidence"],
            "llm_explanation": review["summary"],
            "evidence_summary": evidence_summary,
            "decision": "",
            "final_label": "",
            "final_confidence": "",
            "comment": "",
            # supporting context (not part of the required set)
            "llm_risk_categories": "; ".join(review["risk_categories"]),
            "llm_uncertainties": " | ".join(review["uncertainties"]),
            "represented_addresses": r.represented_addresses,
            "bytecode_length": int(r.bytecode_length),
            "first_observed_block": int(r.first_observed_block),
            "authorization_frequency": int(r.authorization_frequency),
            "evidence_path": r.evidence_path,
            "explorer_link": packet.get("explorer_link"),
            "diagnostic_reasons": "; ".join(diagnostic_reasons),
            "_in_gold": r.bytecode_sha256 in gold_hashes,
        })

    allrows = pd.DataFrame(rows)
    column_order = REQUIRED_COLUMNS + [c for c in allrows.columns if c not in REQUIRED_COLUMNS and c != "_in_gold"]

    gold = allrows[allrows["_in_gold"]][column_order].copy()
    gold_path = os.path.join(out_dir, f"{run_id}_representative_gold_queue.csv")
    gold.to_csv(gold_path, index=False)

    diagnostic = allrows[(~allrows["_in_gold"]) & (allrows["diagnostic_reasons"] != "")][column_order].copy()
    diagnostic = diagnostic.sort_values(
        by=["llm_label", "represented_contract_count"],
        key=lambda s: s.map({"R1": 0, "U": 1, "R2": 2, "B": 3}) if s.name == "llm_label" else -s,
    )
    diag_path = os.path.join(out_dir, f"{run_id}_diagnostic_queue.csv")
    diagnostic.to_csv(diag_path, index=False)

    full_path = os.path.join(out_dir, f"{run_id}_all_unique_runtimes.csv")
    allrows[column_order].to_csv(full_path, index=False)

    summary = {
        "n_screenable_contracts": int(allrows["represented_contract_count"].sum()),
        "n_unique_runtime_hashes": int(n_unique),
        "dedup_saving_rows": int(allrows["represented_contract_count"].sum() - n_unique),
        "representative_gold_queue": {
            "path": gold_path, "n_rows": int(len(gold)),
            "n_contracts_represented": int(gold["represented_contract_count"].sum()),
            "n_families": int(gold["bytecode_family_id"].nunique()),
            "llm_label_counts": gold["llm_label"].value_counts().to_dict(),
            "selection": f"uniform random over unique runtimes, seed={seed}, drawn before labels were joined",
        },
        "diagnostic_queue": {
            "path": diag_path, "n_rows": int(len(diagnostic)),
            "n_contracts_represented": int(diagnostic["represented_contract_count"].sum()),
            "llm_label_counts": diagnostic["llm_label"].value_counts().to_dict(),
        },
        "all_unique_runtimes_csv": full_path,
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(out_dir, f"{run_id}_queue_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)


if __name__ == "__main__":
    main()
