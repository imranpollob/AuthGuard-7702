"""Refresh the representative queue's displayed labels to rubric v3 and draw a small pilot.

The 300-contract representative sample is NOT re-drawn. Its membership (the set of exact
bytecode hashes chosen label-blind with seed 7702) is read back from the existing file and held
fixed; only the displayed LLM label/evidence columns are refreshed to prompt_version v3, since
reviewing against superseded labels would be pointless. The original file is left untouched and
the refreshed one is written alongside it.

The pilot is a stratified sample across (label x coverage_status) cells so a first reviewing
pass exercises every branch of the rubric, including both COMPLETE and PARTIAL coverage. It is
a subset of the representative sample, so pilot decisions remain usable afterwards.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402

PILOT_TARGET = 36
REQUIRED_COLUMNS = [
    "review_id", "contract_address", "exact_bytecode_hash", "bytecode_family_id",
    "represented_contract_count", "verified_project_name", "coverage_status",
    "llm_label", "llm_confidence", "llm_explanation", "evidence_summary",
    "decision", "final_label", "final_confidence", "comment",
]


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    hr_dir = cfg["_resolved_paths"]["human_reviews"]
    seed = cfg.get("seed", 7702)

    existing_path = os.path.join(hr_dir, f"{run_id}_representative_gold_queue.csv")
    existing = pd.read_csv(existing_path, keep_default_na=False)
    frozen_hashes = existing["exact_bytecode_hash"].tolist()
    print(f"[pilot] representative sample membership held fixed: {len(frozen_hashes)} runtimes")

    reviews = pd.read_csv(os.path.join(cfg["_resolved_paths"]["llm_reviews"], f"{run_id}_review_index_promptv3.csv"))
    review_by_addr = reviews.set_index("address")

    rows = []
    for r in existing.to_dict("records"):
        addr = r["contract_address"]
        rec = review_by_addr.loc[addr]
        with open(rec["review_path"]) as f:
            parsed = json.load(f)["parsed_response"]
        with open(r["evidence_path"]) as f:
            packet = json.load(f)
        reach = packet.get("reachability", {}) or {}
        prov = reach.get("unguarded_dangerous_by_target_provenance", {}) or {}

        evidence_summary = (
            f"exec={reach.get('executable_bytes')}B; "
            f"reachable_dangerous={reach.get('reachable_dangerous_count')}; "
            f"unguarded_dangerous={reach.get('unguarded_dangerous_count')}; "
            f"unguarded_targets(calldata={prov.get('calldata_target', 0)},"
            f"const={prov.get('constant_target', 0)},unresolved={prov.get('unresolved_target', 0)},"
            f"critical={prov.get('critical_op', 0)}); "
            f"guards={reach.get('n_guards')} (strong="
            f"{sum(1 for g in (reach.get('guards') or []) if g.get('kind') == 'strong')}); "
            f"ecrecover={reach.get('reaches_ecrecover')}; coverage={reach.get('coverage_status')}"
            + (f"; why_partial={'; '.join(reach.get('coverage_reasons', [])[:2])}"
               if reach.get("coverage_reasons") else "")
        )
        guard_semantics = sorted({g["semantics"] for g in (reach.get("guards") or [])})

        new = dict(r)
        new.update({
            "coverage_status": reach.get("coverage_status"),
            "llm_label": parsed["proposed_label"],
            "llm_confidence": parsed["confidence"],
            "llm_explanation": parsed["summary"],
            "evidence_summary": evidence_summary,
            "llm_risk_categories": "; ".join(parsed["risk_categories"]),
            "llm_uncertainties": " | ".join(parsed["uncertainties"]),
            "llm_evidence_detail": " | ".join(parsed["evidence"]),
            "guard_semantics_observed": " | ".join(guard_semantics)[:500],
            "prompt_version": "v3",
        })
        rows.append(new)

    refreshed = pd.DataFrame(rows)
    column_order = REQUIRED_COLUMNS + [c for c in refreshed.columns if c not in REQUIRED_COLUMNS]
    refreshed = refreshed[column_order]
    refreshed_path = os.path.join(hr_dir, f"{run_id}_representative_gold_queue_promptv3.csv")
    refreshed.to_csv(refreshed_path, index=False)

    assert refreshed["exact_bytecode_hash"].tolist() == frozen_hashes, "sample membership changed"

    # ---- pilot membership ----
    # If a pilot already exists, its membership is FIXED and only its evidence/labels are
    # refreshed; re-sampling would silently change which contracts a reviewer was asked to look
    # at every time labels move. A fresh pilot is stratified across label x coverage cells.
    pilot_path = os.path.join(hr_dir, f"{run_id}_pilot_queue.csv")
    if os.path.exists(pilot_path):
        prior_ids = pd.read_csv(pilot_path, keep_default_na=False)["review_id"].tolist()
        pilot = refreshed[refreshed["review_id"].isin(prior_ids)].copy()
        missing = set(prior_ids) - set(pilot["review_id"])
        if missing:
            raise SystemExit(f"pilot rows missing from refreshed queue: {sorted(missing)}")
        membership_source = f"preserved from existing pilot ({len(prior_ids)} review_ids)"
    else:
        refreshed["_cell"] = refreshed["llm_label"] + "/" + refreshed["coverage_status"]
        per_cell = max(1, PILOT_TARGET // len(refreshed["_cell"].unique()))
        picks = [sub.sample(n=min(per_cell, len(sub)), random_state=seed)
                 for _cell, sub in refreshed.groupby("_cell")]
        pilot = pd.concat(picks)
        if len(pilot) < PILOT_TARGET:
            remaining = refreshed[~refreshed["review_id"].isin(pilot["review_id"])]
            pilot = pd.concat([pilot, remaining.sample(
                n=min(PILOT_TARGET - len(pilot), len(remaining)), random_state=seed)])
        pilot = pilot.drop(columns=["_cell"])
        membership_source = "newly stratified across label x coverage cells"
    refreshed = refreshed.drop(columns=[c for c in ("_cell",) if c in refreshed.columns])
    pilot = pilot.sort_values(["llm_label", "coverage_status", "review_id"])

    pilot.to_csv(pilot_path, index=False)

    summary = {
        "representative_sample_membership_unchanged": True,
        "representative_refreshed_csv": refreshed_path,
        "representative_label_counts_v3": refreshed["llm_label"].value_counts().to_dict(),
        "representative_coverage_counts": refreshed["coverage_status"].value_counts().to_dict(),
        "pilot_queue_csv": pilot_path,
        "pilot_membership_source": membership_source,
        "pilot_n_rows": int(len(pilot)),
        "pilot_contracts_represented": int(pilot["represented_contract_count"].sum()),
        "pilot_cells": {f"{label}/{coverage}": int(n) for (label, coverage), n
                        in pilot.groupby(["llm_label", "coverage_status"]).size().items()},
        "pilot_families": int(pilot["bytecode_family_id"].nunique()),
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(os.path.join(hr_dir, f"{run_id}_pilot_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)


if __name__ == "__main__":
    main()
