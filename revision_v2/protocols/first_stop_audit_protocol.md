# First-STOP and Conservative Canonicalization Audit Protocol

This protocol was written before the new audit outputs. Existing frozen Revision-v1 artifacts,
stored folds, labels, and family assignments remain read-only.

## Representations

The audit compares the same XGBoost learner on:

1. full normalized runtime bytecode;
2. full runtime with only narrowly recognized Solidity-style CBOR metadata removed;
3. the PUSH-aware prefix through the first linear-sweep `STOP`;
4. the pre-metadata suffix strictly after that `STOP`;
5. length/STOP-location statistics only; and
6. conservative reachable-code extraction.

The conservative extractor decodes instruction boundaries and basic blocks, follows fall-through
and directly resolvable `PUSHn` to `JUMP`/`JUMPI` edges, and treats each reachable unresolved
jump as capable of reaching every `JUMPDEST`. If reachable code contains `CODESIZE` or
`CODECOPY`, it retains the entire executable region because nominally unreachable bytes may be
observed as code data. It records removed ranges and uncertainty. Its compact form is a feature
representation, not deployable bytecode; a same-offset masked form is used in bounded execution
tests.

## Evaluation controls

- Primary: the frozen five leave-family-out folds and inner family-grouped OOF thresholds.
- Duplicate controls: observation-weighted, inverse-family-weighted, one-vote-per-exact-bytecode,
  and exact-singleton-only AUPRC.
- Secondary benign control: `benign_general` FPR under each outer-fold model/threshold.
- Cross-chain: leave one of the seven labeled chains out, removing from training every family
  and exact bytecode also present on the held-out chain. The corpus has no date, timestamp, or
  block-height field, so temporal holdout is unavailable rather than reconstructed indirectly.
- Robustness: held-out positives under donor-isolated M1, M2, M3, F200, and M3+F200 using the
  clean-model threshold.
- Uncertainty: 10,000-replicate paired family-clustered bootstrap for pooled AUPRC differences
  against the full representation.
- Semantic audit: static post-first-STOP reachability for all rows and bounded Anvil traces on
  the ten previously selected execution-validation delegates and their fixed calldata suites.

## Decision rules

`valid canonicalization contribution` requires all of the following:

- no unexpected fingerprint divergence for conservative same-offset masking on the bounded
  execution suite;
- family AUPRC is non-inferior to full bytecode (paired 95% CI lower bound at least -0.01);
- F200 or M3+F200 recall improves by at least 0.05 without clean benign-general FPR increasing
  by more than 0.02; and
- cross-chain and duplicate controls do not reverse the representation's main conclusion.

`useful heuristic only` applies when first-STOP improves predictive robustness but static or
dynamic evidence shows the removed suffix cannot be conservatively declared irrelevant.

`dataset shortcut` applies when most discrimination is reproduced by suffix-only or
length/STOP-only features, or when the first-STOP advantage materially collapses under strict
family, duplicate, or cross-chain controls.

`inconclusive` applies when the available corpus/trace coverage cannot distinguish these cases.

These rules govern contribution selection; they do not resurrect Gate A or Gate B and do not
authorize a model-superiority claim.

