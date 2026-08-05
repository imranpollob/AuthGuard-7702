"""Opus 5 provisional labeling of EIP-7702 delegates.

This module encodes the analysis framework applied to every item, so that the same reasoning
is applied identically to all 230 items and every label is auditable against the evidence that
produced it. Per-item manual overrides live in `overrides.py` and take precedence; each
override records why the framework's output was wrong for that item.

Static-analyzer evidence is VISIBLE to this procedure (that is the point of this pass), but it
is used as *evidence*, never as an automatic verdict — see `assess_source_analyzer()`.

The framework in brief
----------------------
For an EIP-7702 delegate, the security question is: after the EOA authorizes this code, can a
party other than the account owner reach an operation that spends, approves, or reassigns
authority over the EOA's assets?

Two facts about the 7702 execution context drive every rule below:

  (a) The EOA's storage is EMPTY at authorization time. The delegate's constructor never ran
      against it. So any authority slot (`owner`, `initialized`, `implementation`) reads as
      zero unless something in the delegate explicitly writes it.
  (b) `ADDRESS()` is the EOA itself, so `msg.sender == address(this)` is the canonical way a
      smart account restricts an action to "a transaction the account owner sent from this
      very account".

Consequences encoded here:

  * `self_call_check` is genuine authorization → supports SAFE.
  * `msg.sender == SLOAD(slot)` on a fresh EOA compares against the zero address, which no
    real caller can equal → the function is unreachable in practice → not a danger, UNLESS an
    unguarded write to that slot exists, in which case whoever writes first takes the account.
  * `msg.sender == <hardcoded constant>` does NOT protect the authorizer: the constant was
    fixed when the delegate was deployed and cannot be the authorizing EOA. It means a fixed
    third party has exclusive privileged access to the EOA's assets. Unless that constant is a
    recognized ERC-4337 EntryPoint, a guarded-but-third-party asset path is a drainer pattern,
    not access control.
  * `tx.origin == msg.sender` is not authorization at all: an attacker calling the EOA
    directly satisfies both. Treated as no guard.
  * Forwarding `msg.value` (the ETH the caller themselves just sent) to a fixed address is not
    a drain of the EOA — the caller would be donating. Only paths that can move assets the EOA
    already holds, or grant approvals over them, count as asset movement.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

V3_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, V3_SRC)
from analysis.protocol_actors import ERC4337_ENTRYPOINT_ADDRESSES

# Recognized ERC-4337 EntryPoint deployments. A caller check against one of these is a
# legitimate smart-account pattern, not a fixed-third-party backdoor.
ENTRYPOINTS = {
    *ERC4337_ENTRYPOINT_ADDRESSES,
    "0x0000000000000000000000000000000000000001",  # ecrecover precompile (not an EntryPoint,
                                                   # but never a "third-party owner")
}

ASSET_MOVING = {"external_call_or_value_transfer", "delegatecall", "selfdestruct", "callcode"}

# Well-known protocol contracts. A caller check against one of these on a callback entry point
# is the protocol's prescribed defensive pattern ("only the pool manager may call me back"),
# not a fixed-third-party backdoor over the account's assets.
KNOWN_PROTOCOL_CALLERS = {
    "0x000000000004444c5dc75cb358380d2e3de08a90": "Uniswap v4 PoolManager",
    "0x000000000022d473030f116ddee9f6b43ac78ba3": "Permit2",
    "0x00000000000000000000000000000000000000ff": "placeholder (never matched in practice)",
}


def _looks_like_callback(sig: str) -> bool:
    """Callback entry points are invoked BY a protocol during an operation the account itself
    started, so restricting them to that protocol's address is correct design rather than a
    third party holding privileged access."""
    s_ = (sig or "").lower()
    return ("callback" in s_ or s_.startswith("on") or "received" in s_
            or "hook" in s_ or s_.startswith("unlock"))


# ----------------------------------------------------------------------------------------
# Evidence extraction
# ----------------------------------------------------------------------------------------

def classify_guard(g: dict, fn_signature: str = "") -> Tuple[str, str]:
    """Classify what a guard actually achieves for the *authorizing EOA*.

    Returns (class, explanation) with class in:
      PROTECTS_OWNER    -- only the account owner (or a party the owner signed for) passes
      THIRD_PARTY_ONLY  -- passes only for an address fixed at delegate-deployment time, which
                           cannot be the authorizing EOA
      NOT_AUTHORIZATION -- the branch depends on an authorization source but does not restrict
                           an attacker (tx.origin == msg.sender, comparisons against
                           caller-supplied calldata, zero-address sanity checks)
      UNRESOLVED        -- a caller/origin comparison whose operand the analyser could not
                           resolve
    """
    sem = g["semantics"]
    const = (g.get("compared_address_constant") or "").lower()
    if sem.startswith("self_call_check"):
        return "PROTECTS_OWNER", ("self-call restriction: passes only for a transaction the "
                                  "authorizing account sent to itself")
    if sem.startswith("signature_authorization"):
        return "PROTECTS_OWNER", "signature authorization (ecrecover-derived branch)"
    if sem.startswith("storage_based_caller_check"):
        return "PROTECTS_OWNER", ("msg.sender compared against a stored authority; note that in "
                                  "the EOA's own storage that slot is zero until written")
    if sem.startswith("tx.origin == msg.sender"):
        return "NOT_AUTHORIZATION", ("tx.origin == msg.sender only rejects contract "
                                     "intermediaries; an attacker calling the account directly "
                                     "satisfies it")
    if sem.startswith("calldata_comparison"):
        return "NOT_AUTHORIZATION", ("the value compared against is supplied by the caller, so "
                                     "the caller can satisfy the comparison at will")
    if sem.startswith("zero_address_check"):
        return "NOT_AUTHORIZATION", "comparison against address(0) is a sanity check, not access control"
    if sem.startswith("hardcoded_address_check"):
        if const in ENTRYPOINTS:
            return "PROTECTS_OWNER", f"caller restricted to a recognized ERC-4337 EntryPoint ({const})"
        if const in KNOWN_PROTOCOL_CALLERS:
            return "CALLBACK_RESTRICTION", (
                f"caller restricted to {KNOWN_PROTOCOL_CALLERS[const]} ({const}), a known "
                f"protocol contract — the prescribed pattern for a callback entry point")
        if _looks_like_callback(fn_signature):
            return "CALLBACK_RESTRICTION", (
                f"{fn_signature} is a callback-shaped entry point restricted to the fixed "
                f"address {const}; a callback is invoked by a protocol during an operation the "
                f"account itself started, so this reads as the protocol's prescribed restriction "
                f"rather than standing third-party access. The identity of {const} was not "
                f"independently confirmed.")
        who = "tx.origin" if "tx.origin" in sem else "msg.sender"
        return "THIRD_PARTY_ONLY", (
            f"{who} must equal the hardcoded address {const}. That literal was fixed when the "
            f"delegate was deployed, so it cannot be the authorizing EOA: this is not protection "
            f"for the authorizer, it is exclusive privileged access for a fixed third party")
    if sem.startswith("caller_check") or sem.startswith("tx_origin_check"):
        return "UNRESOLVED", (f"{sem}; the analyser could not resolve what the caller is "
                              f"compared against, so whether this restricts an attacker is "
                              f"undetermined")
    return "UNRESOLVED", sem


def summarize_functions(cfg: dict) -> dict:
    """Collapse per-function CFG results into the facts the decision rules need."""
    out = {
        "unguarded_arbitrary_call": [],     # attacker-chosen target
        "unguarded_value_drain": [],        # fixed/stored target, but moves the account's own funds
        "unguarded_capability_call": [],    # unauthenticated call whose exploitability is unproven
        "unguarded_passthrough_call": [],   # only forwards msg.value
        "unguarded_delegatecall": [],
        "unguarded_selfdestruct": [],
        "unguarded_create": [],
        "unguarded_authority_write": [],    # SSTORE to a low slot with no caller check
        "third_party_guarded_asset": [],    # guarded, but by a hardcoded non-EntryPoint addr
        "unresolved_guard_only": [],        # guarded, but the comparison operand is unknown
        "callback_restricted": [],          # guarded to a protocol contract on a callback entry
        "self_call_guarded": [],
        "signature_guarded": [],
        "storage_authority_guarded": [],
        "origin_equals_caller_only": [],
        "entrypoint_guarded": [],
        "initializer_unrestricted": [],
        "incomplete_functions": [],
        "n_functions": cfg.get("n_functions", 0),
    }
    for fn in cfg.get("per_function", []):
        sel = fn.get("resolved_signature") or fn["selector"]
        if fn.get("analysis_incomplete"):
            out["incomplete_functions"].append(sel)

        classes = []
        for g in fn.get("guards", []):
            cls, why = classify_guard(g, fn.get("resolved_signature") or "")
            classes.append((cls, g, why))
            sem = g["semantics"]
            if sem.startswith("self_call_check"):
                out["self_call_guarded"].append(sel)
            elif sem.startswith("signature_authorization"):
                out["signature_guarded"].append(sel)
            elif sem.startswith("storage_based_caller_check"):
                out["storage_authority_guarded"].append(sel)
            elif sem.startswith("tx.origin == msg.sender"):
                out["origin_equals_caller_only"].append(sel)
            elif cls == "PROTECTS_OWNER" and (g.get("compared_address_constant") or "").lower() in ENTRYPOINTS:
                out["entrypoint_guarded"].append(sel)

        status = fn["guard_status"]
        # Only capabilities surviving cuts at BOTH strong and storage-derived guards are
        # unauthenticated. ``unguarded_sensitive`` is the broader diagnostic set that survives
        # strong-guard cuts and therefore includes storage-condition-gated paths.
        unguarded = fn.get("unguarded_even_by_storage",
                           fn.get("unguarded_sensitive", []))
        protects = [c for c in classes if c[0] in ("PROTECTS_OWNER", "CALLBACK_RESTRICTION")]
        for cls, g, why in classes:
            if cls == "CALLBACK_RESTRICTION":
                out["callback_restricted"].append((sel, why))

        # A function the analyzer called GUARD_DOMINATED, but whose only guard is a hardcoded
        # third-party address, is effectively "someone else owns your account".
        if status == "GUARDED_BY_STORAGE_CONDITION":
            out["unresolved_guard_only"].append((
                sel,
                "a sensitive path is gated only by a storage-derived condition; without "
                "source/state semantics the condition cannot be assumed to encode authority",
            ))
        elif status == "GUARD_DOMINATED" and not protects and fn.get("n_reachable_sensitive", 0):
            for cls, g, why in classes:
                if cls == "THIRD_PARTY_ONLY":
                    out["third_party_guarded_asset"].append(
                        (sel, g.get("compared_address_constant"), why))
                elif cls == "UNRESOLVED":
                    out["unresolved_guard_only"].append((sel, why))

        # Initializer-shaped entry points with a reachable unauthenticated storage write are
        # the signature EIP-7702 takeover: the EOA's storage starts empty, so the first caller
        # to reach the initializer installs whatever authority it establishes.
        name = (fn.get("resolved_signature") or "").lower()
        if (any(k in name for k in ("initial", "setup(", "init(")) and unguarded
                and any(u["impact"] == "storage_write" for u in unguarded)):
            out["initializer_unrestricted"].append((sel, fn["entry_pc"]))

        # If the stack model had to be padded for this function, argument provenance for its
        # calls is not trustworthy: a padded UNKNOWN can masquerade as, or mask, a
        # calldata-derived target. Such findings are demoted to capability, never used as the
        # basis for a concrete-exploit claim.
        provenance_reliable = not fn.get("stack_underflows")
        for u in unguarded:
            imp = u["impact"]
            tsrc, vsrc = set(u.get("target_src") or []), set(u.get("value_src") or [])
            tconst = u.get("target_const")
            if imp == "selfdestruct":
                out["unguarded_selfdestruct"].append((sel, u["pc"]))
            elif imp == "contract_creation":
                out["unguarded_create"].append((sel, u["pc"]))
            elif imp == "delegatecall":
                out["unguarded_delegatecall"].append((sel, u["pc"], tconst or sorted(tsrc)))
            elif imp in ("external_call_or_value_transfer", "callcode"):
                if "calldata" in tsrc and provenance_reliable:
                    out["unguarded_arbitrary_call"].append((sel, u["pc"], "target from calldata"))
                elif "calldata" in tsrc:
                    out["unguarded_capability_call"].append(
                        (sel, u["pc"], "calldata-derived target",
                         "value=unresolved",
                         "argument provenance unreliable: the stack model was padded for this "
                         "function"))
                else:
                    # Fixed, stored, or unresolved destination. The distinction that matters is
                    # whether the call can move funds the ACCOUNT already holds. Note that data
                    # assembled in memory carries no provenance through this analyser, so
                    # "fixed target + memory data" does NOT establish attacker controllability
                    # and must not be reported as a concrete exploit path.
                    vconst = u.get("value_const")
                    tgt = (tconst or ("stored(sload)" if "sload" in tsrc else "unresolved"))
                    if vsrc == {"callvalue"}:
                        out["unguarded_passthrough_call"].append((sel, u["pc"], tgt))
                    elif (vsrc & {"selfbalance", "balance", "sload", "calldata"}
                          or (vconst not in (0, None) and vconst > 0)):
                        out["unguarded_value_drain"].append(
                            (sel, u["pc"], tgt,
                             "value from " + (",".join(sorted(vsrc)) if vsrc else f"literal {vconst}")))
                    else:
                        out["unguarded_capability_call"].append(
                            (sel, u["pc"], tgt,
                             "value=" + (str(vconst) if vconst is not None
                                         else ",".join(sorted(vsrc)) or "unresolved"),
                             "data=" + (",".join(sorted(u.get("data_src") or [])) or "-")))
            elif imp == "storage_write":
                slot = u.get("storage_slot")
                if slot is not None and int(slot, 16) < 16:
                    out["unguarded_authority_write"].append((sel, u["pc"], slot))
    return out


def assess_source_analyzer(d: dict, s: dict, cfg: dict) -> Tuple[str, str]:
    """Judge the source analyzer's verdict against the CFG evidence.

    Returns (verdict, explanation) with verdict in
    {CONFIRMED, PARTIALLY_CONFIRMED, CONTRADICTED, UNRESOLVED}.
    """
    src = d["source_static_analyzer_evidence"]
    label = src["source_rule_label"]
    rep = src.get("local_reproduction_of_the_rules_question") or {}
    pattern = rep.get("source_rule_locally_reproduced")
    unauth = rep.get("unauthenticated_external_call_from_fallback_or_receive")
    n_tuples = src.get("n_rule_tuples", 0)

    if label == "positive":
        if pattern and unauth:
            return ("CONFIRMED",
                    f"The rule fired on {n_tuples} tuple(s) (enclosing function(s): "
                    f"{', '.join(sorted({t['enclosing_function'] for t in src['rule_firing_tuples_for_this_address']})) or 'n/a'}). "
                    "An independent CFG re-derivation confirms an external call is reachable "
                    "from the receive()/fallback() path, and confirms it is reachable without "
                    "passing any caller-authorization branch. The rule's reachability claim "
                    "holds and, here, the stronger unauthenticated-access claim holds too.")
        if pattern and not unauth:
            return ("PARTIALLY_CONFIRMED",
                    "The reachability the rule asserts is reproduced (an external call is "
                    "reachable from receive()/fallback()), but every such path passes an "
                    "authorization branch. The rule is correct about capability and silent "
                    "about authorization, which is its documented limitation — it has no guard "
                    "predicate. This is capability, not a demonstrated vulnerability.")
        return ("CONTRADICTED" if cfg.get("n_functions") is not None else "UNRESOLVED",
                "The rule reports an external call reachable from receive()/fallback(), but an "
                "independent CFG re-derivation with a non-matching selector could not reach any "
                "external call on that path. Possible causes: Gigahorse and this analyzer "
                "recover different control flow, the call sits behind a path this traversal did "
                "not explore, or the rule attributed a call from a normal selector to the "
                "fallback. Treated as evidence in tension, not as a refutation.")

    # source_label == unflagged
    if pattern and unauth:
        return ("CONTRADICTED",
                "The source analyzer did not flag this contract, yet an external call is "
                "reachable from the receive()/fallback() path without passing any caller "
                "authorization branch. `unflagged` is a weak signal by construction — the "
                "negatives in this dataset are rule-silent, never benignity-verified — so this "
                "is a plausible source-rule miss rather than a contradiction of a positive "
                "finding.")
    if pattern:
        return ("PARTIALLY_CONFIRMED",
                "Not flagged by the source analyzer. An external call is reachable from the "
                "fallback/receive path but only behind an authorization branch, which is "
                "consistent with the rule staying silent (though the rule would have fired on "
                "reachability alone, so agreement here is coincidental rather than principled).")
    return ("CONFIRMED",
            "Not flagged by the source analyzer, and no external call is reachable from the "
            "receive()/fallback() path in the independent CFG re-derivation. Note this only "
            "means the one pattern the rule tests for is absent; it is not evidence of safety.")


# ----------------------------------------------------------------------------------------
# The decision procedure
# ----------------------------------------------------------------------------------------

def decide(d: dict) -> dict:
    cfg = d["cfg_guard_analysis_opus5"]
    if "error" in cfg:
        return {
            "label": "UNCERTAIN", "reason": "NO_RUNTIME_CODE", "confidence": "HIGH",
            "support": "INCOMPLETE_GUARD_EVIDENCE",
            "rationale": "No runtime bytecode is present at this address (empty code). Nothing "
                         "can be assessed; under EIP-7702 this is either a revoked delegation "
                         "or a bare delegation designator.",
        }

    s = summarize_functions(cfg)
    census = cfg.get("static_opcode_census") or {}
    reaches_sig = any(f.get("reaches_ecrecover") for f in cfg.get("per_function", []))
    # Opcode absence rules out caller/origin checks, but opcode *presence* does not establish
    # reachability. Treat this census as unresolved supporting evidence, never as a shortcut to
    # an exploitable-path label.
    no_caller_opcode = (census.get("CALLER", 0) == 0 and census.get("ORIGIN", 0) == 0)
    has_capability = any(census.get(op, 0) for op in
                         ("CALL", "DELEGATECALL", "CALLCODE", "CREATE", "CREATE2", "SELFDESTRUCT"))
    no_explicit_auth_opcode = no_caller_opcode and has_capability and not reaches_sig
    gap = cfg.get("sensitive_opcodes_never_reached_by_analysis") or {}
    fb = cfg.get("fallback_receive_paths") or {}
    unauth_fb = fb.get("unauthenticated_external_call_from_fallback_or_receive")
    proj = d["identity"].get("documented_project")

    unsafe_paths: List[str] = []
    safe_controls: List[str] = []

    for sel, pc, why in s["unguarded_arbitrary_call"]:
        unsafe_paths.append(
            f"{sel}: CALL at pc={pc} with an attacker-chosen target ({why}) reachable with no "
            f"authorization branch on any path from the dispatcher — an unauthorized caller can "
            f"make the authorizing EOA execute an arbitrary call")
    for sel, pc, tgt in s["unguarded_delegatecall"]:
        unsafe_paths.append(
            f"{sel}: DELEGATECALL at pc={pc} to {tgt} reachable with no authorization branch — "
            f"third-party code would execute against the EOA's own storage")
    for sel, pc in s["unguarded_selfdestruct"]:
        unsafe_paths.append(
            f"{sel}: SELFDESTRUCT at pc={pc} reachable with no authorization branch")
    for sel, pc, tgt, val in s["unguarded_value_drain"]:
        unsafe_paths.append(
            f"{sel}: CALL at pc={pc} to {tgt} with {val}, reachable with no authorization branch "
            f"— moves funds the authorizing account already holds to a destination the account "
            f"owner did not authorize at call time")
    for sel, const, why in s["third_party_guarded_asset"]:
        unsafe_paths.append(f"{sel}: {why}")
    for sel, pc in s["initializer_unrestricted"]:
        unsafe_paths.append(
            f"{sel}: initializer-shaped entry point at pc={pc} performs a storage write with no "
            f"authorization branch on any path from the dispatcher. The delegate's constructor "
            f"never runs in the authorizing EOA's context, so that storage starts empty and "
            f"whichever party calls this first establishes whatever authority it sets")
    for sel, pc, slot in s["unguarded_authority_write"]:
        unsafe_paths.append(
            f"{sel}: SSTORE to slot {slot} at pc={pc} with no authorization branch — in the "
            f"EOA's own (initially empty) storage this lets the first caller install whatever "
            f"authority that slot controls")

    if s["self_call_guarded"]:
        safe_controls.append(
            f"self-call restriction (msg.sender == address(this)) on "
            f"{', '.join(sorted(set(s['self_call_guarded']))[:6])} — the canonical EIP-7702 "
            f"owner check, satisfied only by a transaction the account itself sent")
    if s["signature_guarded"]:
        safe_controls.append(
            f"signature-derived authorization branch (ecrecover) on "
            f"{', '.join(sorted(set(s['signature_guarded']))[:6])}")
    if s["entrypoint_guarded"]:
        safe_controls.append(
            f"caller restricted to a recognized ERC-4337 EntryPoint on "
            f"{', '.join(sorted(set(s['entrypoint_guarded']))[:6])}")
    if s["callback_restricted"]:
        safe_controls.append(
            "callback entry point(s) restricted to a fixed protocol address: "
            + "; ".join(f"{sel} — {why}" for sel, why in s["callback_restricted"][:3]))
    if s["storage_authority_guarded"]:
        safe_controls.append(
            f"msg.sender compared against a stored authority on "
            f"{', '.join(sorted(set(s['storage_authority_guarded']))[:6])}")

    conflicting: List[str] = []
    unresolved: List[str] = []

    if s["unresolved_guard_only"]:
        unresolved.append(
            "the only branch protecting a reachable sensitive operation compares msg.sender or "
            "tx.origin against a value the analyser could not resolve, so whether an attacker "
            "is excluded is undetermined: "
            + "; ".join(f"{sel} ({why})" for sel, why in s["unresolved_guard_only"][:4]))
    if s["origin_equals_caller_only"]:
        conflicting.append(
            f"{', '.join(sorted(set(s['origin_equals_caller_only']))[:4])} branch on "
            f"tx.origin == msg.sender, which the CFG counts as a guard but which provides no "
            f"protection against a direct attacker call")
    if gap:
        unresolved.append(
            f"sensitive opcodes present in the bytecode that no traversal reached "
            f"({ {k: v[:4] for k, v in gap.items()} }) — capability here is a lower bound")
    if s["incomplete_functions"]:
        unresolved.append(
            f"analysis incomplete (unresolved dynamic jumps / exploration cap / stack "
            f"underflow) for: {', '.join(sorted(set(s['incomplete_functions']))[:8])}")
    if s["unguarded_create"]:
        unresolved.append(
            f"unrestricted CREATE/CREATE2 at {s['unguarded_create'][:3]} — a capability whose "
            f"concrete risk depends on what the created contract is given authority over, which "
            f"bytecode alone does not establish")
    if s["unguarded_capability_call"]:
        unresolved.append(
            "unauthenticated call(s) to a fixed or stored destination whose payload is assembled "
            "in memory: " + "; ".join(f"{a} pc={b} -> {c} ({d_}, {e})" for a, b, c, d_, e in
                                      s["unguarded_capability_call"][:4])
            + ". This analyser does not track provenance through memory, so whether a caller can "
              "choose that payload — and therefore whether this is exploitable — is not "
              "established. Capability, not a demonstrated vulnerability.")
    if s["unguarded_passthrough_call"]:
        unresolved.append(
            f"unauthenticated call(s) forwarding only msg.value to a fixed destination "
            f"({s['unguarded_passthrough_call'][:3]}) — a caller can only donate their own ETH, "
            f"so this is not by itself a path to the account's assets")

    if no_explicit_auth_opcode:
        unresolved.append(
            "the runtime contains capability opcodes but no CALLER/ORIGIN opcode and no analyzed "
            "path reaches ecrecover. This rules out those explicit authorization mechanisms, "
            "but opcode presence alone does not prove that a capability is reachable; a concrete "
            "control-flow path is still required for an UNSAFE label")

    # ---- decision cascade -------------------------------------------------------------
    strong_unsafe = bool(s["unguarded_arbitrary_call"] or s["unguarded_delegatecall"]
                         or s["unguarded_selfdestruct"] or s["unguarded_value_drain"])
    moderate_unsafe = bool(s["unguarded_authority_write"] or s["initializer_unrestricted"]
                           or s["third_party_guarded_asset"])

    if strong_unsafe:
        if s["initializer_unrestricted"]:
            # Precedence: when the unauthenticated path runs through an initializer that writes
            # the account's own (empty) storage, the takeover is the finding; the delegatecall
            # or call it performs is the mechanism.
            reason = "UNSAFE_INITIALIZATION"
        elif s["unguarded_selfdestruct"]:
            reason = "MALICIOUS_OR_DRAINER"
        elif s["unguarded_delegatecall"]:
            reason = "DANGEROUS_DELEGATECALL_OR_UPGRADE"
        elif s["unguarded_arbitrary_call"]:
            reason = "ARBITRARY_EXTERNAL_CALL"
        else:
            reason = "UNAUTHORIZED_ASSET_MOVEMENT"
        label, support = "UNSAFE", "CONCRETE_EXPLOITABLE_PATH"
        conf = "LOW" if (gap or s["incomplete_functions"]) else "HIGH"
        conf = "MEDIUM" if conf == "LOW" and not gap else conf
    elif moderate_unsafe:
        if s["third_party_guarded_asset"]:
            # The capability is gated, but only for an address fixed at deployment time. Under
            # EIP-7702 that address is by construction not the authorizing EOA.
            reason = ("TX_ORIGIN_AUTHORIZATION_RISK"
                      if any("tx.origin" in w for _, _, w in s["third_party_guarded_asset"])
                      else "UNAUTHORIZED_ASSET_MOVEMENT")
            support = "CONCRETE_UNAUTHORIZED_CAPABILITY"
        elif s["initializer_unrestricted"]:
            reason, support = "UNSAFE_INITIALIZATION", "CONCRETE_UNAUTHORIZED_CAPABILITY"
        elif s["unguarded_authority_write"]:
            reason, support = "OWNER_OR_PRIVILEGE_TAKEOVER", "CONCRETE_UNAUTHORIZED_CAPABILITY"
        else:
            reason, support = "UNAUTHORIZED_ASSET_MOVEMENT", "CONCRETE_UNAUTHORIZED_CAPABILITY"
        label = "UNSAFE"
        conf = "MEDIUM" if not gap else "LOW"
    elif s["unresolved_guard_only"] and not unsafe_paths:
        label, reason = "UNCERTAIN", "INSUFFICIENT_EVIDENCE"
        support, conf = "INCOMPLETE_GUARD_EVIDENCE", "MEDIUM"
    elif safe_controls and not unsafe_paths:
        label = "SAFE"
        if s["self_call_guarded"]:
            reason = "OWNER_OR_SELF_CALL_RESTRICTED"
        elif s["signature_guarded"]:
            reason = "SIGNATURE_AUTHORIZATION_CONFIRMED"
        elif s["entrypoint_guarded"]:
            reason = "ACCESS_CONTROL_APPEARS_APPROPRIATE"
        else:
            reason = "ACCESS_CONTROL_APPEARS_APPROPRIATE"
        support = "STRONG_STATIC_AND_DYNAMIC_EVIDENCE"
        conf = "MEDIUM" if (gap or s["incomplete_functions"]) else "HIGH"
        if gap:
            # We cannot claim "no dangerous path" while sensitive opcodes went unreached.
            label, reason, support = "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "INCOMPLETE_GUARD_EVIDENCE"
            conf = "MEDIUM"
    elif not unsafe_paths and s["n_functions"] and not gap and not s["incomplete_functions"]:
        # Every dispatched function analysed to completion; nothing sensitive is reachable
        # unauthenticated and nothing dangerous was found.
        label, reason = "SAFE", "NO_CONCRETE_DANGEROUS_PATH_FOUND"
        support, conf = "STRONG_STATIC_AND_DYNAMIC_EVIDENCE", "MEDIUM"
    else:
        label, reason = "UNCERTAIN", "INSUFFICIENT_EVIDENCE"
        support, conf = "INCOMPLETE_GUARD_EVIDENCE", "MEDIUM"
        if gap:
            reason = "DECOMPILATION_AMBIGUITY"
        elif s["n_functions"] == 0:
            reason = "DECOMPILATION_AMBIGUITY"

    # A documented, source-verified legitimate project raises confidence but never decides.
    if proj and proj.get("provenance_confidence") == "VERIFIED_LEGITIMATE_CONTROL":
        safe_controls.append(
            f"documented project {proj.get('project')} with live-verified source and a matching "
            f"runtime hash (documentation: {proj.get('official_documentation')})")

    return {
        "label": label, "reason": reason, "confidence": conf, "support": support,
        "unsafe_paths": unsafe_paths, "safe_controls": safe_controls,
        "conflicting": conflicting, "unresolved": unresolved, "summary": s,
    }
