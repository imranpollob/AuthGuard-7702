#!/usr/bin/env python3
"""
ag_features.py -- single source of truth for bytecode featurization.
Used by 02_features.py (bulk) AND 04_mutations.py (on-the-fly mutant featurization)
so there is zero drift between the two.
"""
import os, json
import numpy as np
from ag_common import (normalize_bytecode, disasm, is_delegation_pointer,
                       OPCODE_VOCAB, _bl, opcode_kgrams)

NGRAM_DIM = 512
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SENSITIVE_SIGS = [
    "sweep(address[])", "sweepToken(address)", "sweepTokens(address,uint256)",
    "sweepETH(uint256)", "drain(address)", "drainToken(address)", "steal(address)",
    "attack()", "hack()", "exploit()", "pwn()",
]
GENERIC_SIGS = {
    "transfer(address,uint256)": "a9059cbb",
    "transferFrom(address,address,uint256)": "23b872dd",
    "approve(address,uint256)": "095ea7b3",
    "safeTransferFrom(address,address,uint256)": "42842e0e",
    "withdraw(uint256)": "2e1a7d4d",
    "owner()": "8da5cb5b",
    "execute(address,uint256,bytes)": "b61d27f6",
}


def _keccak_selector(sig):
    try:
        from Crypto.Hash import keccak
        k = keccak.new(digest_bits=256); k.update(sig.encode()); return k.hexdigest()[:8]
    except Exception:
        return None


def build_sensitive_selector_set():
    sel = set()
    for sig in SENSITIVE_SIGS:
        s = _keccak_selector(sig)
        if s:
            sel.add(s)
    art = os.path.join(ROOT, "USENIX EIP-7702 artifact", "eoa_detect", "decompile",
                       "AM_Detect_SensitiveSigName.jsonl")
    if os.path.exists(art):
        with open(art) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                for pair in row.get("result", []):
                    sh = pair[0].lower().replace("0x", "")
                    if len(sh) <= 8:
                        sel.add(sh.zfill(8))
    return sel


def _struct_features(bc, sens):
    ops, pushes, selset = disasm(bc)
    n = len(ops)
    f = {}
    f["code_bytes"] = len(bc) // 2
    f["n_ops"] = n
    f["n_selectors"] = len(selset)
    f["is_delegation_ptr"] = 1.0 if is_delegation_pointer(bc) else 0.0
    f["n_jumpdest"] = ops.count("JUMPDEST")
    f["n_jump"] = ops.count("JUMP")
    f["n_jumpi"] = ops.count("JUMPI")
    f["n_call"] = ops.count("CALL")
    f["n_staticcall"] = ops.count("STATICCALL")
    f["n_delegatecall"] = ops.count("DELEGATECALL")
    f["n_callcode"] = ops.count("CALLCODE")
    f["n_call_family"] = f["n_call"] + f["n_staticcall"] + f["n_delegatecall"] + f["n_callcode"]
    f["n_create"] = ops.count("CREATE") + ops.count("CREATE2")
    f["n_selfdestruct"] = ops.count("SELFDESTRUCT")
    f["n_sstore"] = ops.count("SSTORE")
    f["n_sload"] = ops.count("SLOAD")
    f["n_log"] = sum(ops.count(f"LOG{i}") for i in range(5))
    f["n_revert"] = ops.count("REVERT")
    f["n_invalid"] = sum(1 for o in ops if o.startswith("UNK_") or o == "INVALID")
    f["n_push"] = ops.count("PUSH")
    f["mean_push_size"] = float(np.mean(pushes)) if pushes else 0.0
    f["n_push4"] = sum(1 for s in pushes if s == 4)
    f["n_push20"] = sum(1 for s in pushes if s == 20)
    f["n_push32"] = sum(1 for s in pushes if s == 32)
    f["jumpdest_density"] = f["n_jumpdest"] / max(n, 1)
    f["call_density"] = f["n_call_family"] / max(n, 1)
    f["push_density"] = f["n_push"] / max(n, 1)
    f["has_sensitive_selector"] = 1.0 if (selset & sens) else 0.0
    f["n_sensitive_selectors"] = len(selset & sens)
    for name, selhex in GENERIC_SIGS.items():
        f[f"has_{name.split('(')[0]}"] = 1.0 if selhex in selset else 0.0
    return f, ops


# canonical dense column order (must match struct dict insertion order + histogram prefix)
_STRUCT_ORDER = None
def _struct_cols():
    global _STRUCT_ORDER
    if _STRUCT_ORDER is None:
        f, _ = _struct_features("00", set())
        _STRUCT_ORDER = list(f.keys())
    return _STRUCT_ORDER


def featurize(bcs, sens=None):
    """bcs: iterable of RAW bytecode strings. Returns (X_dense, X_ngram, dense_cols)."""
    if sens is None:
        sens = build_sensitive_selector_set()
    bcs = [normalize_bytecode(b) for b in bcs]
    vocab_idx = {name: i for i, name in enumerate(OPCODE_VOCAB)}
    hist = np.zeros((len(bcs), len(OPCODE_VOCAB)), dtype=np.float32)
    ngram = np.zeros((len(bcs), NGRAM_DIM), dtype=np.float32)
    struct_rows = []
    scols = _struct_cols()
    for r, bc in enumerate(bcs):
        f, ops = _struct_features(bc, sens)
        struct_rows.append([f[c] for c in scols])
        if ops:
            tot = len(ops)
            for o in ops:
                j = vocab_idx.get(o)
                if j is not None:
                    hist[r, j] += 1.0 / tot
            grams = opcode_kgrams(ops, k=4)
            for g in grams:
                ngram[r, _bl(g.encode(), 2) % NGRAM_DIM] += 1.0
            ngram[r] /= max(len(grams), 1)
    X_struct = np.array(struct_rows, dtype=np.float32)
    X_dense = np.hstack([hist, X_struct])
    dense_cols = [f"op_{n}" for n in OPCODE_VOCAB] + scols
    return X_dense, ngram, dense_cols
