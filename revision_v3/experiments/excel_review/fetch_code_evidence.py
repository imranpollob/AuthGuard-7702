"""Fetches real, readable code evidence for the 20 frozen Pilot items -- verified-source
lookups (Sourcify v2, Blockscout v2, both keyless), proxy-implementation resolution via
eth_getStorageAt, and evmole-based decompilation (labeled disassembly with offsets, resolved
function selectors, storage layout) with 4byte.directory selector-name resolution, plus
ASCII-string and notable-constant extraction straight from the (locally available, already
frozen) runtime bytecode.

Does NOT touch pilot_manifest.csv, gold_dev_manifest.csv, or gold_test_manifest.csv -- read
only. Writes one folder per item under revision_v3/human_eval/pilot_code_evidence/.

Usage:
    python3 revision_v3/experiments/excel_review/fetch_code_evidence.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import evmole

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
MANIFEST_PATH = os.path.join(HUMAN_EVAL_DIR, "pilot_manifest.csv")
EVIDENCE_DIR = os.path.join(HUMAN_EVAL_DIR, "pilot_code_evidence")
SELECTOR_CACHE_PATH = os.path.join(EVIDENCE_DIR, "_selector_cache.json")

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
EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

USER_AGENT = "AuthGuard-7702-research/1.0 (academic reproducibility pipeline)"


def http_get(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def safe_folder_name(item_id: str) -> str:
    return item_id.replace(":", "_")


def check_sourcify(chain: str, address: str) -> dict:
    cid = CHAIN_IDS[chain]
    code, body = http_get(f"https://sourcify.dev/server/v2/contract/{cid}/{address}")
    result = {"http_status": code, "raw": None}
    try:
        result["raw"] = json.loads(body)
    except Exception:  # noqa: BLE001
        result["raw"] = {"unparsed": body[:500]}
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


def get_storage_at(chain: str, address: str, slot: str) -> str:
    client = ChainClient(chain)
    return client._call("eth_getStorageAt", [address, slot, "latest"])  # noqa: SLF001


def get_code(chain: str, address: str) -> str:
    client = ChainClient(chain)
    return client.get_code(address)


def slot_to_address(slot_value: str) -> str | None:
    hexpart = slot_value[2:] if slot_value.startswith("0x") else slot_value
    hexpart = hexpart.rjust(64, "0")
    addr = hexpart[-40:]
    if addr == "0" * 40:
        return None
    return "0x" + addr


_selector_cache: dict[str, str | None] = {}


def load_selector_cache() -> None:
    global _selector_cache
    if os.path.exists(SELECTOR_CACHE_PATH):
        with open(SELECTOR_CACHE_PATH) as f:
            _selector_cache = json.load(f)


def save_selector_cache() -> None:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(SELECTOR_CACHE_PATH, "w") as f:
        json.dump(_selector_cache, f, indent=2, sort_keys=True)


def resolve_selector(selector_hex: str) -> str | None:
    """selector_hex without 0x prefix, 8 hex chars."""
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
                # 4byte returns newest-submitted first; prefer the earliest-id (oldest,
                # most likely canonical) entry among duplicates.
                results = sorted(results, key=lambda r: r.get("id", 0))
                name = results[0]["text_signature"]
        except Exception:  # noqa: BLE001
            name = None
    _selector_cache[selector_hex] = name
    time.sleep(0.15)
    return name


STRING_RE = re.compile(rb"[\x20-\x7e]{6,}")


def extract_ascii_strings(bytecode_hex: str) -> list[str]:
    raw = bytes.fromhex(bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex)
    found = []
    for m in STRING_RE.finditer(raw):
        s = m.group().decode("ascii")
        if len(set(s)) <= 1:
            continue
        found.append(s)
    # dedupe, preserve order
    seen = set()
    out = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def analyze_bytecode(bytecode_hex: str) -> dict:
    info = evmole.contract_info(
        bytecode_hex, selectors=True, arguments=True, state_mutability=True,
        storage=True, disassemble=True,
    )
    disasm = [f"{off:5d}  {instr}" for off, instr in info.disassembled]

    functions = []
    for fn in info.functions:
        resolved = resolve_selector(fn.selector)
        functions.append({
            "selector": "0x" + fn.selector,
            "resolved_signature": resolved,
            "bytecode_offset": fn.bytecode_offset,
            "arguments": fn.arguments,
            "state_mutability": fn.state_mutability,
        })

    storage = [
        {"slot": s.slot, "offset": s.offset, "type": s.type,
         "n_reads": len(s.reads), "n_writes": len(s.writes)}
        for s in info.storage
    ]

    # Candidate selectors hidden in fallback-style comparisons: PUSH32 immediates whose
    # last 28 bytes (56 hex chars) are all zero -- i.e. a 4-byte selector left-padded the
    # way `calldataload(0)` naturally aligns it, compared directly without SHR/masking.
    fallback_selector_candidates = []
    for off, instr in info.disassembled:
        if instr.startswith("PUSH32 "):
            imm = instr.split(" ", 1)[1]
            if len(imm) == 64 and imm[8:] == "0" * 56 and imm[:8] != "0" * 8:
                fallback_selector_candidates.append((off, imm[:8]))
    fallback_selectors = []
    for off, sel in fallback_selector_candidates:
        resolved = resolve_selector(sel)
        fallback_selectors.append({
            "selector": "0x" + sel, "resolved_signature": resolved, "bytecode_offset": off,
        })

    # Notable PUSH20 constants (address-shaped, nonzero, not all-0xff).
    address_constants = []
    seen_addrs = set()
    for off, instr in info.disassembled:
        if instr.startswith("PUSH20 "):
            imm = instr.split(" ", 1)[1]
            if imm in ("0" * 40, "f" * 40) or imm in seen_addrs:
                continue
            seen_addrs.add(imm)
            address_constants.append({"bytecode_offset": off, "address": "0x" + imm})

    strings = extract_ascii_strings(bytecode_hex)

    return {
        "disassembly": disasm,
        "functions": functions,
        "fallback_selector_candidates": fallback_selectors,
        "storage": storage,
        "address_constants": address_constants,
        "ascii_strings": strings,
        "opcode_count": len(info.disassembled),
        "runtime_bytecode_length_bytes": (len(bytecode_hex) - 2) // 2,
    }


def write_item_folder(folder: str, bytecode_hex: str, chain: str, address: str,
                       verification: dict, analysis: dict, note: str = "") -> None:
    os.makedirs(folder, exist_ok=True)
    os.makedirs(os.path.join(folder, "decompiled"), exist_ok=True)

    with open(os.path.join(folder, "verification_status.json"), "w") as f:
        json.dump(verification, f, indent=2, default=str)

    with open(os.path.join(folder, "decompiled", "disassembly.txt"), "w") as f:
        f.write("\n".join(analysis["disassembly"]))

    with open(os.path.join(folder, "decompiled", "functions.json"), "w") as f:
        json.dump({
            "dispatched_functions": analysis["functions"],
            "fallback_selector_candidates": analysis["fallback_selector_candidates"],
        }, f, indent=2)

    with open(os.path.join(folder, "decompiled", "storage.json"), "w") as f:
        json.dump(analysis["storage"], f, indent=2)

    with open(os.path.join(folder, "decompiled", "constants.json"), "w") as f:
        json.dump(analysis["address_constants"], f, indent=2)

    with open(os.path.join(folder, "decompiled", "strings.txt"), "w") as f:
        f.write("\n".join(analysis["ascii_strings"]))

    readme = [
        f"# Code evidence for {chain}:{address}",
        "",
        f"Verified source: {'YES' if verification.get('verified') else 'NO'} "
        f"(checked Sourcify v2 + Blockscout v2, both keyless, both queried live).",
        f"Runtime bytecode: {analysis['runtime_bytecode_length_bytes']} bytes, "
        f"{analysis['opcode_count']} decoded instructions.",
        f"Dispatched function selectors found: {len(analysis['functions'])}.",
        f"Fallback-comparison selector candidates found: {len(analysis['fallback_selector_candidates'])}.",
        f"Address-shaped constants found: {len(analysis['address_constants'])}.",
        f"ASCII strings extracted: {len(analysis['ascii_strings'])}.",
    ]
    if note:
        readme += ["", note]
    with open(os.path.join(folder, "README.md"), "w") as f:
        f.write("\n".join(readme) + "\n")


def main() -> int:
    load_selector_cache()
    with open(MANIFEST_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20, f"expected 20 Pilot items, found {len(rows)}"

    summary = {}
    implementation_cache: dict[str, dict] = {}

    for row in rows:
        item_id, chain, address = row["item_id"], row["chain"], row["address"]
        print(f"=== {item_id} ===")
        bytecode_hex = row["runtime_bytecode"]

        sourcify = check_sourcify(chain, address)
        blockscout = check_blockscout(chain, address)
        verification = {"sourcify": sourcify, "blockscout": blockscout,
                         "verified": sourcify["verified"] or blockscout["verified"]}

        analysis = analyze_bytecode(bytecode_hex)

        # Proxy-implementation resolution via storage (EIP-1967 slot first, then slot 0 --
        # the pattern used by GnosisSafeProxy-style contracts, which several Pilot items
        # match structurally).
        impl_info = None
        for slot_name, slot in (("eip1967_implementation", EIP1967_IMPL_SLOT), ("slot_0", "0x0")):
            try:
                val = get_storage_at(chain, address, slot)
            except Exception as e:  # noqa: BLE001
                val = None
                print(f"  storage read failed ({slot_name}): {e}")
            impl_addr = slot_to_address(val) if val else None
            if impl_addr:
                impl_info = {"slot_used": slot_name, "implementation_address": impl_addr}
                break

        folder = os.path.join(EVIDENCE_DIR, safe_folder_name(item_id))
        note = ""
        if impl_info:
            note = (f"Possible proxy: storage slot ({impl_info['slot_used']}) resolves to "
                    f"implementation address {impl_info['implementation_address']}. See "
                    f"../_shared_implementations/{impl_info['implementation_address']}/ for "
                    "that contract's own code evidence.")
            impl_addr = impl_info["implementation_address"]
            if impl_addr not in implementation_cache:
                print(f"  resolving implementation {impl_addr} on {chain}")
                impl_code = get_code(chain, impl_addr)
                impl_verification = {
                    "sourcify": check_sourcify(chain, impl_addr),
                    "blockscout": check_blockscout(chain, impl_addr),
                }
                impl_verification["verified"] = (
                    impl_verification["sourcify"]["verified"] or impl_verification["blockscout"]["verified"]
                )
                impl_analysis = analyze_bytecode(impl_code) if impl_code and impl_code != "0x" else None
                impl_folder = os.path.join(EVIDENCE_DIR, "_shared_implementations", impl_addr)
                if impl_analysis:
                    write_item_folder(impl_folder, impl_code, chain, impl_addr,
                                       impl_verification, impl_analysis,
                                       note=f"This is a shared implementation/singleton contract "
                                            f"resolved from one or more Pilot proxy items on {chain}.")
                implementation_cache[impl_addr] = {
                    "chain": chain, "verified": impl_verification["verified"],
                    "code_bytes": len(impl_code) // 2 - 1 if impl_code else 0,
                }

        write_item_folder(folder, bytecode_hex, chain, address, verification, analysis, note=note)

        summary[item_id] = {
            "chain": chain, "address": address,
            "verified_source": verification["verified"],
            "n_dispatched_functions": len(analysis["functions"]),
            "n_fallback_selector_candidates": len(analysis["fallback_selector_candidates"]),
            "n_resolved_selectors": sum(
                1 for fn in analysis["functions"] if fn["resolved_signature"]
            ) + sum(
                1 for fn in analysis["fallback_selector_candidates"] if fn["resolved_signature"]
            ),
            "n_ascii_strings": len(analysis["ascii_strings"]),
            "n_address_constants": len(analysis["address_constants"]),
            "implementation_resolved": impl_info,
        }
        save_selector_cache()

    with open(os.path.join(EVIDENCE_DIR, "_fetch_summary.json"), "w") as f:
        json.dump({"items": summary, "shared_implementations": implementation_cache}, f, indent=2)

    print("\n=== SUMMARY ===")
    for item_id, s in summary.items():
        print(item_id, s)
    print("\nshared implementations:", implementation_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
