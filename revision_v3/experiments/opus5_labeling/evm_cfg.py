"""CFG + symbolic-stack analysis of EVM runtime bytecode.

Motivation
----------
The Phase-3B guard tracer (`excel_review/evidence_pipeline.trace_guards`) classifies a
dispatched function by scanning the *contiguous byte window* between its dispatch offset and
the next one, looking for `CALLER/ORIGIN ... EQ ... JUMPI` within 8 instructions. That is a
linear scan, not a control-flow analysis, so it structurally cannot see:

  * guards implemented in a shared internal helper (Solidity modifiers compile to internal
    functions reached by a JUMP, usually placed far from the caller's byte window),
  * guards reached through any jump at all (the function body is rarely contiguous),
  * signature-based authorization (`ecrecover`, precompile 0x01),
  * storage-based permission checks whose comparison is against an `SLOAD` value,
  * whether a sensitive opcode is even *reachable* from the entry point it was attributed to.

Its "OPEN" therefore means "no recognized guard in the byte window", which is
`INCOMPLETE_GUARD_EVIDENCE`, not "no access control". This module replaces that with:

  1. a real disassembler + basic-block CFG,
  2. a bounded symbolic-stack executor that resolves dynamic JUMP targets (internal calls and
     returns) and tracks value provenance (calldata / caller / origin / address / sload /
     ecrecover / const),
  3. guard identification at JUMPI sites whose *condition* is provenance-tainted by an
     authorization source,
  4. a guard-dominance test: a sensitive operation is UNGUARDED only if it stays reachable
     from the function entry when traversal is cut at every guard JUMPI. This is a genuine
     "there exists an unauthenticated path" claim, not an absence-of-pattern claim.

Everything here is local (no network). Analysis limits are explicit and every item records
whether it hit them, so an incomplete analysis is reported as incomplete rather than silently
treated as "no guard found".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from analysis.solidity_metadata import validated_solidity_metadata_start

# --------------------------------------------------------------------------------------
# Opcode table: name, number of stack items popped, number pushed.
# --------------------------------------------------------------------------------------

_OPS: Dict[int, Tuple[str, int, int]] = {
    0x00: ("STOP", 0, 0), 0x01: ("ADD", 2, 1), 0x02: ("MUL", 2, 1), 0x03: ("SUB", 2, 1),
    0x04: ("DIV", 2, 1), 0x05: ("SDIV", 2, 1), 0x06: ("MOD", 2, 1), 0x07: ("SMOD", 2, 1),
    0x08: ("ADDMOD", 3, 1), 0x09: ("MULMOD", 3, 1), 0x0A: ("EXP", 2, 1),
    0x0B: ("SIGNEXTEND", 2, 1),
    0x10: ("LT", 2, 1), 0x11: ("GT", 2, 1), 0x12: ("SLT", 2, 1), 0x13: ("SGT", 2, 1),
    0x14: ("EQ", 2, 1), 0x15: ("ISZERO", 1, 1), 0x16: ("AND", 2, 1), 0x17: ("OR", 2, 1),
    0x18: ("XOR", 2, 1), 0x19: ("NOT", 1, 1), 0x1A: ("BYTE", 2, 1), 0x1B: ("SHL", 2, 1),
    0x1C: ("SHR", 2, 1), 0x1D: ("SAR", 2, 1),
    0x20: ("KECCAK256", 2, 1),
    0x30: ("ADDRESS", 0, 1), 0x31: ("BALANCE", 1, 1), 0x32: ("ORIGIN", 0, 1),
    0x33: ("CALLER", 0, 1), 0x34: ("CALLVALUE", 0, 1), 0x35: ("CALLDATALOAD", 1, 1),
    0x36: ("CALLDATASIZE", 0, 1), 0x37: ("CALLDATACOPY", 3, 0), 0x38: ("CODESIZE", 0, 1),
    0x39: ("CODECOPY", 3, 0), 0x3A: ("GASPRICE", 0, 1), 0x3B: ("EXTCODESIZE", 1, 1),
    0x3C: ("EXTCODECOPY", 4, 0), 0x3D: ("RETURNDATASIZE", 0, 1),
    0x3E: ("RETURNDATACOPY", 3, 0), 0x3F: ("EXTCODEHASH", 1, 1),
    0x40: ("BLOCKHASH", 1, 1), 0x41: ("COINBASE", 0, 1), 0x42: ("TIMESTAMP", 0, 1),
    0x43: ("NUMBER", 0, 1), 0x44: ("PREVRANDAO", 0, 1), 0x45: ("GASLIMIT", 0, 1),
    0x46: ("CHAINID", 0, 1), 0x47: ("SELFBALANCE", 0, 1), 0x48: ("BASEFEE", 0, 1),
    0x49: ("BLOBHASH", 1, 1), 0x4A: ("BLOBBASEFEE", 0, 1),
    0x50: ("POP", 1, 0), 0x51: ("MLOAD", 1, 1), 0x52: ("MSTORE", 2, 0),
    0x53: ("MSTORE8", 2, 0), 0x54: ("SLOAD", 1, 1), 0x55: ("SSTORE", 2, 0),
    0x56: ("JUMP", 1, 0), 0x57: ("JUMPI", 2, 0), 0x58: ("PC", 0, 1), 0x59: ("MSIZE", 0, 1),
    0x5A: ("GAS", 0, 1), 0x5B: ("JUMPDEST", 0, 0), 0x5C: ("TLOAD", 1, 1),
    0x5D: ("TSTORE", 2, 0), 0x5E: ("MCOPY", 3, 0), 0x5F: ("PUSH0", 0, 1),
    0xF0: ("CREATE", 3, 1), 0xF1: ("CALL", 7, 1), 0xF2: ("CALLCODE", 7, 1),
    0xF3: ("RETURN", 2, 0), 0xF4: ("DELEGATECALL", 6, 1), 0xF5: ("CREATE2", 4, 1),
    0xFA: ("STATICCALL", 6, 1), 0xFD: ("REVERT", 2, 0), 0xFE: ("INVALID", 0, 0),
    0xFF: ("SELFDESTRUCT", 1, 0),
}
for _i in range(1, 33):
    _OPS[0x5F + _i] = (f"PUSH{_i}", 0, 1)
for _i in range(1, 17):
    _OPS[0x7F + _i] = (f"DUP{_i}", _i, _i + 1)
    _OPS[0x8F + _i] = (f"SWAP{_i}", _i + 1, _i + 1)
for _i in range(0, 5):
    _OPS[0xA0 + _i] = (f"LOG{_i}", 2 + _i, 0)

TERMINALS = {"STOP", "RETURN", "REVERT", "INVALID", "SELFDESTRUCT"}

# Sensitive operations, with the impact class we report for each.
SENSITIVE = {
    "CALL": "external_call_or_value_transfer",
    "CALLCODE": "callcode",
    "DELEGATECALL": "delegatecall",
    "CREATE": "contract_creation",
    "CREATE2": "contract_creation",
    "SELFDESTRUCT": "selfdestruct",
    "SSTORE": "storage_write",
}

# Provenance tags that make a JUMPI condition an authorization guard.
# `address` is deliberately NOT here on its own: a branch that merely touches ADDRESS() is
# usually a `target != address(this)` sanity check, not access control. It counts only in
# combination with `caller` (the self-call pattern), which is handled in guard_semantics.
STRONG_AUTH_SRC = {"caller", "origin", "ecrecover"}
MEDIUM_AUTH_SRC = {"sload", "tload"}

MASK160 = (1 << 160) - 1
UINT256 = (1 << 256) - 1


@dataclass(frozen=True)
class Val:
    """A symbolic stack value: a constant (if known), provenance tags, and -- when this value
    is the result of comparing an authorization source against something -- the constant it was
    compared against.

    `cmp` is what makes the difference between `msg.sender == address(this)` (the account
    owner), `msg.sender == <stored authority>` and `msg.sender == 0xHARDCODED` (a fixed third
    party). Without it every caller check looks alike, which is precisely the distinction an
    EIP-7702 delegate review turns on.
    """

    const: Optional[int] = None
    src: FrozenSet[str] = frozenset()
    cmp: Optional[int] = None
    cmp_src: FrozenSet[str] = frozenset()

    def key(self) -> Tuple:
        # Comparison provenance affects guard meaning (for example self-call versus storage
        # authority) and therefore must participate in state equivalence.
        return (self.const, tuple(sorted(self.src)), self.cmp, tuple(sorted(self.cmp_src)))


UNKNOWN = Val()


def disassemble(code: bytes) -> List[Tuple[int, str, Optional[int]]]:
    """Linear-sweep disassembly. Returns [(pc, opname, immediate_int_or_None)]."""
    out: List[Tuple[int, str, Optional[int]]] = []
    pc = 0
    n = len(code)
    while pc < n:
        op = code[pc]
        name, _, _ = _OPS.get(op, (f"UNKNOWN_{op:02x}", 0, 0))
        if name.startswith("PUSH") and name != "PUSH0":
            width = int(name[4:])
            imm = int.from_bytes(code[pc + 1: pc + 1 + width], "big") if pc + 1 + width <= n else None
            out.append((pc, name, imm))
            pc += 1 + width
        else:
            out.append((pc, name, None))
            pc += 1
    return out


@dataclass
class SensitiveHit:
    pc: int
    op: str
    impact: str
    target_const: Optional[int] = None
    target_src: FrozenSet[str] = frozenset()
    value_src: FrozenSet[str] = frozenset()
    value_const: Optional[int] = None
    data_src: FrozenSet[str] = frozenset()
    slot_const: Optional[int] = None

    def to_dict(self) -> dict:
        d = {
            "pc": self.pc,
            "op": self.op,
            "impact": self.impact,
            "target_src": sorted(self.target_src),
            "value_src": sorted(self.value_src),
            "data_src": sorted(self.data_src),
        }
        if self.target_const is not None:
            d["target_const"] = f"0x{self.target_const & MASK160:040x}"
        if self.value_const is not None:
            d["value_const"] = self.value_const
        if self.slot_const is not None:
            d["storage_slot"] = f"0x{self.slot_const:x}"
        return d


def guard_semantics(src: FrozenSet[str], cmp_src: FrozenSet[str] = frozenset(),
                    cmp_const: Optional[int] = None) -> str:
    """Human-readable meaning of an authorization-tainted branch condition.

    `cmp_src`/`cmp_const` describe what the authorization source was compared *against*, which
    is what separates an owner check from a hardcoded-third-party check.
    """
    who = "msg.sender" if "caller" in src else ("tx.origin" if "origin" in src else "value")
    if "ecrecover" in src:
        return "signature_authorization (branch depends on an ecrecover result)"
    if "caller" in src and "origin" in src and not cmp_src:
        return "tx.origin == msg.sender check (rejects intermediary contracts, not attackers)"
    if "address" in cmp_src:
        return f"self_call_check ({who} == address(this)) — the canonical EIP-7702 pattern"
    if "origin" in cmp_src and "caller" in src:
        return "tx.origin == msg.sender check (rejects intermediary contracts, not attackers)"
    if cmp_src & {"sload", "tload"}:
        return f"storage_based_caller_check ({who} compared against a stored authority)"
    if "calldata" in cmp_src:
        return f"calldata_comparison ({who} compared against a caller-supplied value)"
    if cmp_const is not None and cmp_const != 0:
        return f"hardcoded_address_check ({who} compared against a fixed address literal)"
    if cmp_const == 0:
        return f"zero_address_check ({who} compared against address(0))"
    if "caller" in src:
        return "caller_check (msg.sender compared against an unresolved value)"
    if "origin" in src:
        return "tx_origin_check (tx.origin compared against an unresolved value)"
    if "sload" in src or "tload" in src:
        return "storage_condition (e.g. initialized flag, paused flag, or an authority slot)"
    return "unclassified"


@dataclass
class GuardHit:
    pc: int
    kind: str            # "strong" | "medium"
    src: FrozenSet[str]
    compared_const: Optional[int] = None
    compared_src: FrozenSet[str] = frozenset()

    def to_dict(self) -> dict:
        d = {
            "pc": self.pc,
            "kind": self.kind,
            "condition_provenance": sorted(self.src),
            "compared_against_provenance": sorted(self.compared_src),
            "semantics": guard_semantics(self.src, self.compared_src, self.compared_const),
        }
        if self.compared_const is not None:
            d["compared_address_constant"] = f"0x{self.compared_const & MASK160:040x}"
        return d


@dataclass
class TraversalResult:
    sensitive: Dict[int, SensitiveHit] = field(default_factory=dict)
    guards: Dict[int, GuardHit] = field(default_factory=dict)
    reached_ecrecover: bool = False
    unresolved_jumps: int = 0
    states_explored: int = 0
    hit_state_cap: bool = False
    stack_underflows: int = 0
    hit_per_pc_cap: bool = False
    used_state_widening: bool = False


class Analyzer:
    """Bounded symbolic-stack CFG explorer over one runtime bytecode."""

    MAX_STATES = 60000
    MAX_PER_PC = 96
    WIDEN_AFTER = 8
    MAX_STACK = 64

    def __init__(self, code: bytes, calldata_word0: Optional[int] = None,
                 calldatasize: Optional[int] = None):
        # Optional concrete calldata model. Seeding CALLDATALOAD(0) with a selector that
        # matches no dispatched function (and CALLDATASIZE with 0 or 4) makes every dispatch
        # comparison fold to a constant, so traversal deterministically follows the
        # receive()/fallback() path -- which is exactly what the source analyzer's rule
        # ("external call reachable from receive()/fallback()") quantifies over.
        self.calldata_word0 = calldata_word0
        self.calldatasize = calldatasize
        self.code = code
        self.instrs = disassemble(code)
        self.by_pc: Dict[int, Tuple[int, str, Optional[int]]] = {
            pc: (pc, nm, imm) for pc, nm, imm in self.instrs
        }
        self.order = [pc for pc, _, _ in self.instrs]
        self.next_pc: Dict[int, Optional[int]] = {}
        for i, pc in enumerate(self.order):
            self.next_pc[pc] = self.order[i + 1] if i + 1 < len(self.order) else None
        self.jumpdests: Set[int] = {pc for pc, nm, _ in self.instrs if nm == "JUMPDEST"}

    # -- constant folding -------------------------------------------------------------
    @staticmethod
    def _fold(op: str, args: List[Val]) -> Optional[int]:
        if not args:
            return None
        cs = [a.const for a in args]
        if any(c is None for c in cs):
            # AND with a full 160-bit mask is an address truncation: keep the other operand.
            if op == "AND" and len(cs) == 2:
                for i, c in enumerate(cs):
                    if c in (MASK160, UINT256):
                        other = args[1 - i].const
                        if other is not None:
                            return other & (c if c == MASK160 else UINT256)
            return None
        a = cs[0]
        b = cs[1] if len(cs) > 1 else None
        try:
            if op == "ADD":
                return (a + b) & UINT256
            if op == "SUB":
                return (a - b) & UINT256
            if op == "MUL":
                return (a * b) & UINT256
            if op == "DIV":
                return 0 if b == 0 else a // b
            if op == "MOD":
                return 0 if b == 0 else a % b
            if op == "AND":
                return a & b
            if op == "OR":
                return a | b
            if op == "XOR":
                return a ^ b
            if op == "NOT":
                return (~a) & UINT256
            if op == "EQ":
                return 1 if a == b else 0
            if op == "LT":
                return 1 if a < b else 0
            if op == "GT":
                return 1 if a > b else 0
            if op == "ISZERO":
                return 1 if a == 0 else 0
            if op == "SHL":
                return (b << a) & UINT256 if a < 256 else 0
            if op == "SHR":
                return (b >> a) if a < 256 else 0
            if op == "EXP":
                return pow(a, b, 1 << 256)
        except (ValueError, OverflowError):
            return None
        return None

    @staticmethod
    def _pad(stack: List[Val], need: int, res: TraversalResult) -> None:
        """Underflow-tolerant stack model.

        Aborting on underflow silently truncates the traversal and under-reports reachable
        sensitive operations -- the exact failure mode that made an `executeBatch` function
        look like it contained no external call. Padding with UNKNOWN keeps exploration going
        and over-approximates instead, which is the safe direction for a reachability claim.
        The event is counted so the item is reported as analysis-incomplete.
        """
        res.stack_underflows += 1
        while len(stack) < need:
            stack.insert(0, UNKNOWN)

    def _step_block(self, pc: int, stack: List[Val], res: TraversalResult,
                    stop_at_guard_kinds: Set[str]) -> List[Tuple[int, List[Val]]]:
        """Execute straight-line from `pc` until a control-flow split/terminal.

        Returns the list of (successor_pc, successor_stack) to continue from.
        Records sensitive ops and guards into `res` as a side effect.
        """
        succs: List[Tuple[int, List[Val]]] = []
        cur = pc
        steps = 0
        while cur is not None and steps < 6000:
            steps += 1
            entry = self.by_pc.get(cur)
            if entry is None:
                return succs
            _, name, imm = entry

            if name.startswith("UNKNOWN_"):
                return succs

            if name.startswith("PUSH"):
                stack.append(Val(const=(0 if name == "PUSH0" else imm)))
                cur = self.next_pc[cur]

            elif name.startswith("DUP"):
                k = int(name[3:])
                if len(stack) < k:
                    self._pad(stack, k, res)
                stack.append(stack[-k])
                cur = self.next_pc[cur]

            elif name.startswith("SWAP"):
                k = int(name[4:])
                if len(stack) < k + 1:
                    self._pad(stack, k + 1, res)
                stack[-1], stack[-1 - k] = stack[-1 - k], stack[-1]
                cur = self.next_pc[cur]

            elif name == "JUMP":
                if not stack:
                    res.stack_underflows += 1
                    res.unresolved_jumps += 1
                    return succs
                dest = stack.pop()
                if dest.const is not None and dest.const in self.jumpdests:
                    succs.append((dest.const, stack))
                else:
                    res.unresolved_jumps += 1
                return succs

            elif name == "JUMPI":
                if len(stack) < 2:
                    self._pad(stack, 2, res)
                dest = stack.pop()
                cond = stack.pop()
                if cond.const is not None:
                    # Condition folded to a literal (typically a dispatcher selector
                    # comparison under a seeded calldata model): follow only the feasible
                    # branch. This both makes selector seeding meaningful and prunes large
                    # numbers of infeasible paths.
                    if cond.const == 0:
                        fall = self.next_pc[cur]
                        if fall is not None:
                            succs.append((fall, stack))
                    elif dest.const is not None and dest.const in self.jumpdests:
                        succs.append((dest.const, stack))
                    else:
                        res.unresolved_jumps += 1
                    return succs
                guard_kind = None
                if cond.src & STRONG_AUTH_SRC:
                    guard_kind = "strong"
                elif cond.src & MEDIUM_AUTH_SRC:
                    guard_kind = "medium"
                if guard_kind is not None:
                    prev = res.guards.get(cur)
                    if prev is None or (prev.kind == "medium" and guard_kind == "strong"):
                        res.guards[cur] = GuardHit(
                            pc=cur, kind=guard_kind, src=cond.src,
                            compared_const=cond.cmp, compared_src=cond.cmp_src,
                        )
                if guard_kind is not None and guard_kind in stop_at_guard_kinds:
                    # Cut traversal here: anything past this point is authorization-gated.
                    return succs
                fall = self.next_pc[cur]
                if fall is not None:
                    succs.append((fall, list(stack)))
                if dest.const is not None and dest.const in self.jumpdests:
                    succs.append((dest.const, list(stack)))
                elif dest.const is None:
                    res.unresolved_jumps += 1
                return succs

            elif name in TERMINALS:
                if name == "SELFDESTRUCT":
                    tgt = stack[-1] if stack else UNKNOWN
                    res.sensitive.setdefault(cur, SensitiveHit(
                        pc=cur, op=name, impact=SENSITIVE[name],
                        target_const=tgt.const, target_src=tgt.src))
                return succs

            else:
                spec = None
                for code_i, (nm, npop, npush) in _OPS.items():
                    if nm == name:
                        spec = (npop, npush)
                        break
                npop, npush = spec if spec else (0, 0)
                if len(stack) < npop:
                    self._pad(stack, npop, res)
                args = [stack.pop() for _ in range(npop)]

                if name in SENSITIVE:
                    hit = SensitiveHit(pc=cur, op=name, impact=SENSITIVE[name])
                    if name in ("CALL", "CALLCODE"):
                        # gas, target, value, argOff, argLen, retOff, retLen
                        hit.target_const, hit.target_src = args[1].const, args[1].src
                        hit.value_const, hit.value_src = args[2].const, args[2].src
                        hit.data_src = args[3].src
                        if args[1].const == 1:
                            res.reached_ecrecover = True
                    elif name in ("DELEGATECALL",):
                        hit.target_const, hit.target_src = args[1].const, args[1].src
                        hit.data_src = args[2].src
                    elif name == "SSTORE":
                        hit.slot_const = args[0].const
                        hit.value_src = args[1].src
                    elif name in ("CREATE", "CREATE2"):
                        hit.value_const, hit.value_src = args[0].const, args[0].src
                    res.sensitive.setdefault(cur, hit)

                if name == "STATICCALL" and args[1].const == 1:
                    res.reached_ecrecover = True

                # push results
                if npush:
                    src: Set[str] = set()
                    for a in args:
                        src |= a.src
                    if name == "CALLER":
                        src.add("caller")
                    elif name == "ORIGIN":
                        src.add("origin")
                    elif name == "ADDRESS":
                        src.add("address")
                    elif name == "CALLDATALOAD":
                        src.add("calldata")
                        if self.calldata_word0 is not None and args[0].const == 0:
                            stack.append(Val(const=self.calldata_word0, src=frozenset(src)))
                            cur = self.next_pc[cur]
                            continue
                    elif name == "CALLDATASIZE" and self.calldatasize is not None:
                        stack.append(Val(const=self.calldatasize, src=frozenset({"calldata"})))
                        cur = self.next_pc[cur]
                        continue
                    elif name == "SLOAD":
                        src.add("sload")
                    elif name == "TLOAD":
                        src.add("tload")
                    elif name == "CALLVALUE":
                        src.add("callvalue")
                    elif name == "SELFBALANCE":
                        src.add("selfbalance")
                    elif name == "BALANCE":
                        src.add("balance")
                    elif name in ("CALL", "STATICCALL", "DELEGATECALL", "CALLCODE"):
                        src.add("returndata")
                        if args[1].const == 1:
                            src.add("ecrecover")
                    elif name in ("MLOAD", "RETURNDATASIZE"):
                        src.add("memory")
                    folded = self._fold(name, args) if npush == 1 else None
                    cmp_const, cmp_src = None, frozenset()
                    if name in ("EQ", "SUB", "XOR") and len(args) == 2:
                        for i in (0, 1):
                            if args[i].src & {"caller", "origin"}:
                                other = args[1 - i]
                                cmp_const, cmp_src = other.const, other.src
                                break
                    else:
                        # Carry an already-established comparison through the ISZERO/AND/OR
                        # wrapping that Solidity puts between the EQ and the JUMPI.
                        for a in args:
                            if a.cmp is not None or a.cmp_src:
                                cmp_const, cmp_src = a.cmp, a.cmp_src
                                break
                    v = Val(const=folded, src=frozenset(src), cmp=cmp_const, cmp_src=cmp_src)
                    for _ in range(npush):
                        stack.append(v)
                if len(stack) > self.MAX_STACK:
                    del stack[: len(stack) - self.MAX_STACK]
                cur = self.next_pc[cur]
        return succs

    def traverse(self, entry_pc: int, stop_at_guard_kinds: Set[str]) -> TraversalResult:
        res = TraversalResult()
        seen: Set[Tuple] = set()
        per_pc: Dict[int, int] = {}
        work: List[Tuple[int, List[Val]]] = [(entry_pc, [])]
        while work:
            pc, stack = work.pop()
            n = per_pc.get(pc, 0)
            if n >= self.WIDEN_AFTER:
                # Loop counters and concrete memory offsets can generate an unbounded sequence
                # of otherwise equivalent states.  Widen them to UNKNOWN so a conditional is
                # explored in both directions.  Constants that are valid JUMPDESTs are retained:
                # they commonly encode internal-call return addresses, and losing them would
                # turn a resolvable control transfer into an incomplete one.
                widened = [
                    Val(
                        const=value.const if value.const in self.jumpdests else None,
                        src=value.src,
                        cmp=value.cmp,
                        cmp_src=value.cmp_src,
                    )
                    for value in stack
                ]
                if any(before.key() != after.key()
                       for before, after in zip(stack, widened)):
                    res.used_state_widening = True
                stack = widened
            key = (pc, tuple(v.key() for v in stack[-8:]))
            if key in seen:
                continue
            # Loops over calldata arrays generate unboundedly many distinct states because
            # memory offsets are concrete and increment each iteration. Cap revisits per
            # program counter instead of relying on the global cap alone, so a loop-heavy
            # contract still gets its non-loop paths explored.
            if n >= self.MAX_PER_PC:
                res.hit_per_pc_cap = True
                continue
            per_pc[pc] = n + 1
            seen.add(key)
            res.states_explored += 1
            if res.states_explored > self.MAX_STATES:
                res.hit_state_cap = True
                break
            for nxt, nstack in self._step_block(pc, list(stack), res, stop_at_guard_kinds):
                work.append((nxt, nstack))
        return res


def static_opcode_census(code: bytes) -> dict:
    """Linear-sweep census of sensitive opcodes in executable runtime bytes.

    Used as a soundness backstop for the traversal: if a `CALL`/`DELEGATECALL`/`CREATE*`/
    `SELFDESTRUCT` exists in the code but no traversal ever reached it, the analysis is
    incomplete for that item and must not be reported as "no sensitive operation found".
    A suffix is excluded only when it passes strict Solidity CBOR metadata validation.  The
    remaining sweep can still count instructions in unreachable/data regions -- it therefore
    continues to over-count, which is the safe direction for this use.
    """
    candidate_end = validated_solidity_metadata_start(code)
    executable_end = len(code)
    metadata_rejection_reason = None
    if candidate_end < len(code):
        full_instructions = disassemble(code)
        pcs = [pc for pc, _, _ in full_instructions]
        if candidate_end not in pcs:
            metadata_rejection_reason = "metadata_start_not_instruction_boundary"
        else:
            start_index = pcs.index(candidate_end)
            if start_index == 0 or full_instructions[start_index - 1][1] not in TERMINALS:
                metadata_rejection_reason = "executable_fallthrough_into_metadata_possible"
            elif any(name == "JUMPDEST" for _, name, _ in full_instructions[start_index:]):
                metadata_rejection_reason = "metadata_contains_executable_jumpdest"
            else:
                executable_end = candidate_end
    counts: Dict[str, int] = {}
    sites: Dict[str, List[int]] = {}
    for pc, name, _ in disassemble(code[:executable_end]):
        if name in SENSITIVE or name in ("STATICCALL", "CALLER", "ORIGIN", "ADDRESS"):
            counts[name] = counts.get(name, 0) + 1
            sites.setdefault(name, []).append(pc)
    return {
        "counts": counts,
        "sites": {k: v[:24] for k, v in sites.items()},
        "executable_bytes": executable_end,
        "metadata_bytes": len(code) - executable_end,
        "metadata_recognized": executable_end < len(code),
        "metadata_rejection_reason": metadata_rejection_reason,
    }


def analyze_fallback(code: bytes, known_selectors: Set[int]) -> dict:
    """Reproduce the source analyzer's rule locally.

    The USENIX `eoa_detect` Datalog rule flags a contract iff an external CALL/DELEGATECALL is
    reachable from `receive()` or `fallback()` -- entry points that, by definition, no caller
    check has been applied to at dispatch time. We model that directly: pick a 4-byte selector
    that matches no dispatched function, then explore (a) CALLDATASIZE == 0 (the `receive()`
    path) and (b) CALLDATASIZE == 4 with the non-matching selector (the `fallback()` path).

    Unlike the source rule, we also report whether those paths are guard-dominated, which is
    the distinction between "capability reachable from an unauthenticated entry point" and
    "unauthorized party can actually trigger it".
    """
    sel = 0xDEADBEEF
    while sel in known_selectors:
        sel = (sel + 1) & 0xFFFFFFFF
    out = {}
    for name, size in (("receive_path", 0), ("fallback_path", 4)):
        an = Analyzer(code, calldata_word0=sel << 224, calldatasize=size)
        full = an.traverse(0, stop_at_guard_kinds=set())
        no_strong = an.traverse(0, stop_at_guard_kinds={"strong"})
        calls = [h for h in full.sensitive.values() if h.op in ("CALL", "DELEGATECALL", "CALLCODE")]
        open_calls = [h for h in no_strong.sensitive.values()
                      if h.op in ("CALL", "DELEGATECALL", "CALLCODE")]
        out[name] = {
            "external_call_reachable": bool(calls),
            "external_call_reachable_without_passing_a_caller_guard": bool(open_calls),
            "calls": [h.to_dict() for h in sorted(calls, key=lambda x: x.pc)][:6],
            "guards_on_path": [g.to_dict() for g in sorted(full.guards.values(), key=lambda x: x.pc)][:6],
            "analysis_incomplete": (full.hit_state_cap or full.hit_per_pc_cap
                                    or full.unresolved_jumps > 0 or full.stack_underflows > 0),
        }
    out["source_rule_locally_reproduced"] = (
        out["receive_path"]["external_call_reachable"]
        or out["fallback_path"]["external_call_reachable"]
    )
    out["unauthenticated_external_call_from_fallback_or_receive"] = (
        out["receive_path"]["external_call_reachable_without_passing_a_caller_guard"]
        or out["fallback_path"]["external_call_reachable_without_passing_a_caller_guard"]
    )
    return out


def analyze_function(code: bytes, entry_pc: int, selector: Optional[int] = None,
                     calldatasize: int = 1024) -> dict:
    """Full guard-dominance analysis for one public function.

    When `selector` is supplied we start at `pc=0` and seed `CALLDATALOAD(0)` with that
    selector and `CALLDATASIZE` with a permissive length, so the dispatcher's comparisons fold
    and execution follows exactly the path the EVM would take for that call. This matters:
    starting directly at the function's dispatch target leaves the stack empty, so the
    `JUMP` that a Solidity function body uses to return to the dispatcher-pushed continuation
    is unresolvable and the traversal stops early -- silently under-reporting reachable
    sensitive operations. Starting at the dispatcher fixes that. `entry_pc` is retained for
    reporting and as the fallback when no selector is known.
    """
    if selector is not None:
        an = Analyzer(code, calldata_word0=selector << 224, calldatasize=calldatasize)
        start = 0
    else:
        an = Analyzer(code)
        start = entry_pc
    full = an.traverse(start, stop_at_guard_kinds=set())
    no_strong = an.traverse(start, stop_at_guard_kinds={"strong"})
    no_any = an.traverse(start, stop_at_guard_kinds={"strong", "medium"})

    def state_changing(hits: Dict[int, SensitiveHit]) -> Dict[int, SensitiveHit]:
        return {pc: h for pc, h in hits.items()}

    reachable = state_changing(full.sensitive)
    unguarded_strong = state_changing(no_strong.sensitive)
    unguarded_any = state_changing(no_any.sensitive)

    if not reachable:
        status = "NO_SENSITIVE_OP"
    elif unguarded_any:
        # A sensitive path survives even after cutting both strong and storage-derived guards.
        status = "UNGUARDED_PATH"
    elif unguarded_strong:
        # No path bypasses every recognized guard, but at least one relies only on a
        # storage-derived condition rather than caller/signature provenance.
        status = "GUARDED_BY_STORAGE_CONDITION"
    else:
        status = "GUARD_DOMINATED"

    incomplete = (full.hit_state_cap or full.hit_per_pc_cap
                  or full.unresolved_jumps > 0 or full.stack_underflows > 0)
    return {
        "entry_pc": entry_pc,
        "status": status,
        "analysis_incomplete": incomplete,
        "unresolved_dynamic_jumps": full.unresolved_jumps,
        "hit_state_cap": full.hit_state_cap,
        "hit_per_pc_cap": full.hit_per_pc_cap,
        "used_state_widening": full.used_state_widening,
        "stack_underflows": full.stack_underflows,
        "states_explored": full.states_explored,
        "reaches_ecrecover": full.reached_ecrecover,
        "reachable_sensitive": [h.to_dict() for h in sorted(reachable.values(), key=lambda x: x.pc)],
        "unguarded_sensitive": [h.to_dict() for h in sorted(unguarded_strong.values(), key=lambda x: x.pc)],
        "unguarded_even_by_storage": [h.to_dict() for h in sorted(unguarded_any.values(), key=lambda x: x.pc)],
        "guards": [g.to_dict() for g in sorted(full.guards.values(), key=lambda x: x.pc)],
    }
