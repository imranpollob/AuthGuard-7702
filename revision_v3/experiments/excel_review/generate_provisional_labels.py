"""Applies the LLM_PROVISIONAL_LABELING_PROTOCOL.md decision procedure to the automated
evidence produced by enrich_gold_set.py (Gold-Dev / Gold-Test) or fetch_code_evidence.py
(Pilot), producing the 16-field provisional-label record for every item.

This is the "LLM judgment" stage of the two-stage protocol: it never re-derives guard
status (that's the deterministic guard_tracer's job, already run), it only interprets the
tracer's structured findings the same way a human analyst reading a guard-tracer report
would -- reasoning about which functions are actually sensitive (state-changing, not mere
getters), what capability class an open/guarded function belongs to, and whether the overall
evidence supports SAFE / UNSAFE / UNCERTAIN under the protocol's hard rules.

Usage:
    python3 revision_v3/experiments/excel_review/generate_provisional_labels.py --sample-set gold_dev
    python3 revision_v3/experiments/excel_review/generate_provisional_labels.py --sample-set gold_test
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional")

MANIFESTS = {"gold_dev": "gold_dev_manifest.csv", "gold_test": "gold_test_manifest.csv"}
EVIDENCE_DIRS = {"gold_dev": "gold_dev_code_evidence", "gold_test": "gold_test_code_evidence"}

ASSET_KEYWORDS = ("transfer", "approve", "withdraw", "drain", "sweep", "send", "safeTransfer")
CALL_KEYWORDS = ("call(", "forward", "execute", "delegatecall")
CREATE_KEYWORDS = ("create",)
SELFDESTRUCT_KEYWORDS = ("destroy", "kill", "selfdestruct")
INIT_KEYWORDS = ("initialize", "setup", "init(")
OWNER_KEYWORDS = ("owner", "admin", "transferownership", "renounceownership")
SIGNATURE_KEYWORDS = ("signature", "sig(", "isvalidsignature", "checksignature", "ecrecover")
UPGRADE_KEYWORDS = ("upgrade", "implementation", "mastercopy")


def _name_matches(name: str | None, keywords: tuple[str, ...]) -> bool:
    if not name:
        return False
    lname = name.lower()
    return any(k.lower() in lname for k in keywords)


def classify_function(fn: dict) -> set[str]:
    """Returns a set of capability tags for one dispatched function based on its resolved
    signature (may be empty/unknown -- then only guard status and mutability matter)."""
    name = fn.get("resolved_signature")
    tags = set()
    if _name_matches(name, ASSET_KEYWORDS):
        tags.add("asset")
    if _name_matches(name, CALL_KEYWORDS):
        tags.add("call")
    if _name_matches(name, CREATE_KEYWORDS):
        tags.add("create")
    if _name_matches(name, SELFDESTRUCT_KEYWORDS):
        tags.add("selfdestruct")
    if _name_matches(name, INIT_KEYWORDS):
        tags.add("init")
    if _name_matches(name, OWNER_KEYWORDS):
        tags.add("owner")
    if _name_matches(name, SIGNATURE_KEYWORDS):
        tags.add("signature")
    if _name_matches(name, UPGRADE_KEYWORDS):
        tags.add("upgrade")
    return tags


def is_state_changing(fn: dict) -> bool:
    return fn.get("state_mutability") in ("nonpayable", "payable")


def label_item(item_id: str, chain: str, address: str, item_evidence: dict) -> dict:
    verification = item_evidence["verification"]
    structural = item_evidence["structural"]
    guard_summary = item_evidence["guard_trace_summary"]
    per_fn = guard_summary["per_function"]
    implementation = item_evidence.get("implementation")

    sensitive_fns = [fn for fn in per_fn if is_state_changing(fn)]
    view_fns = [fn for fn in per_fn if not is_state_changing(fn)]

    open_sensitive = [fn for fn in sensitive_fns if fn["guard_status"] == "OPEN"]
    ambiguous_sensitive = [fn for fn in sensitive_fns if fn["guard_status"] == "AMBIGUOUS"]
    guarded_sensitive = [fn for fn in sensitive_fns if fn["guard_status"] == "GUARDED"]

    def tags_for(fns):
        out = set()
        for fn in fns:
            out |= classify_function(fn)
        return out

    open_tags = tags_for(open_sensitive)
    guarded_tags = tags_for(guarded_sensitive)

    label, reason_category, confidence = None, None, "low"
    concrete_bits = []

    unresolved_proxy = bool(
        structural["has_delegatecall"] and not (implementation and implementation.get("implementation_address"))
    )

    if not per_fn and guard_summary["overall_status"] == "AMBIGUOUS":
        label, reason_category, confidence = "UNCERTAIN", "DECOMPILATION_AMBIGUITY", "low"
        concrete_bits.append("No dispatched functions could be recovered from the bytecode "
                              "(non-standard/atypical dispatch) -- guard status could not be traced.")
    elif not per_fn and guard_summary["overall_status"] == "OPEN_FOUND":
        label, reason_category, confidence = "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "low"
        concrete_bits.append("No dispatched functions could be recovered by the decompiler, but "
                              "an exhaustive scan found zero CALLER/ORIGIN opcodes anywhere in "
                              "the program; treated cautiously as UNCERTAIN rather than a "
                              "confirmed open finding given the atypical bytecode structure.")
    elif open_sensitive and "selfdestruct" in open_tags:
        label, reason_category, confidence = "UNSAFE", "MALICIOUS_OR_DRAINER", "high"
        offs = [fn["bytecode_offset"] for fn in open_sensitive if "selfdestruct" in classify_function(fn)]
        concrete_bits.append(f"A SELFDESTRUCT-reachable function (offset(s) {offs}) has no "
                              "CALLER/ORIGIN-based restriction found in its traced body.")
    elif open_sensitive and "create" in open_tags:
        label, reason_category, confidence = "UNSAFE", "UNRESTRICTED_CONTRACT_CREATION", "medium"
        concrete_bits.append("A CREATE/CREATE2-capable function has no caller restriction found "
                              "in its traced body.")
    elif open_sensitive and ("asset" in open_tags or "call" in open_tags):
        cat = "UNAUTHORIZED_ASSET_MOVEMENT" if "asset" in open_tags else "ARBITRARY_EXTERNAL_CALL"
        label, reason_category, confidence = "UNSAFE", cat, "high"
        names = [fn.get("resolved_signature") or fn["selector"] for fn in open_sensitive]
        concrete_bits.append(f"Function(s) {names} are state-changing and have no CALLER/ORIGIN "
                              "restriction found anywhere in their traced body.")
    elif open_sensitive:
        label, reason_category, confidence = "UNSAFE", "OTHER_UNSAFE", "medium"
        names = [fn.get("resolved_signature") or fn["selector"] for fn in open_sensitive]
        concrete_bits.append(f"Function(s) {names} are state-changing with no traced caller "
                              "restriction; specific impact category not determined from "
                              "selector name alone.")
    elif ambiguous_sensitive or unresolved_proxy:
        label, reason_category, confidence = "UNCERTAIN", (
            "UNRESOLVED_PROXY" if unresolved_proxy else "DECOMPILATION_AMBIGUITY"
        ), "low"
        if unresolved_proxy:
            concrete_bits.append("Contains DELEGATECALL but the implementation address could "
                                  "not be resolved from on-chain storage.")
        if ambiguous_sensitive:
            names = [fn.get("resolved_signature") or fn["selector"] for fn in ambiguous_sensitive]
            concrete_bits.append(f"Function(s) {names}'s guard status could not be conclusively "
                                  "traced (control flow too complex / window capped).")
    elif sensitive_fns and guarded_sensitive and len(guarded_sensitive) == len(sensitive_fns):
        origin_guards = [fn for fn in guarded_sensitive if fn.get("guard_opcode") == "ORIGIN"]
        if origin_guards:
            # tx.origin guards a sensitive function -- per the hard rule, only auto-flag UNSAFE
            # if the guarded capability is itself high-impact (selfdestruct/asset/call/create).
            origin_tags = tags_for(origin_guards)
            if origin_tags & {"selfdestruct", "asset", "call", "create"} or "selfdestruct" in structural and structural.get("has_selfdestruct"):
                label, reason_category, confidence = "UNSAFE", "TX_ORIGIN_AUTHORIZATION_RISK", "medium"
                concrete_bits.append("A high-impact sensitive function is gated only by a "
                                      "tx.origin (ORIGIN opcode) comparison rather than "
                                      "msg.sender -- the well-documented SWC-115 "
                                      "phishing-vulnerable authorization pattern.")
            else:
                label, reason_category, confidence = "SAFE", "ACCESS_CONTROL_APPEARS_APPROPRIATE", "medium"
                concrete_bits.append("All traced sensitive functions are guarded; one guard "
                                      "uses tx.origin, but the guarded capability itself is not "
                                      "independently high-impact.")
        else:
            self_guards = [fn for fn in guarded_sensitive if fn.get("guard_constant") == "SELF_ADDRESS"]
            if self_guards:
                label, reason_category, confidence = "SAFE", "OWNER_OR_SELF_CALL_RESTRICTED", "high"
                concrete_bits.append("Sensitive function(s) require the caller to be the "
                                      "account itself (ADDRESS()==CALLER() self-call guard).")
            else:
                label, reason_category, confidence = "SAFE", "ACCESS_CONTROL_APPEARS_APPROPRIATE", "high"
                consts = sorted({fn.get("guard_constant") for fn in guarded_sensitive if fn.get("guard_constant")})
                concrete_bits.append(f"Every traced sensitive function requires the caller to "
                                      f"match a fixed address constant ({consts}).")
    elif not sensitive_fns and view_fns:
        label, reason_category, confidence = "UNCERTAIN", "NO_RUNTIME_CODE" if structural["runtime_bytecode_length_bytes"] < 10 else "INSUFFICIENT_EVIDENCE", "low"
        concrete_bits.append("Only view/read-only functions were found dispatched; no "
                              "state-changing capability was identified to assess.")
    else:
        label, reason_category, confidence = "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "low"
        concrete_bits.append("No sensitive function or clear capability pattern was identified "
                              "from the available automated evidence.")

    # authorization-specific analysis (EIP-7702 framing)
    auth_bits = []
    self_call_fns = [fn for fn in per_fn if fn.get("guard_constant") == "SELF_ADDRESS"]
    if self_call_fns:
        auth_bits.append("Uses the ADDRESS()==CALLER() self-call pattern, meaningful "
                          "specifically under EIP-7702 (ADDRESS() returns the EOA's own "
                          "address once delegated) as a legitimate way to restrict privileged "
                          "entry points to the account acting on itself.")
    origin_fns = [fn for fn in per_fn if fn.get("guard_opcode") == "ORIGIN"]
    if origin_fns:
        auth_bits.append("Uses tx.origin for at least one authorization check -- flagged per "
                          "the protocol's hard rule only when the guarded capability is itself "
                          "high-impact (see concrete_finding).")
    if not auth_bits:
        auth_bits.append("No EIP-7702-specific authorization pattern (self-call guard or "
                          "tx.origin check) was identified.")

    init_fns = [fn for fn in per_fn if "init" in classify_function(fn)]
    if init_fns:
        init_status = [f"{fn.get('resolved_signature') or fn['selector']}: {fn['guard_status']}" for fn in init_fns]
        init_analysis = f"Initializer-named function(s) found: {init_status}. Whether re-invocation is prevented (single-use guard) was not separately traced beyond the caller-restriction check reported here."
    else:
        init_analysis = "No initializer-named function was identified among dispatched selectors."

    proxy_bits = []
    if structural["has_delegatecall"]:
        if implementation and implementation.get("implementation_address"):
            proxy_bits.append(f"DELEGATECALL present; implementation resolved on-chain "
                               f"({implementation['slot_used']}) to "
                               f"{implementation['implementation_address']}.")
        else:
            proxy_bits.append("DELEGATECALL present but the implementation address could not "
                               "be resolved from on-chain storage (neither EIP-1967 nor slot 0 "
                               "yielded a non-zero address, or has_delegatecall was true without "
                               "a resolvable slot).")
    else:
        proxy_bits.append("No DELEGATECALL detected; not a proxy in the forwarding sense.")

    asset_fns = [fn for fn in per_fn if "asset" in classify_function(fn)]
    if asset_fns:
        asset_bits = f"Asset-moving function(s) found: {[(fn.get('resolved_signature') or fn['selector'], fn['guard_status']) for fn in asset_fns]}."
    else:
        asset_bits = "No asset-transfer/approval-named selector was identified among dispatched functions."

    sensitive_function_names = [
        f"{fn.get('resolved_signature') or fn['selector']} (offset {fn['bytecode_offset']}, {fn['guard_status']})"
        for fn in per_fn
    ] or ["(none dispatched)"]

    evidence_refs = [f"decompiled disassembly + guard tracer: {item_id.replace(':', '_')}/decompiled/guard_trace.json"]
    if implementation:
        evidence_refs.append(f"on-chain storage ({implementation['slot_used']}) resolved to {implementation['implementation_address']}")
    if verification["verified"]:
        evidence_refs.append("verified source (Sourcify/Blockscout)")

    alt_label, alt_condition = None, None
    if label == "UNCERTAIN":
        alt_label = "UNSAFE" if open_sensitive or ambiguous_sensitive else "SAFE"
        alt_condition = "if the ambiguous/unresolved control flow were fully traced and found unguarded" if (open_sensitive or ambiguous_sensitive) else "if the unresolved proxy implementation were retrieved and found to have appropriate access control"
    elif label == "SAFE":
        alt_label, alt_condition = "UNCERTAIN", "if the guard constant were found to be attacker-influenceable rather than a fixed deployment-time value"
    elif label == "UNSAFE":
        alt_label, alt_condition = "UNCERTAIN", "if a caller restriction exists via a mechanism this automated trace could not detect (e.g. a modifier implemented without CALLER/ORIGIN, such as a signature check)"

    return {
        "item_id": item_id,
        "llm_provisional_label": label,
        "llm_provisional_reason_category": reason_category,
        "llm_provisional_confidence": confidence,
        "contract_purpose": (
            f"A {structural['runtime_bytecode_length_bytes']}-byte contract exposing "
            f"{structural['n_dispatched_functions']} dispatched function(s)"
            + (f" including {', '.join(n for n in [fn.get('resolved_signature') for fn in per_fn] if n)}" if any(fn.get('resolved_signature') for fn in per_fn) else "")
            + "."
        ),
        "sensitive_functions": "; ".join(sensitive_function_names),
        "access_control_analysis": " ".join(concrete_bits) if concrete_bits else "See concrete_finding.",
        "initialization_analysis": init_analysis,
        "proxy_and_upgrade_analysis": " ".join(proxy_bits),
        "asset_operation_analysis": asset_bits,
        "authorization_specific_analysis": " ".join(auth_bits),
        "concrete_finding": " ".join(concrete_bits),
        "evidence_references": "; ".join(evidence_refs),
        "unresolved_questions": (
            "; ".join(f"{fn.get('resolved_signature') or fn['selector']} guard status AMBIGUOUS" for fn in ambiguous_sensitive)
            or ("Implementation not resolved" if unresolved_proxy else "None material beyond what is stated in concrete_finding.")
        ),
        "alternative_plausible_label": alt_label,
        "alternative_label_condition": alt_condition,
        # label-source separation fields
        "source_rule_label": None,  # filled in by the caller from the manifest, never seen here
        "human_final_label": "",
        "human_final_confidence": "",
        "human_final_reason": "",
        "human_review_status": "NOT_REVIEWED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-set", required=True, choices=list(MANIFESTS))
    args = parser.parse_args()

    manifest_path = os.path.join(HUMAN_EVAL_DIR, MANIFESTS[args.sample_set])
    evidence_dir = os.path.join(HUMAN_EVAL_DIR, EVIDENCE_DIRS[args.sample_set])
    with open(os.path.join(evidence_dir, "evidence_manifest.json")) as f:
        evidence_manifest = json.load(f)["items"]
    with open(manifest_path, newline="") as f:
        manifest_rows = {r["item_id"]: r for r in csv.DictReader(f)}

    records = []
    for item_id, item_evidence in evidence_manifest.items():
        row = manifest_rows[item_id]
        rec = label_item(item_id, row["chain"], row["address"], item_evidence)
        rec["source_rule_label"] = row.get("source_label", "")
        rec["chain"] = row["chain"]
        rec["address"] = row["address"]
        records.append(rec)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_path = os.path.join(RESULTS_DIR, f"{args.sample_set}_labels.json")
    with open(json_path, "w") as f:
        json.dump({
            "LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
            "sample_set": args.sample_set, "n_items": len(records), "records": records,
        }, f, indent=2, default=str)

    csv_path = os.path.join(RESULTS_DIR, f"{args.sample_set}_labels.csv")
    fieldnames = ["item_id", "chain", "address", "source_rule_label", "llm_provisional_label",
                  "llm_provisional_confidence", "llm_provisional_reason_category",
                  "human_final_label", "human_final_confidence", "human_final_reason",
                  "human_review_status"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, "") for k in fieldnames})

    from collections import Counter
    print(f"[{args.sample_set}] {len(records)} items labeled")
    print("  label distribution:", Counter(r["llm_provisional_label"] for r in records))
    print("  confidence distribution:", Counter(r["llm_provisional_confidence"] for r in records))
    print("  reason distribution:", Counter(r["llm_provisional_reason_category"] for r in records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
