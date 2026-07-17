# First-STOP Contribution Decision

Date: 2026-07-16  
Protocol: `revision_v2/protocols/first_stop_audit_protocol.md`  
Primary result: `revision_v2/results/first_stop_audit/first_stop_audit_results.json`

## Verdict

**Useful heuristic only.**

First-STOP is a strong corpus-level risk-screening representation, and its performance is not
explained by the tested length, suffix, exact-duplicate, frozen-family, or chain controls.
However, it is not an executable-bytecode canonicalization: code after the first linear-sweep
`STOP` is statically reachable in every malicious row, is executed by 92 of 100 bounded test
calls, and truncation preserves the observed execution fingerprint in only 22 of those calls.

The conservative reachability extractor passes the bounded semantic check but fails the frozen
predictive non-inferiority criterion. It is therefore not retained as an ICTAI contribution in
this revision.

## Questions and answers

### Is the first `STOP` an execution boundary?

No. A linear sweep confuses a dispatcher branch's early `STOP` with a whole-program terminal.
EVM control flow can jump to later `JUMPDEST` blocks.

- All 727 malicious rows have statically reachable instructions after their first `STOP`.
- 1,382/1,553 benign-cleared rows (89.0%) and 649/797 benign-general rows (81.4%) also have
  statically reachable post-STOP instructions.
- All 10 previously selected execution-validation delegates have statically and dynamically
  reachable post-STOP code.
- 92/100 fixed-calldata traces execute a program counter after the first `STOP`.
- Actual first-STOP truncation preserves the bounded fingerprint for 22/100 calls and for
  0/10 contracts across all their tested calls.

Therefore “executable prefix,” “reachable prefix,” “canonical executable bytecode,” and
“semantics-preserving truncation” are unsupported descriptions.

### Is the predictive result merely length or suffix leakage?

Not under the predefined controls. First-STOP's pooled family-held-out AUPRC is 0.966. The
length/STOP-only model reaches 0.768 and the suffix-only model 0.755. Existing feature ablations
also retain first-STOP performance after removing explicit length and metadata features:
five-fold mean AUPRC is 0.968 without length and 0.967 without length/metadata, versus 0.970 for
the complete first-STOP feature set.

The advantage also survives dependence controls:

| control | full bytecode | first-STOP |
|---|---:|---:|
| Observation-weighted pooled AUPRC | 0.869 | **0.966** |
| Inverse-family AUPRC | 0.839 | **0.955** |
| One vote per exact bytecode | 0.842 | **0.958** |
| Exact-singleton-only AUPRC | 0.817 | **0.952** |
| Strict leave-one-chain-out macro AUPRC | 0.840 | **0.963** |

The cross-chain arm holds out each of seven labeled chains and removes from training every
family and exact bytecode present on the held-out chain. First-STOP AUPRC ranges from 0.925 to
0.999 across these chain tests. The corpus has no timestamp, collection date, block height, or
equivalent field, so a temporal holdout is unavailable and was not synthesized from row order.

These results reject the protocol's **dataset shortcut** verdict as defined: neither the suffix
nor length/offset statistics reproduce most of the signal, and strict dependence/domain controls
do not collapse the result. They do not prove freedom from every artifact of the single positive
source or weak-negative construction. External temporal and independently labeled validation
remain necessary.

## Predictive comparison

All models below use the same frozen outer folds, inner family-grouped OOF threshold selection,
and XGBoost learner. Values are five-fold means; bootstrap differences use pooled held-out rows.

| representation | AUPRC | recall | FPR | benign-general FPR |
|---|---:|---:|---:|---:|
| Full bytecode | 0.885 | 0.770 | 0.106 | 0.058 |
| Metadata stripped | 0.874 | 0.813 | 0.103 | 0.068 |
| **First-STOP** | **0.970** | **0.972** | **0.029** | **0.026** |
| Suffix only | 0.769 | 0.799 | 0.174 | 0.146 |
| Length/STOP only | 0.771 | 0.802 | 0.185 | 0.302 |
| Conservative reachable code | 0.862 | 0.802 | 0.117 | 0.072 |

First-STOP minus full pooled AUPRC is +0.098 with family-clustered 95% CI
[+0.053, +0.152]. This is a within-corpus representation result, not an unsupported general
model-superiority claim.

## Transformation stress

The stress arm transforms both classes after splitting and uses partition-isolated benign donor
pools. The ledger contains 14,361 copied segments with disjoint train/validation/test family and
executable-hash pools.

| representation | M3 AUPRC / recall / FPR | F200 AUPRC / recall / FPR | M3+F200 AUPRC / recall / FPR |
|---|---:|---:|---:|
| Full | .820 / .743 / .111 | .594 / .364 / .089 | .567 / .335 / .094 |
| First-STOP | **.970 / .972 / .031** | **.970 / .972 / .030** | **.970 / .972 / .031** |
| Reachable code | .824 / .762 / .123 | .589 / .396 / .123 | .584 / .407 / .115 |

First-STOP invariance is expected because the tested transformations largely modify metadata,
selected immediates, or append bytes outside the retained prefix. It demonstrates invariance to
this benchmark, not semantic robustness. An adaptive attacker that edits dispatcher/prefix bytes
is required before treating the heuristic as adversarially robust.

## Conservative canonicalizer decision

The implemented extractor:

- decodes instruction boundaries and basic blocks;
- follows fall-through and directly resolvable `PUSHn` to `JUMP`/`JUMPI` edges;
- retains every `JUMPDEST` region when a reachable jump is unresolved;
- disables executable pruning when reachable `CODESIZE` or `CODECOPY` can observe code as data;
- recognizes only the established narrow Solidity-style CBOR trailer;
- records every removed range and its uncertainty; and
- distinguishes compact feature bytes from the same-offset masked form used for execution tests.

Its predefined contribution criteria resolve as follows:

| criterion | result | decision |
|---|---|---|
| Same-offset bounded execution preservation | 100/100 calls; 10/10 contracts; no tested call entered a removed CFG range | Pass, bounded only |
| Family AUPRC non-inferiority to full, CI lower bound >= -0.01 | pooled delta -0.015, 95% CI [-0.043, +0.013] | **Fail** |
| F200 or M3+F200 recall improvement >= 0.05 | +0.032 at F200; +0.072 at M3+F200 | Pass only on compound arm |
| Benign-general FPR increase <= 0.02 | 0.072 vs 0.058, delta +0.014 | Pass |
| Domain controls support retention | cross-chain macro AUPRC 0.837 vs 0.840, but FPR 0.151 vs 0.118 | Not supportive |

Because all criteria were required, conservative canonicalization fails contribution selection.
The bounded execution result remains useful engineering evidence, but it does not compensate for
the predictive and operating-point degradation.

Metadata stripping is behavior-preserving on the same bounded 100-call suite and is statistically
tied with full bytecode (pooled AUPRC delta -0.005, 95% CI [-0.020, +0.012]). It is acceptable as
ordinary preprocessing, not as a standalone scientific contribution.

## Contribution consequence

The provisional contribution path is therefore the requested fallback:

1. AuthGuard-7702 pre-authorization screening tool;
2. adaptive model-guided adversarial attack framework; and
3. transformation-consistent/source-balanced adversarial training.

First-STOP may be retained as an explicitly non-semantic diagnostic or auxiliary screening
heuristic. It must not be named executable-bytecode canonicalization, used to claim behavioral
preservation, or presented as robust before prefix-targeting adaptive attacks are evaluated.

`revision_v2/reports/final_contribution_decision.md` remains deferred until the adaptive attack
and training experiments are complete. The manuscript remains unchanged.

## Reproducibility and evidence

- Protocol: `revision_v2/protocols/first_stop_audit_protocol.md`
- Canonicalizer: `revision_v2/experiments/first_stop_audit/canonicalizer.py`
- Main runner: `revision_v2/experiments/first_stop_audit/run_first_stop_audit.py`
- Execution runner: `revision_v2/experiments/first_stop_audit/run_execution_audit.py`
- Aggregate results: `revision_v2/results/first_stop_audit/first_stop_audit_results.json`
- Static per-row audit: `revision_v2/results/first_stop_audit/static_reachability_per_row.csv.gz`
- Dynamic per-call audit: `revision_v2/results/first_stop_audit/execution_audit_per_call.csv`
- Primary, benign, robustness, and cross-chain scores: corresponding files under
  `revision_v2/results/first_stop_audit/`
- Donor provenance: `revision_v2/results/first_stop_audit/donor_ledger.csv.gz`
- Run log: `revision_v2/logs/first_stop_audit.log`
- Frozen guard: 144/144 files unchanged before and after the run

