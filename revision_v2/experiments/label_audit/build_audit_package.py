#!/usr/bin/env python3
"""Phase 2B — reproducible manual label-adjudication package.

Generates stratified samples, anonymized evidence packets, blinded review forms, reviewer
assignments, guidelines, and agreement scripts. The coder provides NO labels. Human reviewers
fill the blinded forms later; merge + Cohen's kappa scripts ingest them without changing the
frozen sampling.

Strata (from G-DET v2 seed-7702 pooled per-row scores + conflict list):
  random_positive, random_weak_negative, high_scoring_false_positive,
  low_scoring_false_negative, high_confidence_correct, exact_bytecode_conflict,
  highest_scoring_benign_general, representative_transformed
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import load_corpus, RV2, DH, SEED, disasm  # noqa: E402
from ag_features import build_sensitive_selector_set  # noqa: E402

OUT = os.path.join(RV2, "artifact", "label_audit")
GDET = os.path.join(RV2, "results", "gdet_v2", "gdet_v2_per_row_scores.csv")
SENS = build_sensitive_selector_set()
PER_STRATUM = 25
N_REVIEWERS = 3
rng = np.random.default_rng(SEED)


def anon_id(sid):
    return "C" + hashlib.blake2b(sid.encode(), digest_size=6,
                                 salt=SEED.to_bytes(8, "little")).hexdigest()


def evidence_packet(row):
    bc = row["bc"]
    ops, pushes, sels = disasm(bc)
    return dict(
        anon_id=row["anon_id"], code_bytes=len(bc) // 2, n_ops=len(ops),
        n_call_family=sum(ops.count(o) for o in ("CALL", "STATICCALL", "DELEGATECALL", "CALLCODE")),
        has_delegatecall=("DELEGATECALL" in ops), has_sstore=("SSTORE" in ops),
        n_selectors=len(sels), has_sensitive_selector=bool(set(sels) & SENS),
        is_delegation_pointer=(bc.startswith("ef0100") and len(bc) == 46),
        opcode_prefix=" ".join(ops[:40]),
        model_risk_score=round(float(row.get("score", float("nan"))), 4),
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    df, _, _, _ = load_corpus()
    scores = pd.read_csv(GDET)
    ag = scores[(scores["task"] == "primary") & (scores["split"] == "family") &
                (scores["model"] == "authguard") & (scores["seed"] == SEED)].drop_duplicates("sid")
    df = df.merge(ag[["sid", "score", "pred", "y", "threshold"]], on="sid", how="left")

    prim = df[df["class"].isin(["malicious", "benign_cleared"])].copy()
    conflict = pd.read_csv(os.path.join(DH, "conflicting_bytecodes.csv"))

    def sample(pool, n, name):
        pool = pool.copy()
        if len(pool) == 0:
            return pool.assign(stratum=name)
        take = pool.sample(min(n, len(pool)), random_state=SEED)
        return take.assign(stratum=name)

    strata = []
    strata.append(sample(prim[prim["class"] == "malicious"], PER_STRATUM, "random_positive"))
    strata.append(sample(prim[prim["class"] == "benign_cleared"], PER_STRATUM, "random_weak_negative"))
    fp = prim[(prim["class"] == "benign_cleared") & (prim["pred"] == 1)]
    strata.append(sample(fp.sort_values("score", ascending=False).head(80), PER_STRATUM,
                         "high_scoring_false_positive"))
    fn = prim[(prim["class"] == "malicious") & (prim["pred"] == 0)]
    strata.append(sample(fn.sort_values("score").head(80), PER_STRATUM, "low_scoring_false_negative"))
    correct = prim[((prim["pred"] == prim["y"]) & (prim["y"] == 1) & (prim["score"] > 0.9))]
    strata.append(sample(correct, PER_STRATUM, "high_confidence_correct"))
    conf_idx = conflict["original_index"].unique()[:PER_STRATUM]
    cf = df[df.index.isin(conf_idx)]
    strata.append(cf.assign(stratum="exact_bytecode_conflict"))
    bg = df[df["class"] == "benign_general"]
    strata.append(sample(bg.sort_values("score", ascending=False).head(40), PER_STRATUM,
                         "highest_scoring_benign_general"))

    audit = pd.concat(strata, ignore_index=True).drop_duplicates("sid")
    audit["anon_id"] = audit["sid"].map(anon_id)

    # blinded key (kept separate; reviewers never see it)
    key = audit[["anon_id", "sid", "chain", "address", "class", "family_id", "stratum",
                 "score", "pred"]].copy()
    key.to_csv(os.path.join(OUT, "REVIEWER_KEY_do_not_distribute.csv"), index=False)

    packets = [evidence_packet(r) for _, r in audit.iterrows()]
    with open(os.path.join(OUT, "evidence_packets.json"), "w") as f:
        json.dump(packets, f, indent=2)

    # blinded review forms (one row/contract, empty label columns) per reviewer
    order = audit.sample(frac=1.0, random_state=SEED)["anon_id"].tolist()
    for r in range(N_REVIEWERS):
        form = pd.DataFrame({"anon_id": order})
        form["reviewer_id"] = f"R{r+1}"
        form["label"] = ""          # malicious | benign | uncertain
        form["confidence"] = ""     # high | medium | low
        form["rationale"] = ""
        form.to_csv(os.path.join(OUT, f"review_form_R{r+1}_BLINDED.csv"), index=False)

    assign = pd.DataFrame({"anon_id": order})
    assign["reviewers"] = ";".join(f"R{r+1}" for r in range(N_REVIEWERS))
    assign.to_csv(os.path.join(OUT, "reviewer_assignments.csv"), index=False)

    strata_counts = audit["stratum"].value_counts().to_dict()
    with open(os.path.join(OUT, "sampling_manifest.json"), "w") as f:
        json.dump(dict(seed=SEED, per_stratum_target=PER_STRATUM, n_reviewers=N_REVIEWERS,
                       total_items=int(len(audit)), strata_counts=strata_counts,
                       score_source="G-DET v2 authguard seed 7702 pooled test scores"),
                  f, indent=2)

    guidelines = """# Reviewer Guidelines — EIP-7702 Delegate Bytecode Adjudication

You receive anonymized evidence packets (structural bytecode signals + a model risk score;
addresses/chains withheld). For each anon_id record in your BLINDED form:

- label: one of `malicious`, `benign`, `uncertain`.
  - malicious: the bytecode's capability profile is consistent with unauthorized asset
    movement or account takeover if authorized as an EIP-7702 delegate.
  - benign: capability profile consistent with legitimate account-abstraction / wallet logic.
  - uncertain: bytecode alone is insufficient (e.g., delegation pointer, minimal proxy,
    storage-gated logic whose behavior depends on external state).
- confidence: high | medium | low.
- rationale: one sentence.

Do NOT look up addresses. Judge from the packet only. The model risk score is provided for
context; you may disagree with it. Work independently; do not confer with other reviewers.
"""
    with open(os.path.join(OUT, "REVIEWER_GUIDELINES.md"), "w") as f:
        f.write(guidelines)

    print(f"[audit] {len(audit)} items across {len(strata_counts)} strata; "
          f"{N_REVIEWERS} blinded forms -> {OUT}")
    print(json.dumps(strata_counts, indent=1))


if __name__ == "__main__":
    main()
