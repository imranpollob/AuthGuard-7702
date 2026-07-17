#!/usr/bin/env python3
"""Conservative EVM runtime-bytecode reachability analysis for Revision v2.

This module deliberately under-prunes. It decodes instruction boundaries, constructs basic
blocks, follows fall-through and directly-resolvable PUSHn -> JUMP/JUMPI edges, and treats a
reachable unresolved jump as capable of targeting every JUMPDEST. If reachable code uses
CODESIZE or CODECOPY, executable bytes are retained because apparently unreachable bytes can
still be observed as code data. Only a narrowly recognized Solidity-style CBOR trailer is
classified as metadata.

The compact output is a *feature representation*, not deployable replacement bytecode: removing
bytes changes program counters. ``masked_hex`` preserves byte offsets for bounded dynamic tests.
Both forms are emitted so the distinction cannot be hidden by downstream experiments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Iterable


TERMINATORS = {0x00, 0xF3, 0xFD, 0xFE, 0xFF}
JUMP = 0x56
JUMPI = 0x57
JUMPDEST = 0x5B
PUSH0 = 0x5F
PUSH1 = 0x60
PUSH32 = 0x7F
CODESIZE = 0x38
CODECOPY = 0x39


@dataclass(frozen=True)
class Instruction:
    pc: int
    opcode: int
    size: int
    immediate: bytes

    @property
    def end(self) -> int:
        return self.pc + self.size


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    instruction_pcs: tuple[int, ...]


def normalize_hex(raw: str) -> str:
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    h = "".join(c for c in h if c in "0123456789abcdef")
    return h[:-1] if len(h) % 2 else h


def conservative_metadata_start(code: bytes) -> int:
    """Recognize only the repository's established Solidity CBOR trailer form.

    The last two bytes encode the trailer length and the trailer begins with 0xa2. Anything
    else is retained because treating arbitrary suffix data as metadata would be unsafe.
    """
    if len(code) < 4:
        return len(code)
    length = int.from_bytes(code[-2:], "big")
    start = len(code) - 2 - length
    if 0 <= start < len(code) - 2 and code[start] == 0xA2:
        return start
    return len(code)


def decode(code: bytes, end: int | None = None) -> list[Instruction]:
    limit = len(code) if end is None else min(end, len(code))
    out: list[Instruction] = []
    pc = 0
    while pc < limit:
        opcode = code[pc]
        width = opcode - PUSH1 + 1 if PUSH1 <= opcode <= PUSH32 else 0
        size = min(1 + width, limit - pc)
        immediate = code[pc + 1:pc + size] if width else b""
        out.append(Instruction(pc=pc, opcode=opcode, size=size, immediate=immediate))
        pc += size
    return out


def build_blocks(instructions: list[Instruction], code_end: int) -> list[Block]:
    if not instructions:
        return []
    boundaries = {0, code_end}
    for inst in instructions:
        if inst.opcode == JUMPDEST:
            boundaries.add(inst.pc)
        if inst.opcode in TERMINATORS | {JUMP, JUMPI} and inst.end < code_end:
            boundaries.add(inst.end)
    ordered = sorted(boundaries)
    blocks: list[Block] = []
    for start, end in zip(ordered, ordered[1:]):
        pcs = tuple(inst.pc for inst in instructions if start <= inst.pc < end)
        if pcs:
            blocks.append(Block(start=start, end=end, instruction_pcs=pcs))
    return blocks


def _direct_jump_target(block: Block, by_pc: dict[int, Instruction], jumpdests: set[int]) -> int | None:
    """Resolve only the unambiguous adjacent PUSHn destination pattern.

    Under-resolving is intentional: an unresolved reachable jump activates the conservative
    all-JUMPDEST rule instead of risking removal of a legal target.
    """
    if len(block.instruction_pcs) < 2:
        return None
    prev = by_pc[block.instruction_pcs[-2]]
    if not (PUSH1 <= prev.opcode <= PUSH32) or not prev.immediate:
        return None
    target = int.from_bytes(prev.immediate, "big")
    return target if target in jumpdests else None


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def analyze_bytecode(raw: str) -> dict:
    normalized = normalize_hex(raw)
    code = bytes.fromhex(normalized) if normalized else b""
    metadata_start = conservative_metadata_start(code)
    instructions = decode(code, metadata_start)
    by_pc = {inst.pc: inst for inst in instructions}
    blocks = build_blocks(instructions, metadata_start)
    block_by_start = {b.start: b for b in blocks}
    pc_to_block = {pc: b.start for b in blocks for pc in b.instruction_pcs}
    jumpdests = {inst.pc for inst in instructions if inst.opcode == JUMPDEST}

    edges: dict[int, set[int]] = {b.start: set() for b in blocks}
    dynamic_blocks: set[int] = set()
    for i, block in enumerate(blocks):
        last = by_pc[block.instruction_pcs[-1]]
        fallthrough = blocks[i + 1].start if i + 1 < len(blocks) else None
        if last.opcode in (JUMP, JUMPI):
            target = _direct_jump_target(block, by_pc, jumpdests)
            if target is None:
                dynamic_blocks.add(block.start)
            else:
                edges[block.start].add(target)
            if last.opcode == JUMPI and fallthrough is not None:
                edges[block.start].add(fallthrough)
        elif last.opcode not in TERMINATORS and fallthrough is not None:
            edges[block.start].add(fallthrough)

    reachable: set[int] = set()
    reachable_dynamic: set[int] = set()
    pending = [blocks[0].start] if blocks else []
    while pending:
        start = pending.pop()
        if start in reachable or start not in block_by_start:
            continue
        reachable.add(start)
        next_blocks = set(edges[start])
        if start in dynamic_blocks:
            reachable_dynamic.add(start)
            # Every valid dynamic target must be a JUMPDEST instruction.
            next_blocks.update(jumpdests)
        pending.extend(sorted(next_blocks - reachable, reverse=True))

    reachable_instructions = [by_pc[pc] for start in reachable
                              for pc in block_by_start[start].instruction_pcs]
    code_introspection = any(inst.opcode in {CODESIZE, CODECOPY}
                             for inst in reachable_instructions)
    retained_blocks = set(block_by_start) if code_introspection else reachable
    unreachable_ranges = _merge_ranges(
        (b.start, b.end) for b in blocks if b.start not in retained_blocks
    )
    kept_ranges = _merge_ranges(
        (b.start, b.end) for b in blocks if b.start in retained_blocks
    )

    compact = b"".join(code[start:end] for start, end in kept_ranges)
    masked = bytearray(code[:metadata_start])
    for start, end in unreachable_ranges:
        masked[start:end] = b"\x00" * (end - start)

    first_stop_pc = next((inst.pc for inst in instructions if inst.opcode == 0x00), None)
    if first_stop_pc is None:
        first_stop_prefix = code[:metadata_start]
        suffix = b""
    else:
        first_stop_prefix = code[:first_stop_pc + 1]
        suffix = code[first_stop_pc + 1:metadata_start]
    reachable_after_first_stop = bool(
        first_stop_pc is not None and any(
            inst.pc > first_stop_pc and pc_to_block.get(inst.pc) in reachable
            for inst in instructions
        )
    )

    removed = [dict(start=a, end=b, length=b - a, reason="cfg_unreachable")
               for a, b in unreachable_ranges]
    if metadata_start < len(code):
        removed.append(dict(start=metadata_start, end=len(code),
                            length=len(code) - metadata_start,
                            reason="recognized_solidity_cbor_metadata"))

    return dict(
        normalized_hex=normalized,
        metadata_stripped_hex=code[:metadata_start].hex(),
        first_stop_hex=first_stop_prefix.hex(),
        suffix_hex=suffix.hex(),
        reachable_compact_hex=compact.hex(),
        reachable_masked_hex=bytes(masked).hex(),
        analysis=dict(
            total_bytes=len(code),
            executable_bytes=metadata_start,
            metadata_bytes=len(code) - metadata_start,
            metadata_recognized=metadata_start < len(code),
            instruction_count=len(instructions),
            basic_block_count=len(blocks),
            cfg_reachable_block_count=len(reachable),
            retained_block_count=len(retained_blocks),
            jumpdest_count=len(jumpdests),
            unresolved_reachable_jump_count=len(reachable_dynamic),
            code_introspection_reachable=code_introspection,
            first_stop_pc=first_stop_pc,
            first_stop_prefix_bytes=len(first_stop_prefix),
            suffix_bytes=len(suffix),
            cfg_reachable_after_first_stop=reachable_after_first_stop,
            removed_executable_bytes=sum(b - a for a, b in unreachable_ranges),
            retained_executable_bytes=len(compact),
            retained_fraction=(len(compact) / metadata_start if metadata_start else 1.0),
            uncertainty=("reachable_code_introspection_retains_all_executable_bytes"
                         if code_introspection else
                         "reachable_dynamic_jump_retains_all_jumpdest_regions"
                         if reachable_dynamic else "static_edges_only"),
            removed_ranges=removed,
            input_sha256=hashlib.sha256(normalized.encode()).hexdigest(),
            compact_sha256=hashlib.sha256(compact).hexdigest(),
        ),
    )


def public_analysis(result: dict) -> dict:
    """Return the auditable metadata without embedding large bytecode strings."""
    return dict(result["analysis"])

