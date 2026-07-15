# Claim Plan

## Claim discipline

The paper should claim an implemented bytecode-scoring prototype and rigorous evaluation, not a novel classifier or complete wallet product. Every maliciousness claim is scoped to USENIX-artifact positives versus rule-silent weak negatives unless explicitly described as an exploratory independent case.

Do not use “first,” “novel,” or “state of the art” until a current, documented literature audit supports the exact wording. The contribution sentences below intentionally avoid priority claims.

## Proposed contribution sentences

1. **Practical scorer.** We present AuthGuard-7702, an implemented bytecode-only, decompiler-free risk-scoring prototype for screening EIP-7702 delegate code before authorization; it separates USENIX-artifact positives from rule-silent delegates at 0.856 AUPRC under five-fold family-grouped evaluation, while local feature extraction plus prediction averages 3.37 ms per contract.

2. **Leakage-resistant evaluation.** We freeze a deterministic global similarity grouping of 3,258 contracts into 1,329 families and show that a random split inflates AuthGuard AUPRC from 0.856 to 0.961, while an exact-hash blocklist rises from 0.324 to 0.558, exposing memorization that family-grouped testing removes.

3. **Evasion and augmentation.** We provide a structure-preserving M0--M3 evasion benchmark and a source-balanced, family-disjoint augmentation procedure that, under the stricter G-ADV protocol, improves held-out pure-M0 +200% flooding recall from 0.624 to 0.790 and AUPRC from 0.596 to 0.750 while reducing benign FPR from 0.314 to 0.275, with a small clean-recall reduction disclosed.

## Core claim matrix

| ID | Safe claim | Evidence | Required qualification | Section/float |
|---|---|---|---|---|
| C1 | AuthGuard is an implemented bytecode scorer for a pre-signing decision point | feature/training/prediction code; G-DET; local runtime | scorer core only; no wallet/RPC path implemented or timed | Design, RQ1, runtime sentence |
| C2 | AuthGuard reaches 0.856 ± 0.043 AUPRC under family-grouped evaluation | G-DET JSON | target is rule-derived positives vs weak rule-silent negatives; five outer folds | Table 2 |
| C3 | Random splitting inflates AuthGuard AUPRC by about 0.10 | G-DET family/random outputs | diagnostic on this dataset; do not generalize to all prior studies | Figure 2 |
| C4 | Frozen global grouping prevents identical cross-class code from being split by class | frozen CSV; 23 conflicting exact bytecodes | groups are MinHash-estimated opcode similarity clusters, not attacker attribution | Methodology/Table 1 |
| C5 | Sensitive selector rewriting reduces the sensitive-name approximation’s retained recall to zero at M3 | G-MUT | approximation only; full USENIX pipeline not run | Table 3 |
| C6 | AuthGuard retains 0.588 recall at M3 under G-MUT | G-MUT | in-sample training threshold; structure-preserving checker, not execution equivalence | Table 3 |
| C7 | The compound G-VOL +200% condition reduces AuthGuard retained recall to about 0.139 | G-VOL | separate M3-style compound condition; not the G-ADV F200 baseline | limitations only |
| C8 | G-ADV augmentation improves held-out pure-M0 +200% robustness | G-ADV fold means | F200 is a held-out severity generated from M0, not M3; residual FPR is high | Table 4/Figure 3 |
| C9 | G-ADV augmentation has a clean operating-point tradeoff | G-ADV and paired CSV | AUPRC/FPR improve while recall falls; never say “no clean cost” | Table 4/discussion |
| C10 | Independent generalization is unresolved | preregistered independent funnel | exactly one truly novel confirmed positive; INSUFFICIENT DATA | limitations |

## Wording required for baselines

Use exactly:

- **sensitive-name rule approximation**;
- **external-call structural over-approximation**;
- **full USENIX Gigahorse/Datalog pipeline** when discussing the unexecuted system.

Do not shorten the first two to “USENIX detector.” Do not claim AuthGuard beats the full pipeline.

## Mutation wording

Safe:

- “structure-preserving transformations under our opcode-skeleton checker”;
- “attack-capability-preserving by construction for the modeled redeployment parameters,” only when clearly presented as the threat-model assumption;
- “793/793 variants preserved the original pre-metadata opcode-token sequence.”

Unsafe:

- “semantics-preserving”;
- “behaviorally equivalent”;
- “formally verified”;
- “control-flow equivalent” without qualification;
- “robust to arbitrary evasion.”

## Statistical claim policy

- Main G-DET and G-ADV tables use fold means.
- Paired contract-level values may be used for direction and confusion counts.
- The current +200% interval [0.131, 0.193] is not family-clustered. Do not call it leakage-safe statistical confidence in the final paper until the bootstrap resamples frozen families.
- If a family-clustered interval is not produced, omit the interval and report fold means plus family-macro/singleton results.
- State aggregation whenever pooled values differ from fold means.

## Runtime claim policy

Safe: “On the local evaluation environment, feature extraction plus model prediction averaged 3.37 ms per contract (p95 10.67 ms; n=300).”

Required additions before submission: hardware/OS and dependency versions.

Unsafe:

- “end-to-end wallet latency”;
- “complete pre-signing latency”;
- “network-inclusive latency”;
- “N× faster than Gigahorse”;
- “real-time” without defining the boundary.

## Claims to omit from the main paper

- AuthGuard discovers malicious families missed by the positive-label rule.
- AuthGuard generalizes to independently sourced malicious delegates at scale.
- AuthGuard is superior to the full USENIX system.
- The external-call structural over-approximation is a useful detector merely because recall is 1.0.
- `benign_cleared` is clean or verified benign.
- The 8.1% heuristic is the true contamination rate.
- Augmentation recovered the G-VOL 0.139 compound worst case.
- Augmentation has no clean cost.
- The classifier architecture is a research novelty.
- The system includes a deployed wallet warning UI, network fetch path, or user study.
- The explanation/nearest-family component is a validated production explanation system.
- Any “first,” “novel,” or “state-of-the-art” wording without a completed literature matrix.

## Abstract-safe numeric set

Use at most these numbers:

- G-DET family/random AUPRC: 0.856 / 0.961.
- G-ADV pure-M0 +200% recall: 0.624 → 0.790.
- G-ADV pure-M0 +200% AUPRC: 0.596 → 0.750.
- Local scorer-core mean: 3.37 ms, if runtime provenance is completed.

If space is tight, omit latency from the abstract before omitting the clean-recall qualification.

## Proposed title

**AuthGuard-7702: Family-Grouped, Evasion-Aware Bytecode Risk Screening Before EIP-7702 Authorization**

This title is anonymous, avoids priority/model-novelty claims, and foregrounds the tool decision point plus the two strongest methodological contributions.
