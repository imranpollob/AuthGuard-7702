#!/usr/bin/env python3
"""
04_mutations.py -- semantics-preserving mutation stress-test (Task D, the spine).

Protocol (honesty constraint 6):
  * GroupKFold(5) on frozen family_id. Split BEFORE mutation.
  * Detectors are trained/populated on TRAIN families using ORIGINAL (M0) bytecode only.
  * HELD-OUT malicious contracts are mutated M0->M3; mutants inherit the source family and
    stay strictly on the held-out (test) side. No mutant ever touches training.
  * Retained detection = recall on the held-out malicious set at each tier, at the operating
    threshold each model chose on its TRAIN data. Averaged over the 5 folds.

Mutation tiers (all verified control-flow / opcode-token preserving; see verify_preservation):
  M0  original
  M1  metadata-trailer rewrite            (CBOR solc-metadata hash randomized; not executed)
  M2  M1 + PUSH20 address-immediate randomization + dead-code APPEND (benign-sourced,
                                            unreachable, ~+20% static ops)   [attacker redeploy]
  M3  M2 + PUSH4 selector rewrite         (function-rename-at-fact-level; defeats name rule)

Extra: dead-code-volume sweep on top of M3 (0/25/50/100/200% appended) to locate the learned
       models' breaking point -- the honest limit of opcode-structure robustness.

Outputs:
  results/mutation_curve.json      retained-detection recall per method per tier (+ per fold)
  results/mutation_preservation.json   semantics-preservation verification stats
  results/mutation_volume.json     dead-code-volume sweep
"""
import os, sys, json, hashlib, warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, disasm, SEED
from ag_features import featurize, build_sensitive_selector_set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
N_SPLITS = 5
_PUSH1, _PUSH32 = 0x60, 0x7f

SENS = build_sensitive_selector_set()

# ----------------------------------------------------------------------------
# byte-level helpers
# ----------------------------------------------------------------------------
def to_bytes(hexstr):
    hexstr = normalize_bytecode(hexstr)
    try:
        return bytearray.fromhex(hexstr)
    except ValueError:
        clean = "".join(c for c in hexstr if c in "0123456789abcdef")
        if len(clean) % 2:
            clean = clean[:-1]
        return bytearray.fromhex(clean)


def find_metadata_split(b):
    """Return index where solc CBOR metadata trailer starts, or len(b) if none.
    Trailer = last 2 bytes are big-endian length L of a CBOR map that begins with 0xa2."""
    if len(b) < 4:
        return len(b)
    L = (b[-2] << 8) | b[-1]
    start = len(b) - 2 - L
    if 0 <= start < len(b) and b[start] == 0xa2:
        return start
    return len(b)


def push_positions(b, end):
    """Yield (op_index_byte, push_size, imm_start, imm_end) for PUSH ops in b[:end]."""
    i, n = 0, min(end, len(b))
    out = []
    while i < n:
        op = b[i]
        if _PUSH1 <= op <= _PUSH32:
            size = op - _PUSH1 + 1
            out.append((i, size, i + 1, i + 1 + size))
            i += 1 + size
        else:
            i += 1
    return out


def det_rng(seed_material):
    h = hashlib.blake2b(seed_material.encode(), digest_size=8, salt=(SEED).to_bytes(8, "little"))
    return np.random.default_rng(int.from_bytes(h.digest(), "little"))


# ----------------------------------------------------------------------------
# mutations
# ----------------------------------------------------------------------------
def mut_metadata(b, addr):
    """M1: randomize the 32-byte ipfs/bzzr hash inside CBOR metadata (behavior-neutral)."""
    b = bytearray(b)
    ms = find_metadata_split(b)
    rng = det_rng("meta:" + addr)
    if ms < len(b):
        # rewrite the metadata region's bytes except the final 2 length bytes and 0xa2 marker
        for j in range(ms + 1, len(b) - 2):
            b[j] = int(rng.integers(0, 256))
    else:
        # no metadata: append a synthetic neutral CBOR-like trailer
        payload = bytes(int(rng.integers(0, 256)) for _ in range(32))
        trailer = bytearray([0xa2]) + payload
        L = len(trailer)
        b += trailer + bytearray([(L >> 8) & 0xff, L & 0xff])
    return b


def mut_addr_immediates(b, addr):
    """M2a: randomize PUSH20 (address) immediates in executable region (width preserved)."""
    b = bytearray(b)
    ms = find_metadata_split(b)
    rng = det_rng("addr:" + addr)
    for (opi, size, s, e) in push_positions(b, ms):
        if size == 20:
            for j in range(s, e):
                b[j] = int(rng.integers(0, 256))
    return b


BENIGN_DEADCODE = None
def _load_deadcode_source():
    global BENIGN_DEADCODE
    if BENIGN_DEADCODE is None:
        df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
        # a mid-size benign_general contract's executable bytes = realistic decoy padding
        bg = df[df["class"] == "benign_general"].iloc[0]["bytecode"]
        bb = to_bytes(bg)
        ms = find_metadata_split(bb)
        BENIGN_DEADCODE = bytes(bb[:ms])
    return BENIGN_DEADCODE


def mut_deadcode_append(b, addr, frac):
    """M2b: append unreachable benign-sourced opcodes after everything (offsets unshifted).
    Prepend a STOP so it is provably never fallen-into; sized to ~frac of executable ops."""
    if frac <= 0:
        return bytearray(b)
    b = bytearray(b)
    ms = find_metadata_split(b)
    n_exec = ms
    src = _load_deadcode_source()
    want = max(1, int(n_exec * frac))
    rng = det_rng("dead:" + addr + f":{frac}")
    off = int(rng.integers(0, max(1, len(src) - want - 1)))
    chunk = src[off:off + want]
    # 0x00 STOP guarantees the appended block is unreachable by fall-through
    return b + bytearray([0x00]) + bytearray(chunk)


def mut_selector_rewrite(b, addr):
    """M3: rewrite PUSH4 selector immediates that match sensitive selectors -> fresh selectors.
    Defeats the USENIX name-match rule while preserving control flow (width preserved)."""
    b = bytearray(b)
    ms = find_metadata_split(b)
    rng = det_rng("sel:" + addr)
    for (opi, size, s, e) in push_positions(b, ms):
        if size == 4:
            val = b[s:e].hex()
            if val in SENS:  # a sensitive selector -> rename
                for j in range(s, e):
                    b[j] = int(rng.integers(0, 256))
    return b


def make_mutant(orig_hex, addr, tier, extra_frac=0.20):
    b = to_bytes(orig_hex)
    if tier == "M0":
        return b
    b = mut_metadata(b, addr)                 # M1
    if tier == "M1":
        return b
    b = mut_addr_immediates(b, addr)          # M2
    b = mut_deadcode_append(b, addr, extra_frac)
    if tier == "M2":
        return b
    b = mut_selector_rewrite(b, addr)         # M3
    return b


def verify_preservation(orig_hex, mut_b):
    """Executable-region opcode TOKEN sequence must be identical (control-flow preserved).
    Compared over the ORIGINAL executable region only (before the CBOR metadata trailer);
    metadata bytes are data, not code, and M1 legitimately rewrites them."""
    ob = to_bytes(orig_hex)
    ms = find_metadata_split(ob)
    o_ops, _, _ = disasm(ob[:ms].hex())
    m_ops, _, _ = disasm(bytes(mut_b[:ms]).hex())
    return o_ops == m_ops


# ----------------------------------------------------------------------------
# stress test
# ----------------------------------------------------------------------------
def best_f1_threshold(y_true, scores):
    order = np.argsort(-scores); ys = y_true[order]
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys); P = ys.sum()
    prec = tp / np.maximum(tp + fp, 1); rec = tp / max(P, 1)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    return float(scores[order][int(np.argmax(f1))]) if len(f1) else 0.5


def gb():
    return XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
                         colsample_bytree=0.8, eval_metric="logloss", random_state=SEED,
                         n_jobs=4, tree_method="hist")


def main():
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    frozen = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    df["family_id"] = frozen["family_id"].values
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    df["bchash"] = df["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())

    # primary task population
    mask = df["class"].isin(["malicious", "benign_cleared"]).values
    sub = df[mask].reset_index(drop=True)
    y = (sub["class"] == "malicious").astype(int).values
    groups = sub["family_id"].values

    Xd = np.load(os.path.join(RES, "features_dense.npz"))["X"][mask]
    Xn = np.load(os.path.join(RES, "features_ngram.npz"))["X"][mask]
    Xfull = np.hstack([Xd, Xn])
    meta = json.load(open(os.path.join(RES, "feature_meta.json")))
    hist_slice = slice(0, meta["hist_dim"])
    name_j = meta["dense_cols"].index("has_sensitive_selector")
    call_j = meta["dense_cols"].index("n_call_family")

    tiers = ["M0", "M1", "M2", "M3"]
    methods = ["usenix_name_rule", "usenix_struct_rule", "blocklist",
               "opcode_xgb", "selector_model", "authguard"]
    curve = {m: {t: [] for t in tiers} for m in methods}   # per-fold recall lists
    preservation = {t: {"checked": 0, "preserved": 0} for t in tiers if t != "M0"}

    sel_cols = [i for i, c in enumerate(meta["dense_cols"])
                if c.startswith("has_") or c in ("n_selectors", "n_sensitive_selectors",
                                                 "n_call_family", "n_delegatecall")]

    gkf = GroupKFold(n_splits=N_SPLITS)
    for fold, (tr, te) in enumerate(gkf.split(Xd, y, groups)):
        ytr = y[tr]
        # ---- train learned models on M0 train ----
        xgb = gb(); xgb.fit(Xd[tr][:, hist_slice], ytr)
        thr_xgb = best_f1_threshold(ytr, xgb.predict_proba(Xd[tr][:, hist_slice])[:, 1])
        ag = gb(); ag.fit(Xfull[tr], ytr)
        thr_ag = best_f1_threshold(ytr, ag.predict_proba(Xfull[tr])[:, 1])
        scaler = StandardScaler().fit(Xd[tr][:, sel_cols])
        lr = LogisticRegression(max_iter=1000, random_state=SEED)
        lr.fit(scaler.transform(Xd[tr][:, sel_cols]), ytr)
        thr_lr = best_f1_threshold(ytr, lr.predict_proba(scaler.transform(Xd[tr][:, sel_cols]))[:, 1])
        train_mal_hashes = set(sub.iloc[tr][ytr.astype(bool)]["bchash"])

        # ---- held-out malicious only ----
        te_mal = [i for i in te if y[i] == 1]
        held = sub.iloc[te_mal]

        for t in tiers:
            # build mutant bytecodes for held-out malicious
            mut_hexes, hashes = [], []
            for _, row in held.iterrows():
                mb = make_mutant(row["bytecode"], row["address"], t)
                if t != "M0":
                    preservation[t]["checked"] += 1
                    preservation[t]["preserved"] += int(verify_preservation(row["bytecode"], mb))
                mut_hexes.append(mb.hex())
                hashes.append(hashlib.sha256(normalize_bytecode(mb.hex()).encode()).hexdigest())
            Xd_m, Xn_m, _ = featurize(mut_hexes, sens=SENS)
            Xfull_m = np.hstack([Xd_m, Xn_m])

            # recall of each method on these (all true positives)
            name_rec = float((Xd_m[:, name_j] > 0).mean())
            struct_rec = float((Xd_m[:, call_j] > 0).mean())
            block_rec = float(np.mean([h in train_mal_hashes for h in hashes]))
            xgb_rec = float((xgb.predict_proba(Xd_m[:, hist_slice])[:, 1] >= thr_xgb).mean())
            lr_rec = float((lr.predict_proba(scaler.transform(Xd_m[:, sel_cols]))[:, 1] >= thr_lr).mean())
            ag_rec = float((ag.predict_proba(Xfull_m)[:, 1] >= thr_ag).mean())

            curve["usenix_name_rule"][t].append(name_rec)
            curve["usenix_struct_rule"][t].append(struct_rec)
            curve["blocklist"][t].append(block_rec)
            curve["opcode_xgb"][t].append(xgb_rec)
            curve["selector_model"][t].append(lr_rec)
            curve["authguard"][t].append(ag_rec)
        print(f"  fold {fold}: authguard {['%.2f'%np.mean(curve['authguard'][t][-1:]) for t in tiers]} "
              f"name {['%.2f'%curve['usenix_name_rule'][t][-1] for t in tiers]}", flush=True)

    # aggregate mean+/-std across folds
    agg = {m: {t: {"mean": float(np.mean(curve[m][t])), "std": float(np.std(curve[m][t])),
                   "folds": curve[m][t]} for t in tiers} for m in methods}
    with open(os.path.join(RES, "mutation_curve.json"), "w") as f:
        json.dump(agg, f, indent=2)
    with open(os.path.join(RES, "mutation_preservation.json"), "w") as f:
        json.dump(preservation, f, indent=2)

    print("\n=== RETAINED-DETECTION (recall on held-out malicious), mean over folds ===")
    hdr = f'{"method":20s} ' + " ".join(f"{t:>7}" for t in tiers)
    print(hdr)
    for m in methods:
        print(f'{m:20s} ' + " ".join(f'{agg[m][t]["mean"]:7.3f}' for t in tiers))
    print("\npreservation:", preservation)

    # ---------------- dead-code volume sweep (on top of M3) ----------------
    # Find the learned models' breaking point: append increasing unreachable benign code.
    fracs = [0.0, 0.25, 0.5, 1.0, 2.0]
    vmethods = ["opcode_xgb", "authguard", "usenix_struct_rule", "usenix_name_rule"]
    vol = {m: {f: [] for f in fracs} for m in vmethods}
    for fold, (tr, te) in enumerate(gkf.split(Xd, y, groups)):
        ytr = y[tr]
        xgb = gb(); xgb.fit(Xd[tr][:, hist_slice], ytr)
        thr_xgb = best_f1_threshold(ytr, xgb.predict_proba(Xd[tr][:, hist_slice])[:, 1])
        ag = gb(); ag.fit(Xfull[tr], ytr)
        thr_ag = best_f1_threshold(ytr, ag.predict_proba(Xfull[tr])[:, 1])
        te_mal = [i for i in te if y[i] == 1]
        held = sub.iloc[te_mal]
        for fr in fracs:
            mut_hexes = []
            for _, row in held.iterrows():
                # full M3 semantics-preserving mutation, then extra dead-code volume = fr
                b = to_bytes(row["bytecode"])
                b = mut_metadata(b, row["address"])
                b = mut_addr_immediates(b, row["address"])
                b = mut_selector_rewrite(b, row["address"])
                b = mut_deadcode_append(b, row["address"], fr)
                mut_hexes.append(b.hex())
            Xd_m, Xn_m, _ = featurize(mut_hexes, sens=SENS)
            Xfull_m = np.hstack([Xd_m, Xn_m])
            vol["opcode_xgb"][fr].append(float((xgb.predict_proba(Xd_m[:, hist_slice])[:, 1] >= thr_xgb).mean()))
            vol["authguard"][fr].append(float((ag.predict_proba(Xfull_m)[:, 1] >= thr_ag).mean()))
            vol["usenix_struct_rule"][fr].append(float((Xd_m[:, call_j] > 0).mean()))
            vol["usenix_name_rule"][fr].append(float((Xd_m[:, name_j] > 0).mean()))
    vagg = {m: {str(fr): {"mean": float(np.mean(vol[m][fr])), "std": float(np.std(vol[m][fr]))}
                for fr in fracs} for m in vmethods}
    with open(os.path.join(RES, "mutation_volume.json"), "w") as f:
        json.dump(vagg, f, indent=2)
    print("\n=== DEAD-CODE VOLUME SWEEP (recall vs appended-unreachable-code fraction, on M3) ===")
    print(f'{"method":20s} ' + " ".join(f"+{int(fr*100)}%".rjust(7) for fr in fracs))
    for m in vmethods:
        print(f'{m:20s} ' + " ".join(f'{vagg[m][str(fr)]["mean"]:7.3f}' for fr in fracs))


if __name__ == "__main__":
    main()
