#!/usr/bin/env python3
"""AuthGuardBench-7702 dataset audit (Parts 1, 2, 4, 5 of the revision audit).

Read-only over frozen artifacts. Writes:
  revision_v2/audit/dataset_statistics_original.json
  revision_v2/audit/dataset_provenance.csv
  revision_v2/audit/split_invariant_audit.json      (original-benchmark section)
  revision_v2/audit/population_comparability.json
  revision_v2/audit/circularity_signals.csv
  revision_v2/audit/negative_flags.csv              (per-row external contradiction flags)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats as sstats

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(AUDIT, "..", ".."))
USENIX = os.path.join(ROOT, "USENIX EIP-7702 artifact")
PH = os.path.join(ROOT, "PhishingHook Zenodo artifact")

CBOR_MARKERS = ("a2646970667358", "a16469706673")  # solc CBOR metadata: {ipfs:..} shapes


def norm(raw: object) -> str:
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    return h[:-1] if len(h) % 2 else h


def sha(h: str) -> str:
    return hashlib.sha256(h.encode()).hexdigest()


def read_detect_keys() -> set[str]:
    decoder = json.JSONDecoder()
    keys = set()
    with open(os.path.join(USENIX, "eoa_detect", "detect_result.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            pos = 0
            while pos < len(line):
                obj, end = decoder.raw_decode(line, pos)
                chain = obj["path"].split("/")[1].lower()
                keys.add(chain + ":" + obj["address"].lower())
                pos = end
                while pos < len(line) and line[pos] in " \t,":
                    pos += 1
    return keys


def opcount(bc: str) -> int:
    """Fast opcode count via linear sweep (PUSH immediates skipped)."""
    try:
        b = bytes.fromhex(bc) if bc else b""
    except ValueError:
        cleaned = "".join(c for c in bc if c in "0123456789abcdef")
        b = bytes.fromhex(cleaned[:len(cleaned) // 2 * 2])
    i = n = 0
    while i < len(b):
        op = b[i]
        i += 1 + (op - 0x5F if 0x60 <= op <= 0x7F else 0)
        n += 1
    return n


def dist_stats(series: pd.Series) -> dict:
    q = series.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {"n": int(len(series)), "mean": float(series.mean()),
            "p05": float(q[0.05]), "p25": float(q[0.25]), "median": float(q[0.5]),
            "p75": float(q[0.75]), "p95": float(q[0.95]),
            "min": float(series.min()), "max": float(series.max())}


def fold_invariants(frame: pd.DataFrame, fold_col: str, name: str) -> dict:
    sub = frame.dropna(subset=[fold_col]).copy()
    sub["fold"] = sub[fold_col].astype(int)
    fam_cross = int((sub.groupby("family_id")["fold"].nunique() > 1).sum())
    hash_cross = int((sub.groupby("h")["fold"].nunique() > 1).sum())
    label_conflict = int((sub.groupby("h")["label"].nunique() > 1).sum())
    return {
        "population": name,
        "rows": int(len(sub)),
        "families": int(sub["family_id"].nunique()),
        "NO_FAMILY_CROSS_FOLD": {"pass": fam_cross == 0, "violations": fam_cross},
        "NO_EXACT_BYTECODE_CROSS_FOLD": {"pass": hash_cross == 0, "violations": hash_cross},
        "NO_CONFLICTING_EXACT_BYTECODE_LABEL": {"pass": label_conflict == 0,
                                                "violations": label_conflict},
    }


def main() -> int:
    out = {}
    # ------------------------------------------------------------------ load
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    ta = pd.read_csv(os.path.join(ROOT, "paper_build", "data_hygiene",
                                  "task_aligned_dataset_v1.csv"))
    for frame in (cap, ta):
        frame["bc"] = frame["bytecode"].map(norm)
        frame["h"] = frame["bc"].map(sha)
        frame["key"] = frame["chain"].astype(str).str.lower() + ":" + \
            frame["address"].astype(str).str.lower()
        frame["label"] = (frame["class"] == "malicious").astype(int)
        frame["hexlen"] = frame["bytecode"].astype(str).str.len()
        frame["code_bytes"] = frame["bc"].str.len() // 2
        frame["has_cbor_metadata"] = frame["bc"].map(
            lambda b: any(m in b[-300:] for m in CBOR_MARKERS))
    det_keys = read_detect_keys()

    # ------------------------------------------------- original statistics
    def corpus_stats(frame: pd.DataFrame, fold_cols: list[str]) -> dict:
        dup = frame.groupby("h")["key"].transform("size")
        multi_addr = frame.groupby("h")["address"].transform("nunique")
        chains_per_hash = frame.groupby("h")["chain"].transform("nunique")
        stats = {
            "total_rows": int(len(frame)),
            "class_counts": frame["class"].value_counts().to_dict(),
            "unique_chain_address_pairs": int(frame["key"].nunique()),
            "unique_addresses": int(frame["address"].str.lower().nunique()),
            "unique_runtime_bytecodes": int(frame["h"].nunique()),
            "exact_duplicate_groups_gt1": int(
                frame.loc[dup > 1, "h"].nunique()),
            "rows_in_exact_duplicate_groups": int((dup > 1).sum()),
            "cross_label_exact_bytecode_conflict_hashes": int(
                (frame.groupby("h")["class"].nunique() > 1).sum()),
            "cross_binary_label_conflict_hashes": int(
                (frame.groupby("h")["label"].nunique() > 1).sum()),
            "bytecodes_at_multiple_addresses": int(
                frame.loc[multi_addr > 1, "h"].nunique()),
            "bytecodes_on_multiple_chains": int(
                frame.loc[chains_per_hash > 1, "h"].nunique()),
            "family_count": int(frame["family_id"].nunique())
            if "family_id" in frame else None,
            "designator_rows": int(frame["bc"].str.match(
                r"^ef0100[0-9a-f]{40}$").sum()),
            "excel_truncated_rows": int((frame["hexlen"] == 32767).sum()),
        }
        if "family_id" in frame:
            fam_sizes = frame.groupby("family_id").size()
            stats["family_size_distribution"] = {
                "singletons": int((fam_sizes == 1).sum()),
                "size_2_5": int(((fam_sizes >= 2) & (fam_sizes <= 5)).sum()),
                "size_6_20": int(((fam_sizes >= 6) & (fam_sizes <= 20)).sum()),
                "size_gt_20": int((fam_sizes > 20).sum()),
                "max": int(fam_sizes.max()),
            }
            fam_mix = frame.groupby("family_id")["class"].nunique()
            stats["cross_class_families"] = int((fam_mix > 1).sum())
        for col in fold_cols:
            if col in frame:
                stats[f"{col}_assigned_rows"] = int(frame[col].notna().sum())
        return stats

    out["capability_dataset_csv"] = corpus_stats(cap, [])
    out["task_aligned_dataset_v1"] = corpus_stats(
        ta, ["outer_fold_primary", "outer_fold_secondary"])

    # label ↔ source-rule identity check (circularity core)
    mal = ta[ta["class"] == "malicious"]
    cle = ta[ta["class"] == "benign_cleared"]
    out["label_rule_identity"] = {
        "retained_positives": int(len(mal)),
        "positives_with_source_rule_hit": int(mal["key"].isin(det_keys).sum()),
        "retained_rule_silent_negatives": int(len(cle)),
        "negatives_with_source_rule_hit": int(cle["key"].isin(det_keys).sum()),
    }

    # ------------------------------------------------------ provenance table
    provenance = [
        dict(subset="malicious", n_original=793, n_task_aligned=int(len(mal)),
             source="USENIX EIP-7702 artifact, eoa_detect pipeline",
             source_files="eoa_detect/get_code/contracts_with_bytecode.xlsx; "
                          "eoa_detect/detect_result.jsonl",
             generation_script="phase0 extraction (phase0_report.md Task 6); "
                               "paper_build/data_hygiene/task_alignment.py",
             inclusion_rule="observed EIP-7702 delegate candidate (2,685 pool) whose "
                            "decompiled bytecode fired the Gigahorse/Datalog rule "
                            "'external call reachable from receive()/fallback()' "
                            "(detect_result.jsonl, 793 keys)",
             exclusion_rule="66 rows quarantined in task alignment: member of an "
                            "exact-bytecode group carrying conflicting class labels",
             label_assignment="class='malicious' iff (chain,address) in detect_result.jsonl",
             is_observed_7702_delegate=True,
             bytecode_acquisition="source-artifact eth_getCode dump (Excel); runtime "
                                  "bytecode direct, not designator",
             evidence_type="static bytecode-derived source rule (decompiled reachability); "
                           "no per-row transaction/victim evidence in artifact",
             evidence_independence="DERIVED_OVERLAP with model input"),
        dict(subset="benign_cleared", n_original=1657, n_task_aligned=int(len(cle)),
             source="USENIX EIP-7702 artifact, eoa_detect pipeline (same pool)",
             source_files="eoa_detect/get_code/contracts_with_bytecode.xlsx",
             generation_script="phase0 extraction; task_alignment.py",
             inclusion_rule="observed EIP-7702 delegate candidate NOT in "
                            "detect_result.jsonl with non-empty bytecode "
                            "(2,685 - 793 detected - 235 empty = 1,657)",
             exclusion_rule="104 removed in task alignment: 73 designator-row "
                            "exclusions/replacements + 31 conflict-quarantined",
             label_assignment="class='benign_cleared' iff candidate and rule silent",
             is_observed_7702_delegate=True,
             bytecode_acquisition="same source dump; 76 rows were bare EIP-7702 "
                                  "designators (resolved or excluded in task alignment); "
                                  "89 rows Excel-truncated at 32,767 chars",
             evidence_type="absence of a source-rule hit only; no verification of "
                           "benignity",
             evidence_independence="rule-silent weak negative"),
        dict(subset="benign_general", n_original=800, n_task_aligned=int(
                 (ta["class"] == "benign_general").sum()),
             source="PhishingHook Zenodo artifact benign set",
             source_files="artifact/dataset/bytecodes/unique_bytecodes/"
                          "unique_benign_bytecodes.txt (3,542 unique; 800 sampled)",
             generation_script="pre-phase0 session (sample of 800); verified by exact "
                               "hash join: 800/800 present in PhishingHook benign set",
             inclusion_rule="sampled from PhishingHook deduplicated benign bytecodes "
                            "(themselves sampled from 20,000 of 4.17M benign addresses)",
             exclusion_rule="3 rows conflict-quarantined in task alignment",
             label_assignment="class='benign_general' from PhishingHook benign label",
             is_observed_7702_delegate=False,
             bytecode_acquisition="PhishingHook Etherscan dump, Ethereum-only "
                                  "(chain='ethereum(implied)')",
             evidence_type="external dataset's benign label (not attack-checked for "
                           "the EIP-7702 threat model); 7/800 hashes also appear in "
                           "PhishingHook's phishing set",
             evidence_independence="INDEPENDENT of USENIX pipeline; different "
                                   "population (general contracts, not delegates)"),
        dict(subset="benign_AA", n_original=8, n_task_aligned=int(
                 (ta["class"] == "benign_AA").sum()),
             source="curated legitimate EIP-7702/AA delegate implementations",
             source_files="benign_7702_bytecode.csv (fetch_benign_7702_delegates.py; "
                          "MetaMask delegation framework et al., 45 fetches, 8 deduped)",
             generation_script="fetch_benign_7702_delegates.py",
             inclusion_rule="documented delegate implementation address of a known "
                            "project, runtime fetched via eth_getCode",
             exclusion_rule="3 rows dropped in task alignment (exact-bytecode overlap "
                            "or conflict with frozen families)",
             label_assignment="class='benign_AA' by curation",
             is_observed_7702_delegate=True,
             bytecode_acquisition="read-only eth_getCode (full runtime, not truncated)",
             evidence_type="project documentation / deployment registry",
             evidence_independence="INDEPENDENT; strongest negative evidence but n=5"),
    ]
    pd.DataFrame(provenance).to_csv(os.path.join(AUDIT, "dataset_provenance.csv"),
                                    index=False)

    # ------------------------------------------------- circularity signal map
    signals = [
        dict(signal="Gigahorse decompiled control flow: external call reachable from "
                    "receive()/fallback() (AM_Detect_FallbackCallOut_High)",
             used_for="defines all 793 positives (detect_result.jsonl)",
             classification="DERIVED_OVERLAP",
             rationale="computed by decompiling the exact runtime bytecode the model "
                       "receives; reachability itself is not in the 773 features or the "
                       "opcode-token stream, but every input bit it depends on is"),
        dict(signal="function-name lexical rule (attack/hack/sweep/steal/drain/exploit/"
                    "pwn prefixes; AM_Detect_SensitiveSigName.jsonl)",
             used_for="auxiliary source output; 58/793 positives, 11 cleared",
             classification="DERIVED_OVERLAP",
             rationale="derived from selectors present in the bytecode; AuthGuard's "
                       "selector features see the same selectors"),
        dict(signal="observed EIP-7702 delegation (candidate-pool membership, "
                    "sa_contract.xlsx count column)",
             used_for="defines the candidate pool for positives AND primary negatives",
             classification="INDEPENDENT",
             rationale="on-chain authorization observations, not bytecode; identical "
                       "for both primary classes so it carries no label signal"),
        dict(signal="'matched' column in sa_contract_malicious.xlsx (826/2,685; "
                    "covers 793/793 positives + 13 retained cleared rows)",
             used_for="unclear; artifact does not document the matched-against list",
             classification="UNKNOWN",
             rationale="direction unresolvable from artifact: could be external intel "
                       "cross-reference or an internal detection roll-up"),
        dict(signal="transaction behavior / victim reports / attack transactions",
             used_for="not present in the artifact (ethics statement: victim data "
                      "removed; no tx hashes, no timestamps)",
             classification="INDEPENDENT (absent)",
             rationale="no per-row behavioral evidence exists for any positive"),
        dict(signal="scamsonethereum blacklists (7,915 + 495 addresses)",
             used_for="not used in label generation; audit cross-reference",
             classification="INDEPENDENT",
             rationale="address-level overlap: 0/727 positives, 1 cleared row "
                       "blacklisted (contradiction flag)"),
        dict(signal="PhishingHook phishing set (3,458 unique bytecodes)",
             used_for="not used in label generation; audit cross-reference",
             classification="INDEPENDENT",
             rationale="bytecode-hash overlap: 0 positives, 3 benign_cleared, "
                       "7 benign_general rows also occur in the phishing set "
                       "(contradiction flags)"),
    ]
    pd.DataFrame(signals).to_csv(os.path.join(AUDIT, "circularity_signals.csv"),
                                 index=False)

    # --------------------------------------------- negative contradiction flags
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
    ph_phish_hashes = set()
    with open(os.path.join(PH, "artifact", "dataset", "bytecodes", "unique_bytecodes",
                           "unique_phishing_bytecodes.txt")) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ph_phish_hashes.add(sha(norm(line)))
    neg = ta[ta["class"] != "malicious"].copy()
    neg["flag_usenix_matched"] = neg["key"].isin(matched)
    neg["flag_external_blacklist"] = neg["address"].str.lower().isin(blacklist)
    neg["flag_phishinghook_phishing_bytecode"] = neg["h"].isin(ph_phish_hashes)
    flags = neg[neg[["flag_usenix_matched", "flag_external_blacklist",
                     "flag_phishinghook_phishing_bytecode"]].any(axis=1)]
    flags[["chain", "address", "class", "family_id", "flag_usenix_matched",
           "flag_external_blacklist", "flag_phishinghook_phishing_bytecode"]].to_csv(
        os.path.join(AUDIT, "negative_flags.csv"), index=False)
    out["negative_contradiction_flags"] = {
        "rows_flagged": int(len(flags)),
        "by_class": flags["class"].value_counts().to_dict(),
        "flag_usenix_matched": int(flags["flag_usenix_matched"].sum()),
        "flag_external_blacklist": int(flags["flag_external_blacklist"].sum()),
        "flag_phishinghook_phishing_bytecode": int(
            flags["flag_phishinghook_phishing_bytecode"].sum()),
    }

    # --------------------------------------------------- split invariants (v1)
    inv = {"benchmark": "task_aligned_dataset_v1 (original)"}
    primary = ta[ta["class"].isin(["malicious", "benign_cleared"])]
    secondary = ta[ta["class"].isin(["malicious", "benign_cleared", "benign_general"])]
    inv["primary_task"] = fold_invariants(primary, "outer_fold_primary",
                                          "malicious vs benign_cleared")
    inv["secondary_task"] = fold_invariants(secondary, "outer_fold_secondary",
                                            "+ benign_general")
    # transformation donor leakage from the recorded ledger
    ledger_path = os.path.join(ROOT, "revision_v2", "results",
                               "transformation_consistent", "donor_ledger.csv.gz")
    donor_result = {"pass": None, "detail": "ledger missing"}
    if os.path.exists(ledger_path):
        with gzip.open(ledger_path, "rt") as fh:
            ledger = pd.read_csv(fh)
        violations = []
        for (exp, fold), grp in ledger.groupby(["experiment_id", "outer_fold"]):
            pools = grp.groupby("recipient_partition")["copied_segment_sha256"].agg(set)
            fam_pools = grp.groupby("recipient_partition")["donor_family"].agg(set)
            parts = list(pools.index)
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)):
                    seg = pools[parts[i]] & pools[parts[j]]
                    fam = fam_pools[parts[i]] & fam_pools[parts[j]]
                    if seg:
                        violations.append(dict(experiment=exp, fold=int(fold),
                                               kind="segment", a=parts[i], b=parts[j],
                                               n=len(seg)))
                    if fam:
                        violations.append(dict(experiment=exp, fold=int(fold),
                                               kind="donor_family", a=parts[i],
                                               b=parts[j], n=len(fam)))
            # donors must never come from a recipient family in another partition either
            recip_fams = grp.groupby("recipient_partition")["recipient_family"].agg(set)
            for part in parts:
                other = set().union(*[recip_fams[p] for p in parts if p != part]) \
                    if len(parts) > 1 else set()
                overlap = fam_pools[part] & other
                if overlap:
                    violations.append(dict(experiment=exp, fold=int(fold),
                                           kind="donor_equals_foreign_recipient_family",
                                           a=part, b="other", n=len(overlap)))
        donor_result = {"pass": len(violations) == 0,
                        "ledger_rows": int(len(ledger)),
                        "violations": violations[:20],
                        "n_violations": len(violations)}
    inv["NO_TRANSFORMATION_DONOR_LEAKAGE"] = donor_result
    all_pass = (inv["primary_task"]["NO_FAMILY_CROSS_FOLD"]["pass"]
                and inv["primary_task"]["NO_EXACT_BYTECODE_CROSS_FOLD"]["pass"]
                and inv["primary_task"]["NO_CONFLICTING_EXACT_BYTECODE_LABEL"]["pass"]
                and inv["secondary_task"]["NO_FAMILY_CROSS_FOLD"]["pass"]
                and inv["secondary_task"]["NO_EXACT_BYTECODE_CROSS_FOLD"]["pass"]
                and inv["secondary_task"]["NO_CONFLICTING_EXACT_BYTECODE_LABEL"]["pass"]
                and donor_result["pass"] is True)
    inv["ALL_PASS"] = bool(all_pass)

    # ------------------------------------------- population comparability (P5)
    comp = {}
    mal_s, cle_s = primary[primary["label"] == 1], primary[primary["label"] == 0]
    gen_s = ta[ta["class"] == "benign_general"]
    primary_ops = primary["bc"].map(opcount)
    gen_ops = gen_s["bc"].map(opcount)
    comp["chain_distribution"] = {
        "malicious": mal_s["chain"].value_counts().to_dict(),
        "benign_cleared": cle_s["chain"].value_counts().to_dict(),
        "benign_general": gen_s["chain"].value_counts().to_dict(),
    }
    contingency = pd.crosstab(primary["chain"], primary["label"])
    chi2 = sstats.chi2_contingency(contingency)
    comp["chain_vs_label_chi2"] = {"chi2": float(chi2.statistic),
                                   "p": float(chi2.pvalue), "dof": int(chi2.dof)}
    comp["code_bytes"] = {
        "malicious": dist_stats(mal_s["code_bytes"]),
        "benign_cleared": dist_stats(cle_s["code_bytes"]),
        "benign_general": dist_stats(gen_s["code_bytes"]),
        "ks_mal_vs_cleared": {
            "stat": float(sstats.ks_2samp(mal_s["code_bytes"],
                                          cle_s["code_bytes"]).statistic),
            "p": float(sstats.ks_2samp(mal_s["code_bytes"],
                                       cle_s["code_bytes"]).pvalue)},
    }
    comp["opcode_count"] = {
        "malicious": dist_stats(primary_ops[primary["label"] == 1]),
        "benign_cleared": dist_stats(primary_ops[primary["label"] == 0]),
        "benign_general": dist_stats(gen_ops),
    }
    fam_sizes = primary.groupby("family_id")["key"].count()
    primary_fam_size = primary["family_id"].map(fam_sizes)
    dup_sizes = primary.groupby("h")["key"].transform("size")
    comp["family_size_per_row"] = {
        "malicious": dist_stats(primary_fam_size[primary["label"] == 1]),
        "benign_cleared": dist_stats(primary_fam_size[primary["label"] == 0]),
    }
    comp["exact_duplicate_group_size_per_row"] = {
        "malicious": dist_stats(dup_sizes[primary["label"] == 1]),
        "benign_cleared": dist_stats(dup_sizes[primary["label"] == 0]),
    }
    comp["cbor_metadata_presence"] = {
        "malicious": float(mal_s["has_cbor_metadata"].mean()),
        "benign_cleared": float(cle_s["has_cbor_metadata"].mean()),
        "benign_general": float(gen_s["has_cbor_metadata"].mean()),
    }
    comp["is_observed_eip7702_delegate"] = {
        "malicious": True, "benign_cleared": True,
        "benign_general": False, "benign_AA": "curated implementations",
    }
    comp["verified_source_status"] = "unknown for all subsets (never collected)"
    comp["acquisition_pipeline_identity"] = (
        "primary positives and primary negatives come from the SAME acquisition pipeline "
        "(USENIX eoa_detect eth_getCode dump over the 2,685 observed delegate pool) and "
        "the SAME source analysis pass; benign_general and benign_AA are separately "
        "acquired control populations")

    with open(os.path.join(AUDIT, "dataset_statistics_original.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(AUDIT, "split_invariant_audit.json"), "w") as fh:
        json.dump({"original_benchmark": inv}, fh, indent=2)
    with open(os.path.join(AUDIT, "population_comparability.json"), "w") as fh:
        json.dump(comp, fh, indent=2)
    print(json.dumps({"invariants_all_pass": inv["ALL_PASS"],
                      "label_rule_identity": out["label_rule_identity"],
                      "negative_flags": out["negative_contradiction_flags"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
