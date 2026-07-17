#!/usr/bin/env python3
"""Deterministic smoke tests for the adaptive search algorithms."""
import numpy as np

from search import ACTIONS, beam_search, random_search
from run_adaptive_attacks import safe_addr_immediate_rewrite, safe_selector_immediate_rewrite


def fake_apply(sequence):
    return "00" + "".join(f"{ACTIONS.index(action):02x}" for action in sequence)


def fake_score(batch):
    return np.asarray([1.0 / max(len(value), 1) for value in batch])


def test_random_budget_and_determinism():
    one = random_search("00", 1.0, 0.5, "row", fake_apply, fake_score, budget=16)
    two = random_search("00", 1.0, 0.5, "row", fake_apply, fake_score, budget=16)
    assert len(one[1]) <= 16
    assert one[0].sequence == two[0].sequence
    assert one[0].score <= 1.0


def test_beam_budget_and_improvement():
    def apply_state(prefix, bytecode, action):
        return fake_apply(prefix + (action,))
    best, queried, _ = beam_search("00", 1.0, 0.5, apply_state, fake_score,
                                   budget=20, width=4, max_depth=4)
    assert len(queried) <= 20
    assert best.score < 1.0


def test_truncated_push_immediates_are_skipped():
    # PUSH20 and PUSH4 with too few trailing bytes must remain valid best-effort bytecode and
    # must not trigger the frozen helper's out-of-range write.
    assert safe_addr_immediate_rewrite(bytearray.fromhex("73aabb"), "test").hex() == "73aabb"
    assert safe_selector_immediate_rewrite(bytearray.fromhex("63aabb"), "test").hex() == "63aabb"


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(); print(f"[ok] {name}")
