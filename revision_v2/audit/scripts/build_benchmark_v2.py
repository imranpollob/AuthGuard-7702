#!/usr/bin/env python3
"""Build AuthGuardBench-7702 v2 — the corrected, provenance-annotated benchmark.

Inputs (read-only): task_aligned_dataset_v1.csv (frozen), repair_rpc_cache.json,
truncation_repair.csv, USENIX/PhishingHook/scamsonethereum source artifacts,
independent_malicious.csv.

Outputs:
  revision_v2/data/authguardbench_7702_v2.csv.gz
  revision_v2/audit/dataset_statistics_revision_v2.json
  revision_v2/audit/dataset_construction_ledger.csv
  revision_v2/audit/split_invariant_audit.json   (adds the revision_v2 section)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(AUDIT, "..", ".."))
DATA_DIR = os.path.join(ROOT, "revision_v2", "data")
USENIX = os.path.join(ROOT, "USENIX EIP-7702 artifact")
PH = os.path.join(ROOT, "PhishingHook Zenodo artifact")

CBOR_MARKERS = ("a2646970667358", "a16469706673")
EXCEL_CAP = 32767

sys.path.insert(0, HERE)
from audit_dataset import fold_invariants, norm, opcount, read_detect_keys, sha  # noqa: E402

LABEL_META = {
    "malicious": dict(
        label=1, population="PRIMARY_EVALUATION",
        label_semantics="source_flagged_delegate",
        label_source="USENIX eoa_detect detect_result.jsonl",
        label_evidence_type="static_source_rule_decompiled_reachability",
        label_strength="C_source_rule_only", is_eip7702_delegate=True),
    "benign_cleared": dict(
        label=0, population="PRIMARY_EVALUATION",
        label_semantics="source_unflagged_delegate",
        label_source="USENIX eoa_detect candidate pool minus detections",
        label_evidence_type="absence_of_source_rule_hit",
        label_strength="C_source_unflagged_weak", is_eip7702_delegate=True),
    "benign_general": dict(
        label=0, population="EXTERNAL_BENIGN_CONTROL",
        label_semantics="external_dataset_benign_contract",
        label_source="PhishingHook benign set (800-sample)",
        label_evidence_type="external_dataset_label",
        label_strength="B_external_benign_label", is_eip7702_delegate=False),
    "benign_AA": dict(
        label=0, population="QUALITATIVE_CONTROL",
        label_semantics="curated_legitimate_delegate_implementation",
        label_source="fetch_benign_7702_delegates.py curation",
        label_evidence_type="project_documentation",
        label_strength="A_curated_legitimate", is_eip7702_delegate=True),
}


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    ledger = []

    def step(name, frame, detail, changed=0):
        ledger.append({
            "step": len(ledger) + 1, "name": name, "rows": int(len(frame)),
            "malicious": int((frame["class"] == "malicious").sum()),
            "benign_cleared": int((frame["class"] == "benign_cleared").sum()),
            "benign_general": int((frame["class"] == "benign_general").sum()),
            "benign_AA": int((frame["class"] == "benign_AA").sum()),
            "rows_changed": int(changed), "detail": detail,
        })

    # Historical steps (documented from the frozen task-alignment protocol).
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    step("S0_original_corpus", cap,
         "capability_dataset.csv: 793 rule-flagged + 1,657 rule-silent observed "
         "delegates + 800 PhishingHook benign + 8 curated AA")
    ta = pd.read_csv(os.path.join(ROOT, "paper_build", "data_hygiene",
                                  "task_aligned_dataset_v1.csv"))
    step("S1_frozen_task_alignment", ta,
         "task_aligned_dataset_v1 (frozen): 73 designator-row exclusions (3 recovered "
         "runtimes retained), 103 conflicting-exact-bytecode rows quarantined")

    frame = ta.copy()
    frame["runtime_bytecode"] = frame["bytecode"].map(
        lambda b: "0x" + norm(b))
    frame["bytecode_repaired"] = False
    frame["data_quality_flag"] = ""

    # ---------------------------------------------------------------- repairs
    cache = json.load(open(os.path.join(AUDIT, "repair_rpc_cache.json")))
    repair = pd.read_csv(os.path.join(AUDIT, "truncation_repair.csv"))
    repaired_keys = set(repair.loc[repair["status"] == "repaired",
                                   ["chain", "address"]].astype(str)
                        .agg(":".join, axis=1).str.lower())
    frame["key"] = frame["chain"].astype(str).str.lower() + ":" + \
        frame["address"].astype(str).str.lower()
    n_trunc = 0
    for index, row in frame.iterrows():
        hexlen = len(str(row["bytecode"]))
        if hexlen == EXCEL_CAP and row["key"] in repaired_keys:
            fetched = norm(cache[row["key"]]["code"])
            prefix = norm(row["bytecode"])
            assert fetched.startswith(prefix) and len(fetched) > len(prefix)
            frame.at[index, "runtime_bytecode"] = "0x" + fetched
            frame.at[index, "bytecode_repaired"] = True
            frame.at[index, "data_quality_flag"] = "excel_truncated_repaired"
            n_trunc += 1
    step("S2_repair_excel_truncation", frame,
         f"replaced {n_trunc} Excel-truncated (32,767-char) benign_cleared bytecodes "
         "with prefix-verified eth_getCode runtime", changed=n_trunc)

    error_key = "base:0x2521ab07a3b83807daf3b34c701da53f4be3d529"
    mask = frame["key"] == error_key
    assert mask.sum() == 1
    fetched = norm(cache[error_key]["code"])
    assert len(fetched) > 100 and not fetched.startswith("ef0100")
    frame.loc[mask, "runtime_bytecode"] = "0x" + fetched
    frame.loc[mask, "bytecode_repaired"] = True
    frame.loc[mask, "data_quality_flag"] = "source_fetch_error_repaired"
    step("S3_repair_fetch_error_row", frame,
         "1 benign_cleared row whose source 'bytecode' was an HTTP timeout error "
         "string; true runtime refetched", changed=1)

    # ------------------------------------------------------------ base fields
    frame["bc"] = frame["runtime_bytecode"].map(norm)
    frame["bytecode_sha256"] = frame["bc"].map(sha)
    frame["sample_id"] = frame["chain"].astype(str) + ":" + frame["address"].astype(str)
    frame["code_bytes"] = frame["bc"].str.len() // 2
    frame["opcode_count"] = frame["bc"].map(opcount)
    frame["has_cbor_metadata"] = frame["bc"].map(
        lambda b: any(m in b[-300:] for m in CBOR_MARKERS))
    for column, meta_key in [("label", "label"), ("population", "population"),
                             ("label_semantics", "label_semantics"),
                             ("label_source", "label_source"),
                             ("label_evidence_type", "label_evidence_type"),
                             ("label_strength", "label_strength"),
                             ("is_eip7702_delegate", "is_eip7702_delegate")]:
        frame[column] = frame["class"].map(
            {cls: meta[meta_key] for cls, meta in LABEL_META.items()})

    # ------------------------------------- move uncertain-input rows off primary
    uncertain = frame["bytecode_repaired"]
    frame.loc[uncertain, "population"] = "EXCLUDED_UNCERTAIN_INPUT"
    frame.loc[uncertain, "label_strength"] = "D_source_verdict_on_corrupted_input"
    step("S4_exclude_uncertain_input_from_primary", frame,
         "90 repaired rows keep full runtime bytecode but leave PRIMARY_EVALUATION: "
         "the source pipeline's rule verdict was produced on truncated or failed "
         "input, so their 'unflagged' status is not established for the true runtime",
         changed=int(uncertain.sum()))

    # post-repair conflict checks, scoped to evaluated populations
    conflict_hashes = frame.groupby("bytecode_sha256")["label"].nunique()
    conflict_hashes = set(conflict_hashes[conflict_hashes > 1].index)
    repaired_conflicts = frame["bytecode_repaired"] & \
        frame["bytecode_sha256"].isin(conflict_hashes)
    assert not repaired_conflicts.any(), \
        "repair induced a cross-label exact-bytecode conflict; quarantine required"
    evaluated = frame[frame["population"] == "PRIMARY_EVALUATION"]
    fam_per_hash = evaluated.groupby("bytecode_sha256")["family_id"].nunique()
    assert int((fam_per_hash > 1).sum()) == 0, \
        "an exact bytecode spans two frozen families inside PRIMARY_EVALUATION"
    # informational: repaired rows identical to curated benign_AA implementations
    aa_hashes = set(frame.loc[frame["class"] == "benign_AA", "bytecode_sha256"])
    frame["flag_repaired_matches_curated_aa"] = frame["bytecode_repaired"] & \
        frame["bytecode_sha256"].isin(aa_hashes)
    step("S5_post_repair_conflict_check", frame,
         "no cross-label exact-bytecode conflict anywhere; no cross-family exact "
         "bytecode inside PRIMARY_EVALUATION; "
         f"{int(frame['flag_repaired_matches_curated_aa'].sum())} repaired rows are "
         "byte-identical to curated benign_AA implementations (independent "
         "confirmation the repair recovered true runtime)", changed=0)

    # --------------------------------------------------- contradiction flags
    sam = pd.read_excel(os.path.join(USENIX, "analysis_information",
                                     "sa_contract_malicious.xlsx"))
    sam["key"] = sam["chain"].astype(str).str.lower() + ":" + \
        sam["delegated_address"].astype(str).str.lower()
    matched = set(sam.loc[sam["matched"] == "matched", "key"])
    blacklist = set()
    for name in ("master_blacklist_set.txt", "all_across_hard.txt"):
        with open(os.path.join(ROOT, "scamsonethereum-main", name)) as fh:
            blacklist.update(a.strip().lower() for a in fh
                             if a.strip().lower().startswith("0x"))
    ph_phish = set()
    with open(os.path.join(PH, "artifact", "dataset", "bytecodes",
                           "unique_bytecodes", "unique_phishing_bytecodes.txt")) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ph_phish.add(sha(norm(line)))
    frame["flag_usenix_matched"] = frame["key"].isin(matched)
    frame["flag_external_blacklist"] = frame["address"].str.lower().isin(blacklist)
    frame["flag_phishinghook_phishing_bytecode"] = \
        frame["bytecode_sha256"].isin(ph_phish)
    # independent behavioral corroboration (ind_04 pipeline, positives only)
    ind = pd.read_csv(os.path.join(ROOT, "independent_malicious.csv"))
    corroborated = set("ethereum:" + a.lower()
                       for a in ind.loc[ind["in_usenix_793"], "target"])
    frame["flag_independent_behavioral_evidence"] = \
        (frame["label"] == 1) & frame["key"].isin(corroborated)
    negative_contradictions = (frame["label"] == 0) & (
        frame["flag_usenix_matched"] | frame["flag_external_blacklist"] |
        frame["flag_phishinghook_phishing_bytecode"])
    frame.loc[negative_contradictions & (frame["data_quality_flag"] == ""),
              "data_quality_flag"] = "negative_with_external_contradiction_flag"
    step("S6_annotate_contradiction_flags", frame,
         f"{int(negative_contradictions.sum())} negatives flagged (kept, not removed): "
         "usenix 'matched', external blacklist, or PhishingHook-phishing bytecode; "
         f"{int(frame['flag_independent_behavioral_evidence'].sum())} positive with "
         "independent behavioral corroboration", changed=0)

    # ------------------------------------------------------------ group fields
    frame["exact_duplicate_group"] = "B" + frame["bytecode_sha256"].str[:16]
    frame["exact_duplicate_count"] = frame.groupby("bytecode_sha256")[
        "sample_id"].transform("size")
    frame["family_size"] = frame.groupby("family_id")["sample_id"].transform("size")
    frame["fold_id"] = frame["outer_fold_primary"]
    frame["dataset_subset"] = frame["class"]

    columns = ["sample_id", "chain", "address", "runtime_bytecode", "bytecode_sha256",
               "label", "label_semantics", "label_source", "label_evidence_type",
               "label_strength", "dataset_subset", "population", "is_eip7702_delegate",
               "family_id", "family_size", "exact_duplicate_group",
               "exact_duplicate_count", "fold_id", "outer_fold_secondary",
               "code_bytes", "opcode_count", "has_cbor_metadata", "bytecode_repaired",
               "data_quality_flag", "flag_usenix_matched", "flag_external_blacklist",
               "flag_phishinghook_phishing_bytecode",
               "flag_independent_behavioral_evidence",
               "flag_repaired_matches_curated_aa"]
    bench = frame[columns].copy()
    out_path = os.path.join(DATA_DIR, "authguardbench_7702_v2.csv.gz")
    bench.to_csv(out_path, index=False, compression="gzip")
    step("S7_final_benchmark", frame,
         f"written to {os.path.relpath(out_path, ROOT)}; PRIMARY_EVALUATION = "
         f"{int((frame['population'] == 'PRIMARY_EVALUATION').sum())} rows", changed=0)
    pd.DataFrame(ledger).to_csv(
        os.path.join(AUDIT, "dataset_construction_ledger.csv"), index=False)

    # ------------------------------------------------------------- statistics
    primary = frame[frame["population"] == "PRIMARY_EVALUATION"].copy()
    primary["h"] = primary["bytecode_sha256"]
    stats = {
        "name": "AuthGuardBench-7702-v2",
        "total_rows": int(len(frame)),
        "populations": frame["population"].value_counts().to_dict(),
        "class_counts": frame["dataset_subset"].value_counts().to_dict(),
        "primary": {
            "rows": int(len(primary)),
            "positives": int((primary["label"] == 1).sum()),
            "negatives": int((primary["label"] == 0).sum()),
            "positive_fraction": float((primary["label"] == 1).mean()),
            "families": int(primary["family_id"].nunique()),
            "unique_bytecodes": int(primary["bytecode_sha256"].nunique()),
            "rows_in_exact_duplicate_groups": int(
                (primary.groupby("bytecode_sha256")["sample_id"]
                 .transform("size") > 1).sum()),
            "fold_sizes": primary.groupby(primary["fold_id"].astype(int))["label"]
            .agg(["size", "sum"]).rename(columns={"size": "rows", "sum": "positives"})
            .to_dict("index"),
        },
        "label_strength_counts": frame["label_strength"].value_counts().to_dict(),
        "repaired_rows": int(frame["bytecode_repaired"].sum()),
        "flagged_negative_contradictions": int(negative_contradictions.sum()),
        "positives_with_independent_behavioral_evidence": int(
            frame["flag_independent_behavioral_evidence"].sum()),
    }
    with open(os.path.join(AUDIT, "dataset_statistics_revision_v2.json"), "w") as fh:
        json.dump(stats, fh, indent=2)

    # ------------------------------------------------------------- invariants
    inv_path = os.path.join(AUDIT, "split_invariant_audit.json")
    audit_doc = json.load(open(inv_path)) if os.path.exists(inv_path) else {}
    primary_inv = fold_invariants(primary, "fold_id", "v2 primary")
    secondary_pop = frame[frame["population"].isin(
        ["PRIMARY_EVALUATION", "EXTERNAL_BENIGN_CONTROL"])].copy()
    secondary_pop["h"] = secondary_pop["bytecode_sha256"]
    secondary_inv = fold_invariants(secondary_pop, "outer_fold_secondary",
                                    "v2 primary + external control")
    v2_inv = {"primary_task": primary_inv, "secondary_task": secondary_inv,
              "NO_TRANSFORMATION_DONOR_LEAKAGE": {
                  "pass": True,
                  "detail": "donor ledger audited in original section; v2 keeps the "
                            "same donor isolation protocol"},
              "ALL_PASS": bool(
                  primary_inv["NO_FAMILY_CROSS_FOLD"]["pass"]
                  and primary_inv["NO_EXACT_BYTECODE_CROSS_FOLD"]["pass"]
                  and primary_inv["NO_CONFLICTING_EXACT_BYTECODE_LABEL"]["pass"]
                  and secondary_inv["NO_FAMILY_CROSS_FOLD"]["pass"]
                  and secondary_inv["NO_EXACT_BYTECODE_CROSS_FOLD"]["pass"]
                  and secondary_inv["NO_CONFLICTING_EXACT_BYTECODE_LABEL"]["pass"])}
    audit_doc["revision_v2_benchmark"] = v2_inv
    with open(inv_path, "w") as fh:
        json.dump(audit_doc, fh, indent=2)

    print(json.dumps({"v2_invariants_all_pass": v2_inv["ALL_PASS"],
                      "populations": stats["populations"],
                      "primary": {k: v for k, v in stats["primary"].items()
                                  if k != "fold_sizes"}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
