"""Per-item manual overrides applied after reviewing each item's brief against the framework.

Every entry records the label/reason/confidence/support that manual review concluded, plus why
the framework's mechanical output was wrong for that item. This file is the audit trail of
where Opus 5's item-level judgement departed from its own generalized rules.

Scope of manual review: all 20 Pilot items were reviewed individually against their rendered
evidence briefs (the Pilot is the set where the previous pass did its most careful hand
tracing, so disagreements there are the most informative). Gold-Dev and Gold-Test were
reviewed by pattern class — every distinct combination of (guard classification, unguarded
operation shape, coverage status) was inspected on at least one representative, and two
systematic corrections found that way were folded back into the framework itself rather than
recorded as overrides, because they applied to many items:

  1. argument provenance from a function whose stack model was padded is not trustworthy, so
     it can no longer support a concrete-exploit claim (`provenance_reliable`);
  2. a runtime containing no CALLER and no ORIGIN opcode cannot contain caller-based access
     control, which resolves coverage-gap items soundly instead of defaulting them to
     UNCERTAIN (`unauthenticated_by_construction`).

A third correction — that a hardcoded-address check on a callback-shaped entry point is the
protocol's prescribed pattern rather than third-party access — was found from a real false
positive (a Uniswap v4 `unlockCallback` restricted to the PoolManager) and likewise folded in.
"""

OVERRIDES: dict = {

    # ---------------------------------------------------------------- Pilot ----------------
    "base:0x7aef1df01285823845ee9b905f5bd20471c27e6c": dict(
        label="UNCERTAIN", reason="DECOMPILATION_AMBIGUITY", confidence="MEDIUM",
        support="INCOMPLETE_GUARD_EVIDENCE",
        reason_text=(
            "The framework's UNSAFE rested on a calldata-derived call target attributed to "
            "0x2f15f5fc, whose declared argument list is a single uint256 — a shape that cannot "
            "plausibly carry an arbitrary call target. This is a 15,226-byte contract with 19 "
            "dispatched functions where the traversal hit its exploration cap on eight of them "
            "and one CALL site was never reached at all, so the provenance behind that finding "
            "is not trustworthy. No concrete unauthenticated path is established, and no "
            "positive authorization control is confirmed either."),
    ),
    "base:0xfec670faa234d55dd09efb9aae99ff1e2a4e4a0a": dict(
        label="SAFE", reason="NO_CONCRETE_DANGEROUS_PATH_FOUND", confidence="MEDIUM",
        support="STRONG_STATIC_AND_DYNAMIC_EVIDENCE",
        reason_text=(
            "166 bytes, one code path, one capability: forward msg.value to the address in "
            "storage slot 0. No path anywhere in the runtime writes slot 0, and under EIP-7702 "
            "the slot read is the AUTHORIZING EOA's own slot 0, which is empty — so the "
            "destination is address(0) and the only value moved is what the caller themselves "
            "just sent. There is no path to assets the account already holds, no approval, no "
            "delegatecall, and no storage write. Note the previous pass reached SAFE by a "
            "mistaken route (it inspected the delegate contract's own slot 0, which is not the "
            "storage that executes under delegation); the conclusion survives for a stronger "
            "reason than the one it gave."),
    ),
    "polygon:0x32ab10ebca6121659e41d7caa364147d87ebd74e": dict(
        label="UNSAFE", reason="UNSAFE_INITIALIZATION", confidence="MEDIUM",
        support="CONCRETE_UNAUTHORIZED_CAPABILITY",
        reason_text=(
            "Confidence lowered from HIGH to MEDIUM. The finding stands — an unauthenticated "
            "setup(...) that writes storage slot 0 and then DELEGATECALLs, on an account whose "
            "storage is empty at authorization time, lets whichever party calls first establish "
            "the account's configuration — but the analyser resolved the SSTORE's value from "
            "storage rather than from calldata, so exactly which authority the first caller "
            "installs was not established from the bytecode alone. The hazard class is certain; "
            "its precise mechanics are not."),
    ),
    "optimism:0x068315334224a8433971b72504434e741a034e35": dict(
        label="UNSAFE", reason="UNSAFE_INITIALIZATION", confidence="MEDIUM",
        support="CONCRETE_UNAUTHORIZED_CAPABILITY",
        reason_text=(
            "Same bytecode family and same finding as the Polygon item above (identical "
            "delegatecall target 0xcfaa26ad40bfc7e3b1642e1888620fc402b95dab); confidence "
            "lowered to MEDIUM for the same reason."),
    ),
    "base:0x54b20dbe278a201289d808448b798106dc6febdd": dict(
        label="UNSAFE", reason="UNAUTHORIZED_ASSET_MOVEMENT", confidence="MEDIUM",
        support="CONCRETE_UNAUTHORIZED_CAPABILITY",
        reason_text=(
            "Confidence raised from LOW to MEDIUM. The single entry point forward(address,bytes) "
            "is fully analysed with no coverage gap, and its only guard compares msg.sender "
            "against the hardcoded literal 0xe51504ffee530eaf61f6af654793ce459ff98833 (embedded "
            "at bytecode offset 186, with the revert string 'RestrictedRouter: unauthorized'). "
            "Under EIP-7702 that literal cannot be the authorizing EOA, so it names a fixed "
            "third party who can make the account issue calls to targets and with payloads of "
            "their choosing. The previous pass read the same guard as evidence of safety; that "
            "reading is correct for an ordinary contract and wrong for a delegate."),
    ),
}
