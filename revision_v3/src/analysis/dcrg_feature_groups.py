"""Predeclared DCRG representation groups shared by all evaluation populations."""
from __future__ import annotations

from analysis.delegation_context import DCRG_FEATURE_ORDER

CFG_CAPABILITY_FEATURES = (
    "n_functions",
    "n_complete_functions",
    "n_incomplete_functions",
    "n_unguarded_call",
    "n_unguarded_delegatecall",
    "n_unguarded_create",
    "n_unguarded_selfdestruct",
    "n_unguarded_sstore",
    "fallback_external_call_reachable",
    "n_unreached_sensitive_sites",
    "coverage_complete",
    "coverage_partial",
    "coverage_unknown",
)

UNTYPED_GUARD_FEATURES = CFG_CAPABILITY_FEATURES + (
    "n_unguarded_sensitive",
    "n_sensitive_without_any_recognized_guard",
    "n_storage_condition_guarded_sensitive",
    "n_guards",
    "fallback_open_external_call",
)

PROTOCOL_ACTOR_FEATURES = {
    "n_erc4337_entrypoint_guards",
    "n_hardcoded_authority_matches",
    "n_hardcoded_authority_mismatches",
}

FEATURE_GROUPS = {
    "cfg_capability_only": CFG_CAPABILITY_FEATURES,
    "dcrg_untyped_guards": UNTYPED_GUARD_FEATURES,
    "dcrg_without_protocol_actors": tuple(
        name for name in DCRG_FEATURE_ORDER if name not in PROTOCOL_ACTOR_FEATURES
    ),
    "dcrg_full": tuple(DCRG_FEATURE_ORDER),
}


def validate_feature_groups() -> None:
    full = set(DCRG_FEATURE_ORDER)
    if set(FEATURE_GROUPS["dcrg_full"]) != full:
        raise ValueError("full DCRG feature group drifted from the schema")
    for name, features in FEATURE_GROUPS.items():
        if not features or len(features) != len(set(features)):
            raise ValueError(f"invalid or duplicate features in {name}")
        unknown = set(features) - full
        if unknown:
            raise ValueError(f"{name} contains unknown DCRG features: {sorted(unknown)}")


validate_feature_groups()
