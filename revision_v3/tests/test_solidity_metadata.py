"""Safety-boundary tests for conservative Solidity metadata recognition."""
from __future__ import annotations

import os
import sys

import cbor2


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V3 = os.path.join(ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))
sys.path.insert(0, os.path.join(V3, "experiments", "opus5_labeling"))

from analysis.solidity_metadata import validated_solidity_metadata_start  # noqa: E402
from evm_cfg import Analyzer, Val, static_opcode_census  # noqa: E402


def _runtime_with_metadata(executable: bytes, metadata: dict) -> bytes:
    encoded = cbor2.dumps(metadata, canonical=True)
    return executable + encoded + len(encoded).to_bytes(2, "big")


def test_valid_ipfs_solc_metadata_is_excluded_from_opcode_census():
    # The metadata digest deliberately contains CALL and DELEGATECALL bytes.  Neither is code.
    digest = bytes([0xF1, 0xF4]) + bytes(30)
    code = _runtime_with_metadata(
        bytes([0x00]), {"ipfs": b"\x12\x20" + digest, "solc": b"\x00\x08\x1c"}
    )
    assert validated_solidity_metadata_start(code) == 1
    census = static_opcode_census(code)
    assert census["metadata_recognized"] is True
    assert "CALL" not in census["counts"]
    assert "DELEGATECALL" not in census["counts"]


def test_arbitrary_a2_suffix_is_not_treated_as_metadata():
    # Old heuristic accepted any length-delimited suffix beginning with 0xa2.
    code = bytes.fromhex("00a201020003")
    assert validated_solidity_metadata_start(code) == len(code)


def test_unknown_key_or_wrong_value_shape_is_retained():
    unknown = _runtime_with_metadata(b"\x00", {"future": b"x"})
    malformed_ipfs = _runtime_with_metadata(b"\x00", {"ipfs": bytes(34)})
    assert validated_solidity_metadata_start(unknown) == len(unknown)
    assert validated_solidity_metadata_start(malformed_ipfs) == len(malformed_ipfs)


def test_trailing_cbor_object_is_rejected():
    first = cbor2.dumps({"bzzr1": bytes(32)}, canonical=True)
    encoded = first + cbor2.dumps(True)
    code = b"\x00" + encoded + len(encoded).to_bytes(2, "big")
    assert validated_solidity_metadata_start(code) == len(code)


def test_real_sensitive_opcode_before_metadata_remains_counted():
    code = _runtime_with_metadata(b"\xf4\x00", {"bzzr1": bytes(32), "solc": b"\x00\x08\x1c"})
    census = static_opcode_census(code)
    assert census["sites"]["DELEGATECALL"] == [0]


def test_valid_metadata_with_an_instruction_aligned_jumpdest_is_retained():
    # Search the digest positions because preceding CBOR bytes can decode as PUSH immediates.
    for position in range(32):
        digest = bytearray(32)
        digest[position] = 0x5B
        code = _runtime_with_metadata(b"\x00", {"bzzr1": bytes(digest)})
        start = validated_solidity_metadata_start(code)
        suffix_instructions = [
            (pc, name) for pc, name, _ in __import__("evm_cfg").disassemble(code)
            if pc >= start
        ]
        if any(name == "JUMPDEST" for _, name in suffix_instructions):
            census = static_opcode_census(code)
            assert census["metadata_recognized"] is False
            assert census["metadata_rejection_reason"] == "metadata_contains_executable_jumpdest"
            break
    else:
        raise AssertionError("test fixture could not place an instruction-aligned JUMPDEST")


def test_valid_cbor_inside_push_immediate_is_not_excluded():
    metadata = cbor2.dumps({"bzzr1": bytes(32)}, canonical=True)
    # PUSH32 consumes the nominal metadata start and therefore makes it non-instruction-aligned.
    code = b"\x7f" + metadata + len(metadata).to_bytes(2, "big")
    census = static_opcode_census(code)
    assert census["metadata_recognized"] is False
    assert census["metadata_rejection_reason"] == "metadata_start_not_instruction_boundary"


def test_valid_metadata_after_nonterminal_instruction_is_retained():
    code = _runtime_with_metadata(b"\x01", {"bzzr1": bytes(32)})  # ADD can fall through.
    census = static_opcode_census(code)
    assert census["metadata_recognized"] is False
    assert census["metadata_rejection_reason"] == "executable_fallthrough_into_metadata_possible"


def test_state_widening_explores_loop_exit_without_hiding_a_cap(monkeypatch):
    # counter=0; while counter<3: counter += 1; then execute CALL.  With only two exact
    # visits the exit is not reached; widening the counter makes LT unknown and explores both
    # the loop body and exit, preserving conservative capability reachability.
    code = bytes.fromhex("5f5b60038110601357505f5f5f5f5f5f5ff1005b600101600156")
    monkeypatch.setattr(Analyzer, "WIDEN_AFTER", 1)
    monkeypatch.setattr(Analyzer, "MAX_PER_PC", 3)
    result = Analyzer(code).traverse(0, stop_at_guard_kinds=set())
    assert result.used_state_widening is True
    assert result.hit_per_pc_cap is False
    assert any(hit.op == "CALL" for hit in result.sensitive.values())


def test_state_key_distinguishes_guard_comparison_provenance():
    caller_vs_self = Val(src=frozenset({"caller"}), cmp_src=frozenset({"address"}))
    caller_vs_storage = Val(src=frozenset({"caller"}), cmp_src=frozenset({"sload"}))
    assert caller_vs_self.key() != caller_vs_storage.key()
