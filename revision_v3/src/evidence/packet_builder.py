"""Automated, deterministic evidence-packet builder for human review.

HARD RULE, enforced by construction: this module never reads or accepts as input any of
{label, label_semantics, label_source, label_evidence_type, label_strength, AuthGuard score,
AuthGuard prediction, calibrated_score, raw_score, other reviewers' judgments}. The only
inputs are bytecode-derived facts (chain, address, runtime bytecode) plus optional,
neutral, publicly-documented project metadata (explorer links, known-project docs). Callers
must not pass label/score columns in `row` -- see `FORBIDDEN_FIELDS` below, checked at
runtime.

Fields NOT available offline (transaction/authorization history, live source-verification
status) are explicitly marked "NOT_AVAILABLE_OFFLINE" with a reason, never silently omitted
or fabricated.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from evidence.explorer_links import explorer_link
from evidence.known_projects import known_project_evidence
from evidence.proxy_detection import compute_proxy_evidence
from evidence.selectors_table import ADMIN_OWNERSHIP_SIGNATURES
from features.disassembler import linear_sweep, normalize_hex
from features.selectors import GENERIC_SIGNATURES, TOKEN_MOVEMENT_SIGNATURES, build_sensitive_selector_set
from features.structural import compute_structural_features

FORBIDDEN_FIELDS = {
    "label", "label_semantics", "label_source", "label_evidence_type", "label_strength",
    "authguard_score", "authguard_prediction", "raw_score", "calibrated_score",
    "model_score", "reviewer_judgment", "other_reviewer_labels", "is_false_positive",
    "is_false_negative",
}


def _assert_no_forbidden_fields(row: dict) -> None:
    present = FORBIDDEN_FIELDS & set(k.lower() for k in row.keys())
    if present:
        raise ValueError(
            f"evidence packet builder refuses input containing forbidden fields: {present} "
            "-- evidence packets must never carry model scores or source labels"
        )


def _anonymize_id(sample_id: str, salt: str = "revision_v3_evidence") -> str:
    digest = hashlib.blake2b(f"{salt}:{sample_id}".encode(), digest_size=8).hexdigest()
    return f"EV_{digest}"


def _token_transfer_and_approval_evidence(selector_set: set[str]) -> dict:
    movement = {sig: GENERIC_SIGNATURES[sig] in selector_set for sig in TOKEN_MOVEMENT_SIGNATURES}
    approval_present = GENERIC_SIGNATURES.get("approve(address,uint256)") in selector_set
    return {
        "token_movement_selectors_present": {k: v for k, v in movement.items() if v},
        "any_token_movement_selector_present": any(movement.values()),
        "approval_selector_present": approval_present,
    }


def _deterministic_summary(fields: dict) -> str:
    """Template-based (no LLM) plain-language summary of the extracted evidence, for the
    reviewer's quick orientation -- states facts only, no risk judgment."""
    lines = []
    lines.append(f"Runtime bytecode length: {fields['runtime_bytecode_length_bytes']} bytes "
                 f"({fields['opcode_count']} decoded opcodes).")
    if fields["proxy_evidence"]["is_eip7702_designator"]:
        lines.append(f"This entry is an EIP-7702 authorization designator pointing to "
                     f"{fields['proxy_evidence']['designator_target_address']}.")
    if fields["proxy_evidence"]["has_delegatecall"]:
        lines.append(f"Contains {fields['proxy_evidence']['delegatecall_count']} DELEGATECALL "
                     f"instruction(s)."
                     + (" Pattern resembles a minimal forwarding proxy (short bytecode, no SSTORE)."
                        if fields["proxy_evidence"]["resembles_minimal_forwarder"] else ""))
    if any(fields["proxy_evidence"].get(k) for k in
           ("eip1967_implementation_slot_present", "eip1967_admin_slot_present", "eip1967_beacon_slot_present")):
        lines.append("Contains a byte sequence matching a standard EIP-1967 proxy storage slot constant.")
    if fields["proxy_evidence"]["any_admin_ownership_selector_present"]:
        present = list(fields["proxy_evidence"]["admin_ownership_selectors_present"].keys())
        lines.append(f"Contains selector(s) matching common ownership/admin/init signatures: {', '.join(present)}.")
    if fields["token_transfer_evidence"]["any_token_movement_selector_present"]:
        present = [k for k, v in fields["token_transfer_evidence"]["token_movement_selectors_present"].items() if v]
        lines.append(f"Contains token-transfer selector(s): {', '.join(present)}.")
    if fields["token_transfer_evidence"]["approval_selector_present"]:
        lines.append("Contains an approve(address,uint256) selector.")
    lines.append(f"Structural counts: CALL={fields['structural']['n_call']}, "
                f"STATICCALL={fields['structural']['n_staticcall']}, "
                f"DELEGATECALL={fields['structural']['n_delegatecall']}, "
                f"CREATE/CREATE2={fields['structural']['n_create']}, "
                f"SSTORE={fields['storage_operations']['n_sstore']}, SLOAD={fields['storage_operations']['n_sload']}, "
                f"SELFDESTRUCT={fields['structural']['n_selfdestruct']}, LOG={fields['structural']['n_log']}.")
    if fields["structural"]["has_sensitive_selector"]:
        lines.append(f"Contains {fields['structural']['n_sensitive_selectors']} selector(s) "
                     "matching the project's sensitive-name reference list "
                     "(sweep/drain/attack-style names or source-analyzer-flagged names).")
    if fields["known_project"] is not None:
        lines.append(f"Address is documented as {fields['known_project']['project']} "
                     f"({fields['known_project']['documentation_url']}).")
    return " ".join(lines)


def build_evidence_packet(row: dict, sensitive_selectors: set[str] | None = None) -> dict:
    """row must contain: sample_id, chain, address, runtime_bytecode, code_bytes (optional).
    Must NOT contain any field in FORBIDDEN_FIELDS."""
    _assert_no_forbidden_fields(row)
    sensitive_selectors = sensitive_selectors if sensitive_selectors is not None else build_sensitive_selector_set()

    hex_str = normalize_hex(row["runtime_bytecode"])
    tokens, push_sizes, selector_set = linear_sweep(hex_str)
    struct_fields, _ = compute_structural_features(hex_str, sensitive_selectors)
    proxy_evidence = compute_proxy_evidence(hex_str)
    token_transfer_evidence = _token_transfer_and_approval_evidence(selector_set)
    bytecode_sha256 = hashlib.sha256(bytes.fromhex(hex_str) if hex_str else b"").hexdigest()

    packet = {
        "anon_id": _anonymize_id(str(row["sample_id"])),
        "chain": row.get("chain"),
        "address": row.get("address"),
        "runtime_bytecode_sha256": bytecode_sha256,
        "runtime_bytecode_length_bytes": len(hex_str) // 2,
        "opcode_count": len(tokens),
        "opcode_disassembly": tokens,
        "decompiled_or_source_representation": {
            "status": "NOT_AVAILABLE_OFFLINE",
            "reason": "No decompiler (e.g. Gigahorse) or verified-source API is wired into "
                      "this offline pipeline; only linear-sweep disassembly is available.",
        },
        "verified_source_code_availability": {
            "status": "NOT_DETERMINABLE_OFFLINE",
            "reason": "Requires a live block-explorer verified-source API call, not performed here.",
        },
        "proxy_evidence": proxy_evidence,
        "storage_operations": {
            "n_sstore": struct_fields["n_sstore"], "n_sload": struct_fields["n_sload"],
        },
        "structural": {
            "n_call": struct_fields["n_call"], "n_staticcall": struct_fields["n_staticcall"],
            "n_delegatecall": struct_fields["n_delegatecall"], "n_callcode": struct_fields["n_callcode"],
            "n_create": struct_fields["n_create"], "n_selfdestruct": struct_fields["n_selfdestruct"],
            "n_log": struct_fields["n_log"], "n_jump": struct_fields["n_jump"],
            "n_jumpi": struct_fields["n_jumpi"], "n_jumpdest": struct_fields["n_jumpdest"],
            "n_push": struct_fields["n_push"], "has_sensitive_selector": struct_fields["has_sensitive_selector"],
            "n_sensitive_selectors": struct_fields["n_sensitive_selectors"],
        },
        "token_transfer_evidence": token_transfer_evidence,
        "authorization_history": {
            "status": "NOT_AVAILABLE_OFFLINE",
            "reason": "Requires the temporal collector (revision_v3/temporal/) or an "
                      "archive-node/indexer query, not performed for this packet.",
        },
        "transaction_history_statistics": {
            "status": "NOT_AVAILABLE_OFFLINE",
            "reason": "Requires a live RPC/indexer query, not performed for this packet.",
        },
        "explorer_link": explorer_link(row.get("chain"), row.get("address")),
        "known_project": known_project_evidence(row.get("chain", ""), row.get("address", "")),
        "audit_links": {
            "status": "NOT_AVAILABLE_OFFLINE" if known_project_evidence(row.get("chain", ""), row.get("address", "")) is None
            else "SEE_KNOWN_PROJECT_DOCUMENTATION_URL",
        },
        "packet_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "packet_generator_version": "revision_v3.evidence.packet_builder.v1",
    }
    packet["deterministic_summary"] = _deterministic_summary(packet)
    return packet
