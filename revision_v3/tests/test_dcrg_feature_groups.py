from analysis.delegation_context import DCRG_FEATURE_ORDER
from analysis.dcrg_feature_groups import FEATURE_GROUPS, PROTOCOL_ACTOR_FEATURES


def test_dcrg_ablation_groups_are_nested_and_protocol_actor_ablation_is_exact():
    full = set(DCRG_FEATURE_ORDER)
    assert set(FEATURE_GROUPS["cfg_capability_only"]) < set(
        FEATURE_GROUPS["dcrg_untyped_guards"]
    ) < full
    assert set(FEATURE_GROUPS["dcrg_without_protocol_actors"]) == (
        full - PROTOCOL_ACTOR_FEATURES
    )
    assert set(FEATURE_GROUPS["dcrg_full"]) == full
