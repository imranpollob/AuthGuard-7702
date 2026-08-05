"""Shared, reusable evidence-collection pipeline for Pilot/Gold-Dev/Gold-Test/temporal items.

Generalizes the logic originally developed by hand for the 20 Pilot items
(fetch_code_evidence.py) into a scale-safe, automated pipeline:
  - live keyless verified-source checks (Sourcify v2, Blockscout v2)
  - proxy/implementation resolution (EIP-1967 slot, Safe-style slot 0)
  - full evmole decompilation (disassembly, selectors, storage)
  - 4byte.directory selector resolution (cached)
  - ASCII string / address-constant extraction
  - an automated GUARD TRACER: follows each dispatched function's body and classifies its
    entry as GUARDED / OPEN / AMBIGUOUS with respect to CALLER/ORIGIN-based restriction,
    generalizing the manual disassembly-reading method used for the Pilot batch.

This module performs no LLM judgment -- it only produces the structured, deterministic
evidence that the labeling step (generate_provisional_labels.py) reasons over.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import evmole

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
from temporal.rpc_client import ChainClient  # noqa: E402

CHAIN_IDS = {"ethereum": 1, "optimism": 10, "base": 8453, "polygon": 137, "bnb": 56,
             "gnosis": 100, "arbitrum": 42161}
BLOCKSCOUT_HOSTS = {
    "ethereum": "eth.blockscout.com", "optimism": "optimism.blockscout.com",
    "base": "base.blockscout.com", "arbitrum": "arbitrum.blockscout.com",
    "polygon": "polygon.blockscout.com", "bnb": "bsc.blockscout.com",
    "gnosis": "gnosis.blockscout.com",
}
EIP1967_IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bb"
USER_AGENT = "AuthGuard-7702-research/1.0 (academic reproducibility pipeline)"

STRING_RE = re.compile(rb"[\x20-\x7e]{6,}")


def http_get(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def check_sourcify(chain: str, address: str) -> dict:
    cid = CHAIN_IDS[chain]
    code, body = http_get(f"https://sourcify.dev/server/v2/contract/{cid}/{address}")
    result = {"http_status": code, "raw": None}
    try:
        result["raw"] = json.loads(body)
    except Exception:  # noqa: BLE001
        result["raw"] = {"unparsed": (body or "")[:500]}
    result["verified"] = bool(result["raw"].get("match"))
    return result


def check_blockscout(chain: str, address: str) -> dict:
    host = BLOCKSCOUT_HOSTS[chain]
    code, body = http_get(f"https://{host}/api/v2/smart-contracts/{address}")
    result = {"http_status": code, "raw": None}
    if code == 200:
        try:
            result["raw"] = json.loads(body)
        except Exception:  # noqa: BLE001
            result["raw"] = {"unparsed": body[:500]}
    result["verified"] = bool(result["raw"] and result["raw"].get("is_verified"))
    return result


def get_storage_at(chain: str, address: str, slot: str) -> str | None:
    client = ChainClient(chain)
    try:
        return client._call("eth_getStorageAt", [address, slot, "latest"])  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return None


def get_code(chain: str, address: str) -> str | None:
    client = ChainClient(chain)
    try:
        return client.get_code(address)
    except Exception:  # noqa: BLE001
        return None


def slot_to_address(slot_value: str | None) -> str | None:
    if not slot_value:
        return None
    hexpart = slot_value[2:] if slot_value.startswith("0x") else slot_value
    hexpart = hexpart.rjust(64, "0")
    addr = hexpart[-40:]
    if addr == "0" * 40:
        return None
    return "0x" + addr


_selector_cache: dict[str, str | None] = {}
_selector_cache_path: str | None = None


def init_selector_cache(path: str) -> None:
    global _selector_cache, _selector_cache_path
    _selector_cache_path = path
    if os.path.exists(path):
        with open(path) as f:
            _selector_cache = json.load(f)


def save_selector_cache() -> None:
    if _selector_cache_path is None:
        return
    os.makedirs(os.path.dirname(_selector_cache_path), exist_ok=True)
    with open(_selector_cache_path, "w") as f:
        json.dump(_selector_cache, f, indent=2, sort_keys=True)


def resolve_selector(selector_hex: str) -> str | None:
    if selector_hex in _selector_cache:
        return _selector_cache[selector_hex]
    code, body = http_get(
        f"https://www.4byte.directory/api/v1/signatures/?hex_signature=0x{selector_hex}&format=json"
    )
    name = None
    if code == 200:
        try:
            data = json.loads(body)
            results = data.get("results", [])
            if results:
                results = sorted(results, key=lambda r: r.get("id", 0))
                name = results[0]["text_signature"]
        except Exception:  # noqa: BLE001
            name = None
    _selector_cache[selector_hex] = name
    time.sleep(0.1)
    return name


def extract_ascii_strings(bytecode_hex: str) -> list[str]:
    raw = bytes.fromhex(bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex)
    found = []
    for m in STRING_RE.finditer(raw):
        s = m.group().decode("ascii")
        if len(set(s)) <= 1:
            continue
        found.append(s)
    seen, out = set(), []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def analyze_bytecode(bytecode_hex: str) -> dict:
    """evmole-based decompilation: disassembly, selectors, storage, notable constants."""
    info = evmole.contract_info(
        bytecode_hex, selectors=True, arguments=True, state_mutability=True,
        storage=True, disassemble=True,
    )
    disasm = list(info.disassembled)  # [(offset, "OP imm"), ...]

    functions = []
    for fn in info.functions:
        resolved = resolve_selector(fn.selector)
        functions.append({
            "selector": "0x" + fn.selector, "resolved_signature": resolved,
            "bytecode_offset": fn.bytecode_offset, "arguments": fn.arguments,
            "state_mutability": fn.state_mutability,
        })

    storage = [
        {"slot": s.slot, "offset": s.offset, "type": s.type,
         "n_reads": len(s.reads), "n_writes": len(s.writes)}
        for s in info.storage
    ]

    fallback_selectors = []
    for off, instr in disasm:
        if instr.startswith("PUSH32 "):
            imm = instr.split(" ", 1)[1]
            if len(imm) == 64 and imm[8:] == "0" * 56 and imm[:8] != "0" * 8:
                resolved = resolve_selector(imm[:8])
                fallback_selectors.append({
                    "selector": "0x" + imm[:8], "resolved_signature": resolved, "bytecode_offset": off,
                })

    address_constants, seen_addrs = [], set()
    for off, instr in disasm:
        if instr.startswith("PUSH20 "):
            imm = instr.split(" ", 1)[1]
            if imm in ("0" * 40, "f" * 40) or imm in seen_addrs:
                continue
            seen_addrs.add(imm)
            address_constants.append({"bytecode_offset": off, "address": "0x" + imm})

    return {
        "disassembly": [f"{off:5d}  {ins}" for off, ins in disasm],
        "disassembly_raw": disasm,
        "functions": functions,
        "fallback_selector_candidates": fallback_selectors,
        "storage": storage,
        "address_constants": address_constants,
        "ascii_strings": extract_ascii_strings(bytecode_hex),
        "opcode_count": len(disasm),
        "runtime_bytecode_length_bytes": (len(bytecode_hex) - 2) // 2,
        "has_delegatecall": any(ins == "DELEGATECALL" for _, ins in disasm),
        "has_selfdestruct": any(ins == "SELFDESTRUCT" for _, ins in disasm),
        "has_create": any(ins in ("CREATE", "CREATE2") for _, ins in disasm),
        "n_caller_total": sum(1 for _, ins in disasm if ins == "CALLER"),
        "n_origin_total": sum(1 for _, ins in disasm if ins == "ORIGIN"),
    }


# ---------------------------------------------------------------------------
# Automated guard tracer
# ---------------------------------------------------------------------------

def _body_bounds(disasm_raw: list[tuple[int, str]], dispatched_offsets: list[int],
                  start_off: int, max_window: int = 400) -> tuple[int, int]:
    """Approximate the byte-offset range of one dispatched function's reachable body: from
    its own dispatch offset to the next-higher dispatch offset (or a capped window if this
    is the last one / offsets are non-monotonic). This is a heuristic, same idea as the
    manual '40-70 line window' used when tracing the Pilot items by hand -- imprecise at the
    margins, which is exactly why ambiguous cases are classified AMBIGUOUS rather than OPEN."""
    higher = sorted(o for o in dispatched_offsets if o > start_off)
    end_off = higher[0] if higher else start_off + max_window
    end_off = min(end_off, start_off + max_window)
    return start_off, end_off


def trace_guards(analysis: dict) -> dict:
    """For every dispatched function (and, best-effort, fallback-only contracts with no
    clean dispatcher), classify its guard status.

    Returns {"per_function": [...], "any_sensitive_open": bool, "all_traced_guarded": bool,
             "any_ambiguous": bool, "overall_status": "GUARDED_ALL"|"OPEN_FOUND"|"AMBIGUOUS"}
    """
    disasm_raw = analysis["disassembly_raw"]
    functions = analysis["functions"]
    dispatched_offsets = [fn["bytecode_offset"] for fn in functions]

    per_function = []
    any_open, any_ambiguous, any_guarded = False, False, False

    if not functions:
        # No cleanly dispatched functions found (e.g. atypical dispatch, or pure-fallback
        # contract). Fall back to a whole-program scan: if CALLER/ORIGIN never appears at
        # all, that's still a meaningful (if coarse) OPEN signal; otherwise AMBIGUOUS.
        if analysis["n_caller_total"] == 0 and analysis["n_origin_total"] == 0:
            return {
                "per_function": [], "any_sensitive_open": True, "all_traced_guarded": False,
                "any_ambiguous": False,
                "overall_status": "OPEN_FOUND",
                "note": "No dispatched functions recovered by evmole (atypical/fallback-only "
                        "bytecode); whole-program scan found zero CALLER/ORIGIN opcodes.",
            }
        return {
            "per_function": [], "any_sensitive_open": False, "all_traced_guarded": False,
            "any_ambiguous": True, "overall_status": "AMBIGUOUS",
            "note": "No dispatched functions recovered by evmole; cannot reliably locate "
                    "function bodies to trace guards despite CALLER/ORIGIN opcodes existing "
                    "somewhere in the program.",
        }

    offset_index = {off: i for i, (off, _) in enumerate(disasm_raw)}

    for fn in functions:
        start_off, end_off = _body_bounds(disasm_raw, dispatched_offsets, fn["bytecode_offset"])
        start_i = offset_index.get(start_off)
        if start_i is None:
            start_i = next((i for i, (o, _) in enumerate(disasm_raw) if o >= start_off), None)
        if start_i is None:
            per_function.append({**fn, "guard_status": "AMBIGUOUS",
                                  "guard_opcode": None, "guard_constant": None, "guard_offset": None,
                                  "note": "could not locate body start in disassembly"})
            any_ambiguous = True
            continue
        window = []
        for i in range(start_i, len(disasm_raw)):
            off, ins = disasm_raw[i]
            if off >= end_off:
                break
            window.append((off, ins))

        guard_found = None
        for wi, (off, ins) in enumerate(window):
            if ins not in ("CALLER", "ORIGIN"):
                continue
            # Look ahead a few instructions for AND ... EQ ... JUMPI (a comparison-based guard)
            lookahead = window[wi:wi + 8]
            has_eq = any(i2 == "EQ" for _, i2 in lookahead)
            has_jumpi = any(i2 == "JUMPI" for _, i2 in lookahead)
            if has_eq and has_jumpi:
                # Find a PUSH20 shortly before this CALLER/ORIGIN (the compared constant).
                # Standard codegen is `PUSH20 <addr> PUSH20 <mask> AND` -- take the FIRST
                # (earliest) non-mask PUSH20 in the window, since the address literal precedes
                # its own masking constant; a later PUSH20 in the same window is very likely
                # the 0xffff...ff (or 0x0) bitmask applied to CALLER/ORIGIN itself, not the
                # compared value.
                lookbehind = window[max(0, wi - 6):wi]
                constant = None
                mask_values = {"f" * 40, "0" * 40}
                for _, ins2 in lookbehind:
                    if ins2.startswith("PUSH20 "):
                        val = ins2.split(" ", 1)[1]
                        if val not in mask_values:
                            constant = "0x" + val
                            break
                if constant is None:
                    # Some guards compare ADDRESS() to CALLER() (self-call) with no PUSH20
                    if any(i2 == "ADDRESS" for _, i2 in lookbehind):
                        constant = "SELF_ADDRESS"
                guard_found = {
                    "opcode": ins, "offset": off, "constant": constant,
                }
                break
        if guard_found:
            per_function.append({**fn, "guard_status": "GUARDED",
                                  "guard_opcode": guard_found["opcode"],
                                  "guard_constant": guard_found["constant"],
                                  "guard_offset": guard_found["offset"], "note": ""})
            any_guarded = True
            continue

        # No comparison-based guard found in-window. Distinguish OPEN (window fully covers
        # the body, confirmed via a terminating opcode) from AMBIGUOUS (window was capped
        # before reaching a clear function end, e.g. very large function).
        terminators = {"STOP", "RETURN", "REVERT", "INVALID", "SELFDESTRUCT"}
        reached_terminator = any(ins in terminators for _, ins in window)
        capped = (end_off - start_off) >= 400 and not reached_terminator
        if capped:
            per_function.append({**fn, "guard_status": "AMBIGUOUS", "guard_opcode": None,
                                  "guard_constant": None, "guard_offset": None,
                                  "note": "window capped before a clear terminator was reached"})
            any_ambiguous = True
        else:
            per_function.append({**fn, "guard_status": "OPEN", "guard_opcode": None,
                                  "guard_constant": None, "guard_offset": None,
                                  "note": "no CALLER/ORIGIN-based comparison found in the "
                                          "traced body window"})
            any_open = True

    if any_ambiguous and not any_open:
        overall = "AMBIGUOUS"
    elif any_open:
        overall = "OPEN_FOUND"
    elif any_guarded:
        overall = "GUARDED_ALL"
    else:
        overall = "AMBIGUOUS"

    return {
        "per_function": per_function,
        "any_sensitive_open": any_open,
        "all_traced_guarded": any_guarded and not any_open and not any_ambiguous,
        "any_ambiguous": any_ambiguous,
        "overall_status": overall,
    }


def enrich_item(chain: str, address: str, bytecode_hex: str) -> dict:
    """Full pipeline for one item: verification + decompile + proxy resolution + guard trace.
    Returns a single structured evidence dict. No LLM judgment happens here."""
    sourcify = check_sourcify(chain, address)
    blockscout = check_blockscout(chain, address)
    verification = {"sourcify": sourcify, "blockscout": blockscout,
                     "verified": sourcify["verified"] or blockscout["verified"]}

    analysis = analyze_bytecode(bytecode_hex)
    guard_trace = trace_guards(analysis)

    impl_info = None
    for slot_name, slot in (("eip1967_implementation", EIP1967_IMPL_SLOT), ("slot_0", "0x0")):
        val = get_storage_at(chain, address, slot)
        impl_addr = slot_to_address(val)
        if impl_addr and analysis["has_delegatecall"]:
            impl_info = {"slot_used": slot_name, "implementation_address": impl_addr}
            break
        if impl_addr and slot_name == "slot_0" and not analysis["has_delegatecall"]:
            # Non-DELEGATECALL slot-0 address (owner/destination pattern, not a proxy)
            impl_info = {"slot_used": slot_name, "implementation_address": impl_addr,
                         "is_delegatecall_target": False}
            break

    return {
        "chain": chain, "address": address, "verification": verification,
        "analysis": analysis, "guard_trace": guard_trace, "implementation": impl_info,
    }
