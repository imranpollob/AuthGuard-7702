#!/usr/bin/env python3
"""Phase 2A — deterministic known-conflict escalation rule evaluation.

Rule: if a test contract's exact normalized-bytecode hash is in the frozen 23-group conflict
set, abstain/escalate (do not auto-decide). Because the primary corpus already quarantines
those rows, we measure the rule on the FULL retained + quarantined population to show what
fraction it would escalate and whether it concentrates known-ambiguous cases, without
restoring quarantined rows to training. Also reports the before/after-quarantine sensitivity
(v1 original-cohort vs task-aligned) already documented, as a pointer.
"""
import hashlib
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import load_corpus, RV2, ROOT, DH, SEED  # noqa: E402

OUT = os.path.join(RV2, "results", "conflicts")


def main():
    df, _, _, _ = load_corpus()
    conflict = pd.read_csv(os.path.join(DH, "conflicting_bytecodes.csv"))
    conflict_hashes = set(conflict["normalized_bytecode_sha256"])

    # retained corpus hashes
    df["h"] = df["bc"].map(lambda b: hashlib.sha256(b.encode()).hexdigest())
    retained_conflict = df["h"].isin(conflict_hashes).sum()

    # full original cohort for the escalation-coverage view
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    from ag_common import normalize_bytecode
    cap["h"] = cap["bytecode"].map(lambda b: hashlib.sha256(normalize_bytecode(b).encode()).hexdigest())
    orig_conflict_rows = int(cap["h"].isin(conflict_hashes).sum())

    out = dict(
        conflict_groups=int(conflict["normalized_bytecode_sha256"].nunique()),
        conflict_rows_original=orig_conflict_rows,
        conflict_rows_in_retained_corpus=int(retained_conflict),
        escalation_rule="escalate if exact bytecode hash in frozen conflict set",
        retained_corpus_escalation_rate=float(retained_conflict / len(df)),
        interpretation=(
            "All 23 conflicting exact-bytecode groups are already quarantined from the primary "
            "task, so the retained corpus contains 0 of them; the deterministic known-conflict "
            "escalation rule therefore escalates 0% of retained decisions while, by construction, "
            "routing 100% of the known-ambiguous exact bytecodes to human/deeper analysis. This "
            "rule is a zero-false-abstention safety net for previously-seen conflicts; it does "
            "not generalize to unseen ambiguous bytecodes (that is Gate B's role)."),
        before_after_quarantine_sensitivity_pointer=(
            "paper_build/data_hygiene/original_vs_task_aligned.md and revision_v2 G-DET v2 vs "
            "frozen v1: AuthGuard family AUPRC 0.856 (pre-quarantine original cohort) -> 0.881 "
            "(post-quarantine task-aligned); quarantine did not inflate the headline."))
    with open(os.path.join(OUT, "abstention_eval.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
