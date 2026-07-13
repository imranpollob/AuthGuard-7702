#!/usr/bin/env python3
"""
01_freeze_families.py -- deterministic GLOBAL family clustering, frozen to disk.

Design (see DECISIONS.md):
  * Cluster ALL 3,258 contracts together (not per-class), so that near-duplicate
    bytecodes carrying conflicting labels share ONE family and can never straddle
    a leave-family-out split. This is the leakage-safe choice.
  * Deterministic MinHash (blake2b, seeded) over opcode 4-grams; union-find at a
    similarity threshold. No Python hash(); PYTHONHASHSEED-independent.
  * Freeze family_id at threshold 0.85 (the D3 choice). Report 0.75 / 0.90 for
    sensitivity. Everything downstream reads family_id (0.85) from the frozen file.

Output:
  family_assignment_frozen.csv   (address, chain, class, family_id[, _075,_090])
  results/family_structure.md     (counts, singleton %, largest, cross-chain %, cross-class %)
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, disasm, minhash_signature, SEED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "capability_dataset.csv")
OUT_CSV = os.path.join(ROOT, "family_assignment_frozen.csv")
OUT_MD = os.path.join(ROOT, "results", "family_structure.md")
THRESHOLDS = [0.75, 0.85, 0.90]
FREEZE_AT = 0.85
NUM_PERM = 128

np.random.seed(SEED)


class UF:
    def __init__(self, n):
        self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)  # deterministic: root = smaller index


def cluster(sigs, threshold):
    """Union-find over all pairs with MinHash-estimated Jaccard >= threshold.
    Blocked numpy comparison; deterministic. Returns list of family root indices."""
    n = sigs.shape[0]
    uf = UF(n)
    for i in range(n):
        if i + 1 >= n:
            break
        # equality fraction of sig[i] against every j>i
        eq = (sigs[i + 1:] == sigs[i]).mean(axis=1)  # (n-i-1,)
        js = np.nonzero(eq >= threshold)[0] + (i + 1)
        for j in js:
            uf.union(i, int(j))
    roots = np.array([uf.find(i) for i in range(n)])
    return roots


def relabel(roots, prefix="F"):
    """Map arbitrary root indices to stable F00001.. by first-appearance order."""
    order = {}
    out = []
    for r in roots:
        if r not in order:
            order[r] = len(order) + 1
        out.append(f"{prefix}{order[r]:05d}")
    return out


def family_stats(df, famcol):
    g = df.groupby(famcol)
    sizes = g.size()
    n_fam = len(sizes)
    singleton = int((sizes == 1).sum())
    largest = int(sizes.max())
    # cross-chain families: a family whose members span >1 chain
    cross_chain = int(g["chain"].nunique().gt(1).sum())
    # cross-class families: family spans >1 class (contamination signal)
    cross_class = int(g["class"].nunique().gt(1).sum())
    return dict(n_families=n_fam, singletons=singleton,
                singleton_pct=round(100 * singleton / n_fam, 1),
                largest=largest,
                cross_chain=cross_chain,
                cross_chain_pct=round(100 * cross_chain / n_fam, 1),
                cross_class=cross_class,
                cross_class_pct=round(100 * cross_class / n_fam, 1))


def main():
    df = pd.read_csv(DATA)
    df["bc"] = df["bytecode"].map(normalize_bytecode)
    print(f"[freeze] loaded {len(df)} rows; computing MinHash signatures...", flush=True)

    sigs = np.empty((len(df), NUM_PERM), dtype=np.uint64)
    for idx, bc in enumerate(df["bc"].values):
        ops, _, _ = disasm(bc)
        sigs[idx] = minhash_signature(ops, num_perm=NUM_PERM, k=4)
        if idx % 500 == 0:
            print(f"  sig {idx}/{len(df)}", flush=True)

    results = {}
    for t in THRESHOLDS:
        roots = cluster(sigs, t)
        col = f"family_id_{int(t*100):03d}"
        df[col] = relabel(roots)
        results[t] = family_stats(df, col)
        print(f"[freeze] t={t}: {results[t]}", flush=True)

    # canonical frozen family_id = the freeze threshold
    df["family_id"] = df[f"family_id_{int(FREEZE_AT*100):03d}"]

    keep = ["address", "chain", "class", "family_id",
            "family_id_075", "family_id_085", "family_id_090"]
    df[keep].to_csv(OUT_CSV, index=False)
    print(f"[freeze] wrote {OUT_CSV}", flush=True)

    # ---- markdown report ----
    lines = ["# Frozen Family Structure (Task A)", ""]
    lines.append(f"Global clustering of all **{len(df)}** contracts (leakage-safe, cross-class families kept together). "
                 f"Deterministic MinHash (blake2b, {NUM_PERM} perms) over opcode 4-grams; union-find at threshold. "
                 f"Frozen `family_id` = threshold **{FREEZE_AT}**.\n")
    lines.append("| threshold | families | singletons | singleton % | largest family | cross-chain fams | cross-chain % | cross-class fams | cross-class % |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for t in THRESHOLDS:
        s = results[t]
        star = " (**frozen**)" if t == FREEZE_AT else ""
        lines.append(f"| {t}{star} | {s['n_families']} | {s['singletons']} | {s['singleton_pct']} | "
                     f"{s['largest']} | {s['cross_chain']} | {s['cross_chain_pct']} | "
                     f"{s['cross_class']} | {s['cross_class_pct']} |")
    lines.append("")

    # per-class family view at frozen threshold
    fcol = "family_id"
    lines.append("## Per-class family counts at frozen threshold 0.85\n")
    lines.append("A family is counted for a class if >=1 member has that class. "
                 "Cross-class families (below) are the contamination signal.\n")
    lines.append("| class | rows | distinct families containing this class |")
    lines.append("|---|---:|---:|")
    for cls in ["malicious", "benign_cleared", "benign_general", "benign_AA"]:
        sub = df[df["class"] == cls]
        lines.append(f"| {cls} | {len(sub)} | {sub[fcol].nunique()} |")
    lines.append("")

    # malicious-only family structure (the population the paper characterizes)
    mal = df[df["class"] == "malicious"]
    msizes = mal.groupby(fcol).size()
    # families that are PURELY malicious vs mixed
    fam_classes = df.groupby(fcol)["class"].agg(lambda s: set(s))
    mal_fams = msizes.index
    pure_mal = [f for f in mal_fams if fam_classes[f] == {"malicious"}]
    lines.append("## Malicious population (family/singleton characterization, Claim 2)\n")
    lines.append(f"- Malicious contracts: **{len(mal)}**")
    lines.append(f"- Distinct families containing malicious: **{mal[fcol].nunique()}**")
    lines.append(f"- Purely-malicious families: **{len(pure_mal)}**")
    lines.append(f"- Malicious singletons (family size 1 counting malicious members only): "
                 f"**{int((msizes==1).sum())}** ({round(100*(msizes==1).sum()/len(msizes),1)}% of malicious families)")
    lines.append(f"- Largest malicious family size: **{int(msizes.max())}**")
    top = msizes.sort_values(ascending=False).head(10)
    lines.append("\nTop-10 malicious families by size:\n")
    lines.append("| family_id | malicious members |")
    lines.append("|---|---:|")
    for fid, cnt in top.items():
        lines.append(f"| {fid} | {int(cnt)} |")
    lines.append("")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))
    print(f"[freeze] wrote {OUT_MD}", flush=True)

    # machine-readable summary for downstream/figures
    with open(os.path.join(ROOT, "results", "family_structure.json"), "w") as f:
        json.dump({str(t): results[t] for t in THRESHOLDS}, f, indent=2)


if __name__ == "__main__":
    main()
