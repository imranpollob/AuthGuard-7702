from analysis.delegation_context import DCRG_FEATURE_ORDER

from revision_v3.experiments.delegation_context.run_dcrg_ablation import FEATURE_GROUPS


def test_ablation_feature_groups_are_nested_and_full_is_canonical():
    cfg = set(FEATURE_GROUPS["cfg_capability_only"])
    untyped = set(FEATURE_GROUPS["dcrg_untyped_guards"])
    no_actors = set(FEATURE_GROUPS["dcrg_without_protocol_actors"])
    full = set(FEATURE_GROUPS["dcrg_full"])
    assert cfg < untyped < full
    assert no_actors < full
    assert FEATURE_GROUPS["dcrg_full"] == DCRG_FEATURE_ORDER


def test_protocol_actor_ablation_removes_only_actor_context():
    full = set(FEATURE_GROUPS["dcrg_full"])
    no_actors = set(FEATURE_GROUPS["dcrg_without_protocol_actors"])
    assert full - no_actors == {
        "n_erc4337_entrypoint_guards",
        "n_hardcoded_authority_matches",
        "n_hardcoded_authority_mismatches",
    }
