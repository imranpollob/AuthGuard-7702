from __future__ import annotations

import pytest

from revision_v3.experiments.external_controls.evaluate_frozen_legitimate_controls import (
    consensus_decision,
)


def test_consensus_warn_requires_two_of_three_seed_warnings():
    assert consensus_decision(2, 3, "COMPLETE", True) == "WARN"
    assert consensus_decision(3, 3, "PARTIAL", False) == "WARN"


def test_seed_disagreement_defers_instead_of_hiding_instability():
    assert consensus_decision(1, 3, "COMPLETE", True) == "DEFER"


def test_no_warning_requires_complete_coverage_and_authority_context():
    assert consensus_decision(0, 3, "COMPLETE", True) == "NO_MODEL_WARNING"
    assert consensus_decision(0, 3, "PARTIAL", True) == "DEFER"
    assert consensus_decision(0, 3, "COMPLETE", False) == "DEFER"


def test_consensus_rejects_nonfrozen_seed_count():
    with pytest.raises(ValueError, match="exactly three"):
        consensus_decision(0, 5, "COMPLETE", True)
