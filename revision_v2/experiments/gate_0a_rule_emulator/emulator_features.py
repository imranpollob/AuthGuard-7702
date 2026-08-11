#!/usr/bin/env python3
"""Gate 0A — hand-coded emulator of the USENIX source-label rule.

The label being emulated is documented in
`USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl`, relation
`AM_Visualize_ExternalCallInfo`: a CALL or DELEGATECALL statement that belongs
(transitively, through the internal call graph) to a public function whose
signature is `fallback()` or `receive()`.

So the emulator is built around one question -- *is an external call reachable
from the fallback/receive entry?* -- plus the generic structural risk features
named in the work order. Everything here is linear-sweep disassembly and static
CFG reachability over PUSH-resolved jump targets. No decompiler, no Datalog.

Deliberately cheap: this file exists to establish what a few microseconds of
hand-written analysis recovers, so the cost of the real analyzer can be judged
against it.
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Opcode tables (only what the emulator reasons about)
# ---------------------------------------------------------------------------
PUSH1, PUSH32 = 0x60, 0x7F
JUMPDEST = 0x5B
JUMP, JUMPI = 0x56, 0x57

# Block terminators: control cannot fall through these.
TERMINATORS = {
    0x00,  # STOP
    0xF3,  # RETURN
    0xFD,  # REVERT
    0xFE,  # INVALID
    0xFF,  # SELFDESTRUCT
    JUMP,
}

EXTERNAL_CALL_OPS = {0xF1: "CALL", 0xF4: "DELEGATECALL"}  # the rule's two opcodes
ALL_CALL_OPS = {0xF1: "CALL", 0xF2: "CALLCODE", 0xF4: "DELEGATECALL", 0xFA: "STATICCALL"}

SELFDESTRUCT = 0xFF
BALANCE, SELFBALANCE = 0x31, 0x47
CALLER = 0x33
EQ, SUB, XOR = 0x14, 0x03, 0x18
CALLVALUE = 0x34
CALLDATASIZE, CALLDATALOAD = 0x36, 0x35

ERC20_SELECTORS = {
    "a9059cbb",  # transfer(address,uint256)
    "23b872dd",  # transferFrom(address,address,uint256)
    "095ea7b3",  # approve(address,uint256)
}

FEATURE_NAMES = [
    "has_selfdestruct",
    "n_hardcoded_addresses",
    "balance_sweep",
    "immutable_call_target",
    "has_caller_guard",
    "erc20_selector_present",
    "code_bytes",
    "unique_opcode_count",
    "n_external_call_ops",
    "has_external_call",
    "has_dispatcher",
    "has_fallback_path",
    "fallback_reaches_external_call",
    "fallback_reaches_external_call_over",
    "n_fallback_reachable_blocks",
]


def _decode(code: bytes):
    """Linear sweep. Returns list of (pc, opcode, immediate_bytes)."""
    out = []
    i, n = 0, len(code)
    while i < n:
        op = code[i]
        if PUSH1 <= op <= PUSH32:
            size = op - PUSH1 + 1
            out.append((i, op, code[i + 1 : i + 1 + size]))
            i += 1 + size
        else:
            out.append((i, op, b""))
            i += 1
    return out


def _strip_metadata(code: bytes) -> bytes:
    """Drop a trailing CBOR metadata blob if the 2-byte length trailer points at one."""
    if len(code) < 2:
        return code
    declared = int.from_bytes(code[-2:], "big")
    if 0 < declared <= len(code) - 2:
        return code[: len(code) - 2 - declared]
    return code


def _build_blocks(instrs):
    """Split into basic blocks. Returns (block_starts, block_of_pc, blocks)."""
    starts = {0}
    for idx, (pc, op, imm) in enumerate(instrs):
        if op == JUMPDEST:
            starts.add(pc)
        if op in TERMINATORS or op == JUMPI:
            if idx + 1 < len(instrs):
                starts.add(instrs[idx + 1][0])
    ordered = sorted(starts)
    # map each instruction to its block start
    block_of = {}
    cur = 0
    starts_set = set(ordered)
    for pc, op, imm in instrs:
        if pc in starts_set:
            cur = pc
        block_of[pc] = cur
    blocks = {s: [] for s in ordered}
    for tup in instrs:
        blocks[block_of[tup[0]]].append(tup)
    return ordered, block_of, blocks


def _jumpdests(instrs):
    return {pc for pc, op, _ in instrs if op == JUMPDEST}


def _build_cfg(instrs, blocks, ordered, jdests):
    """Static CFG. Edges resolved only through literal PUSH targets.

    Returns (edges, selector_edges) where selector_edges are JUMPI targets guarded
    by a PUSH4 selector equality -- i.e. the dispatcher's "this selector matched"
    branches. Those are exactly the edges the fallback path does NOT take.
    """
    edges = {s: set() for s in ordered}
    over_edges = {s: set() for s in ordered}  # over-approximates dynamic dispatch
    selector_edges = {s: set() for s in ordered}
    nxt = {ordered[i]: ordered[i + 1] for i in range(len(ordered) - 1)}

    for start in ordered:
        body = blocks[start]
        if not body:
            continue
        last_pc, last_op, _ = body[-1]

        # does this block compare a PUSH4 selector? (dispatcher signature)
        has_push4_sel = any(
            PUSH1 <= op <= PUSH32 and (op - PUSH1 + 1) == 4 for _, op, _ in body
        )
        has_eq = any(op in (EQ, SUB, XOR) for _, op, _ in body)
        is_dispatch_block = has_push4_sel and has_eq

        if last_op in (JUMP, JUMPI):
            # precise: resolve target from the nearest preceding PUSH literal
            target = None
            for pc, op, imm in reversed(body[:-1]):
                if PUSH1 <= op <= PUSH32:
                    val = int.from_bytes(imm, "big") if imm else -1
                    if val in jdests:
                        target = val
                    break
            # over-approximate: any PUSHed valid JUMPDEST in this block is a candidate,
            # which is how Solidity's stack-passed return addresses actually resolve.
            cands = {
                int.from_bytes(imm, "big")
                for _, op, imm in body[:-1]
                if PUSH1 <= op <= PUSH32 and imm and int.from_bytes(imm, "big") in jdests
            }
            if target is not None:
                if last_op == JUMPI and is_dispatch_block:
                    selector_edges[start].add(target)
                else:
                    edges[start].add(target)
            if last_op == JUMPI and is_dispatch_block:
                over_edges[start] |= cands - {target} if target is not None else cands
            else:
                over_edges[start] |= cands
            if last_op == JUMPI and start in nxt:
                edges[start].add(nxt[start])  # fall-through: selector did not match
                over_edges[start].add(nxt[start])
        elif last_op in TERMINATORS:
            pass  # no fall-through
        elif start in nxt:
            edges[start].add(nxt[start])
            over_edges[start].add(nxt[start])

    # the over-approximate CFG keeps every precise edge too
    for s in ordered:
        over_edges[s] |= edges[s]

    return edges, over_edges, selector_edges


def _reachable(edges, root, ordered):
    seen, stack = set(), [root]
    valid = set(ordered)
    while stack:
        b = stack.pop()
        if b in seen or b not in valid:
            continue
        seen.add(b)
        stack.extend(edges.get(b, ()))
    return seen


def extract(bytecode_hex: str) -> dict:
    """Emulator feature vector for one runtime bytecode."""
    raw = bytecode_hex[2:] if bytecode_hex[:2].lower() == "0x" else bytecode_hex
    raw = "".join(c for c in raw if c in "0123456789abcdefABCDEF")
    if len(raw) % 2:
        raw = raw[:-1]
    try:
        code_full = bytes.fromhex(raw)
    except ValueError:
        code_full = b""
    code = _strip_metadata(code_full)

    instrs = _decode(code)
    f = {name: 0.0 for name in FEATURE_NAMES}
    f["code_bytes"] = float(len(code_full))
    if not instrs:
        return f

    ops = [op for _, op, _ in instrs]
    f["unique_opcode_count"] = float(len(set(ops)))
    f["has_selfdestruct"] = float(SELFDESTRUCT in ops)
    f["n_hardcoded_addresses"] = float(
        sum(1 for _, op, imm in instrs if PUSH1 <= op <= PUSH32 and (op - PUSH1 + 1) == 20)
    )
    f["n_external_call_ops"] = float(sum(1 for o in ops if o in EXTERNAL_CALL_OPS))
    f["has_external_call"] = float(f["n_external_call_ops"] > 0)

    selectors = {
        imm.hex() for _, op, imm in instrs if PUSH1 <= op <= PUSH32 and (op - PUSH1 + 1) == 4
    }
    f["erc20_selector_present"] = float(bool(selectors & ERC20_SELECTORS))

    # balance sweep: BALANCE/SELFBALANCE feeding a CALL within a short window
    WINDOW = 12
    sweep = 0.0
    for idx, o in enumerate(ops):
        if o in ALL_CALL_OPS:
            if any(ops[j] in (BALANCE, SELFBALANCE) for j in range(max(0, idx - WINDOW), idx)):
                sweep = 1.0
                break
    f["balance_sweep"] = sweep

    # immutable call target: PUSH20 literal shortly before a call op
    imm_target = 0.0
    for idx, (pc, o, im) in enumerate(instrs):
        if o in ALL_CALL_OPS:
            lo = max(0, idx - WINDOW)
            if any(
                PUSH1 <= instrs[j][1] <= PUSH32 and (instrs[j][1] - PUSH1 + 1) == 20
                for j in range(lo, idx)
            ):
                imm_target = 1.0
                break
    f["immutable_call_target"] = imm_target

    # CALLER-comparison access guard: CALLER ... EQ/SUB/XOR ... JUMPI in a window
    guard = 0.0
    for idx, o in enumerate(ops):
        if o == CALLER:
            hi = min(len(ops), idx + WINDOW)
            seg = ops[idx:hi]
            if any(s in (EQ, SUB, XOR) for s in seg) and JUMPI in seg:
                guard = 1.0
                break
    f["has_caller_guard"] = guard

    # ---- rule-targeted: fallback/receive reachability to an external call ----
    ordered, block_of, blocks = _build_blocks(instrs)
    jdests = _jumpdests(instrs)
    edges, over_edges, selector_edges = _build_cfg(instrs, blocks, ordered, jdests)

    f["has_dispatcher"] = float(any(sel for sel in selector_edges.values()))

    # Fallback path = everything reachable from entry WITHOUT taking a matched-selector
    # branch. If there is no dispatcher at all, the whole contract is the fallback.
    fb_blocks = _reachable(edges, ordered[0], ordered)
    fb_over = _reachable(over_edges, ordered[0], ordered)
    f["n_fallback_reachable_blocks"] = float(len(fb_blocks))

    f["fallback_reaches_external_call_over"] = float(
        any(
            any(op in EXTERNAL_CALL_OPS for _, op, _ in blocks.get(b, []))
            for b in fb_over
        )
    )

    # A fallback path exists if the non-matching path leads somewhere other than an
    # immediate revert.
    non_revert = 0
    for b in fb_blocks:
        body = blocks.get(b, [])
        if body and body[-1][1] not in (0xFD, 0xFE):
            non_revert += 1
    f["has_fallback_path"] = float(non_revert > 1)

    reaches = 0.0
    for b in fb_blocks:
        if any(op in EXTERNAL_CALL_OPS for _, op, _ in blocks.get(b, [])):
            reaches = 1.0
            break
    f["fallback_reaches_external_call"] = reaches

    return f


def featurize(bytecodes) -> np.ndarray:
    rows = [extract(b) for b in bytecodes]
    return np.array([[r[n] for n in FEATURE_NAMES] for r in rows], dtype=np.float64)
