"""Phase 3A label taxonomy -- shared by the Excel workbook builder, the reviewer-copy script,
the master-adjudication importer, and the summary script. Single source of truth so every
tool validates against the exact same allowed values.
"""

PRIMARY_LABELS = ["SAFE", "UNSAFE", "UNCERTAIN"]

LABEL_DEFINITIONS = {
    "SAFE": "The available evidence supports that the delegate is appropriate to authorize "
            "under EIP-7702. No concrete authorization-related security risk was identified.",
    "UNSAFE": "The available evidence shows a concrete security risk that could make "
              "authorization dangerous.",
    "UNCERTAIN": "The available evidence is insufficient to make a reliable SAFE or UNSAFE "
                 "decision. Includes cases that cannot be assessed from the currently "
                 "available runtime bytecode.",
}

UNSAFE_REASONS = [
    "MALICIOUS_OR_DRAINER",
    "UNAUTHORIZED_ASSET_MOVEMENT",
    "DANGEROUS_APPROVAL_OR_TRANSFER",
    "ARBITRARY_EXTERNAL_CALL",
    "UNSAFE_INITIALIZATION",
    "OWNER_OR_PRIVILEGE_TAKEOVER",
    "DANGEROUS_DELEGATECALL_OR_UPGRADE",
    "AUTHORIZATION_SPECIFIC_MISUSE",
    "OTHER_UNSAFE",
]

UNCERTAIN_REASONS = [
    "UNRESOLVED_PROXY",
    "EXTERNAL_OR_DYNAMIC_DEPENDENCY",
    "STATE_DEPENDENT_BEHAVIOR",
    "NO_RUNTIME_CODE",
    "FUTURE_OR_COUNTERFACTUAL_CODE",
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "OTHER_UNCERTAIN",
]

SAFE_REASONS = [
    "DOCUMENTED_LEGITIMATE_IMPLEMENTATION",
    "ACCESS_CONTROL_APPEARS_APPROPRIATE",
    "INITIALIZATION_APPEARS_SAFE",
    "NO_CONCRETE_DANGEROUS_PATH_FOUND",
    "OTHER_SAFE",
]

ALL_REASON_CATEGORIES = SAFE_REASONS + UNSAFE_REASONS + UNCERTAIN_REASONS

REASONS_BY_LABEL = {
    "SAFE": SAFE_REASONS,
    "UNSAFE": UNSAFE_REASONS,
    "UNCERTAIN": UNCERTAIN_REASONS,
}

CONFIDENCE_LEVELS = ["high", "medium", "low"]

AGREEMENT_VALUES = ["YES", "PARTLY", "NO"]

INCLUDED_IN_BINARY_EVALUATION_VALUES = ["YES", "NO"]

# Fields that must NEVER appear in any reviewer-facing sheet or LLM review input (Phase 3A
# reuses Phase 2's blinding contract -- see revision_v3/src/evidence/packet_builder.py).
FORBIDDEN_FIELDS = {
    "label", "label_semantics", "label_source", "label_evidence_type", "label_strength",
    "authguard_score", "authguard_prediction", "raw_score", "calibrated_score",
    "model_score", "source_label", "source_positive", "source_unflagged",
    "is_false_positive", "is_false_negative", "gold_test_sampling_metadata",
    "ref_model_mean_score", "ref_model_mean_prediction", "disagrees_with_source_label",
    "gold_dev_stratum", "pilot_reason",
}
