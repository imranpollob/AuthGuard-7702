# Adaptive Adversarial Bytecode Attack Protocol

This protocol is frozen before adaptive-attack results. The first-STOP verdict is final: it is
an empirical shortcut warning only and is not an attack target, defense, canonicalizer, or main
contribution.

## Target and split

The target is the full 773-feature AuthGuard XGBoost model. For each frozen outer family fold,
the model and threshold are learned from the other four folds; the threshold uses inner
family-grouped OOF predictions. Attacks operate only on malicious rows in the held-out fold.
No test candidate is used for fitting or threshold selection.

Transfer is measured without retuning the candidate against:

1. full AuthGuard with model seed 7703; and
2. the strongest same-host histogram plus hashed-n-gram XGBoost baseline.

Both transfer models receive their own training-only OOF thresholds.

## Valid action space

Candidate sequences may combine each action at most once, with at most one flooding level:

- rewrite recognized/appended metadata;
- rewrite width-preserving `PUSH20` address immediates;
- rewrite sensitive width-preserving `PUSH4` selector immediates;
- append a `STOP`-guarded neutral opcode region;
- append donor-isolated flooding at 25%, 50%, 100%, or 200% of source size.

Candidates must be even-length hex, remain within nominal +200% byte overhead (the single
`STOP` guard byte is exempt), and preserve the original pre-metadata opcode-token sequence.
Donor selection is partition-isolated and label-independent;
every copied segment is recorded. Opcode-token validity is not behavioral equivalence. Address
and selector rewriting are expected to change some observed executions and are reported
separately by bounded execution tests.

## Attacks and comparators

- Fixed one-query comparators: M1, M2, M3, F25, F50, F100, F200.
- Random-flood oracle: best of F25/F50/F100/F200, charged four queries.
- Fixed-transform oracle: best of all seven fixed comparators, charged seven queries.
- Random search: up to 64 unique valid sequence queries, deterministic per source.
- Model-guided beam search: beam width four, depth at most four, and the same 64-query budget.

The clean source is a zero-query no-op candidate, so an adaptive attack never reports a worse
score merely because every queried candidate increased risk.

## Metrics

For each method:

- attack success rate (ASR) among malicious sources correctly detected before attack;
- unconditional evasion rate;
- mean/median target-score reduction;
- total queries and queries to first successful evasion;
- mean/p95 bytecode overhead;
- transfer ASR and transfer score reduction for both transfer models;
- syntactic-validity rate; and
- bounded execution-fingerprint preservation on the ten previously selected delegates and their
  fixed 100-call suite.

Uncertainty uses 10,000 family-clustered bootstrap replicates. Primary adaptive comparisons are
beam minus random search and beam minus the fixed-transform oracle at identical source rows.

## Contribution-2 decision rule

The adaptive framework is a separate contribution only if all hold:

1. random or beam search improves ASR over the fixed-transform oracle by at least 0.05 and its
   family-clustered 95% CI excludes zero;
2. beam search exceeds random search at the same query budget with a 95% CI excluding zero, or
   reaches statistically tied ASR with at least 25% lower successful-query cost;
3. target-crafted attacks transfer with ASR at least 0.20 to at least one transfer model; and
4. candidate validity is 100%, with raw bounded execution-preservation reported rather than
   presumed.

Failure does not erase the benchmark. It changes contribution selection: the framework can be
merged with transformation-consistent training, while the dependence-aware EIP-7702 benchmark
and evaluation protocol becomes the third contribution.
