#!/usr/bin/env python3
"""Small deterministic checks for the conservative bytecode canonicalizer."""
from canonicalizer import analyze_bytecode


def test_unreachable_suffix_removed():
    r = analyze_bytecode("005b00")
    assert r["analysis"]["cfg_reachable_after_first_stop"] is False
    assert r["analysis"]["removed_executable_bytes"] == 2
    assert r["reachable_compact_hex"] == "00"


def test_static_jump_after_stop_retained():
    # PUSH1 0x04; JUMP; STOP; JUMPDEST; STOP
    r = analyze_bytecode("600456005b00")
    assert r["analysis"]["cfg_reachable_after_first_stop"] is True
    assert r["analysis"]["removed_executable_bytes"] == 1
    assert r["reachable_masked_hex"] == "600456005b00"


def test_dynamic_jump_retains_jumpdest_regions():
    # CALLDATALOAD; JUMP; STOP; JUMPDEST; STOP
    r = analyze_bytecode("3556005b00")
    assert r["analysis"]["unresolved_reachable_jump_count"] == 1
    assert r["analysis"]["cfg_reachable_after_first_stop"] is True


def test_code_introspection_disables_executable_pruning():
    r = analyze_bytecode("38005b00")
    assert r["analysis"]["code_introspection_reachable"] is True
    assert r["analysis"]["removed_executable_bytes"] == 0


def test_narrow_metadata_rule():
    # executable STOP + a2 01 02, declared CBOR length 3
    r = analyze_bytecode("00a201020003")
    assert r["analysis"]["metadata_recognized"] is True
    assert r["analysis"]["executable_bytes"] == 1
    assert r["metadata_stripped_hex"] == "00"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"[ok] {test.__name__}")
