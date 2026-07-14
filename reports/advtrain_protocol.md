# Adversarial-Training Robustness — FROZEN PROTOCOL

**Frozen (UTC):** 2026-07-14T21:20:34Z
**Status:** Pre-registered. Written and hashed BEFORE training or inspecting any outcome. No
criterion below may change after seeing results. Recovery, partial recovery, a
robustness–accuracy trade-off, or no recovery are all valid outcomes and will be reported plainly.

## Research question
Does mutation-augmented training make AuthGuard more robust to structure-preserving bytecode
manipulation WITHOUT (1) materially reducing clean family-held-out performance, (2) learning the
shortcut "padded bytecode ⇒ malicious," or (3) overfitting to the exact augmentation conditions?

## Terminology (strict)
Prior verification established **opcode-skeleton / control-flow identity** for the generated
variants, NOT full EVM semantic equivalence. We therefore say **structure-preserving mutation**
and **attack-capability-preserving mutation**, never "semantics-preserving." **Held-out mutation
condition** (M3) and **held-out mutation severity** (+200%) test extrapolation beyond the
training augmentation recipe; they do NOT prove robustness to arbitrary unseen attacks.

## Reused frozen artifacts (unchanged)
`family_assignment_frozen.csv`; `pipeline/ag_common.py` (disassembler/preprocessing);
`pipeline/ag_features.py` (feature extraction, dense 261 + n-gram 512); the mutation harness
`pipeline/04_mutations.py` (`make_mutant` for M1/M2/M3, `mut_deadcode_append` for flooding);
AuthGuard-M0 hyperparameters (XGBoost: n_estimators=300, max_depth=6, learning_rate=0.1,
subsample=0.9, colsample_bytree=0.8, tree_method=hist, seed=7702); the opcode-histogram RF and
XGBoost baselines; the frozen GroupKFold(5) family folds on the primary task. Mutations and
family assignments are NOT redefined.

## Condition definitions (composed from the reused primitives)
All conditions transform an M0 source `x` (address `a`) with a domain-tagged RNG seed:
- **M0** = `x`
- **M1** = `make_mutant(x,a,"M1")` (metadata-trailer rewrite)
- **M2** = `make_mutant(x,a,"M2")` (+ PUSH20 address-immediate randomization + 20% appended dead-code)
- **M3** = `make_mutant(x,a,"M3")` (M2 + sensitive PUSH4 selector rewrite) — **HELD-OUT**
- **F25/F50/F100** = `mut_deadcode_append(x, a, 0.25/0.50/1.00)` — pure M0 + X% unreachable dead-code
- **F200** = `mut_deadcode_append(x, a, 2.00)` — **HELD-OUT severity**

Rationale for the flooding axis being pure-M0-based (not M3+pad): defining "+X% flooding" on
top of M3 would embed the held-out selector rewrite into the *seen* flooding conditions, leaking
M3. Pure-M0 flooding keeps M3 and +200% cleanly held out. (This differs from the original paper's
sweep, which measured M3+flood; internal M0-model-vs-aug-model comparisons here are valid because
both are evaluated on the identical condition set.)

### T1.1 Seen training-augmentation conditions
{M0, M1, M2, F25, F50, F100}. **M3 and F200 are NOT used in augmentation training.**
Training variants use RNG domain `"train"`; test variants use domain `"test"` (independent seeds).

### T1.2 Held-out evaluation conditions
{M3, F200}. Described as held-out mutation **condition** / **severity**, not novel attack types.

### T1.3 Symmetric augmentation
The identical augmentation mechanism and volume distribution are applied to malicious AND benign
(benign_cleared) training contracts. Per-class variant counts per condition are reported
(`advtrain_training_composition.csv`). This is required to block the "padding ⇒ malicious" shortcut.

### T1.4 Source-contract-balanced weighting
Each source contract contributes exactly 1.0 total training weight: for a source with M0 + K
generated variants, each of the (K+1) instances gets weight `1/(K+1)`. Contracts with more
variants get no extra influence. Class weighting (if any) is applied AFTER source balancing; the
original AuthGuard-M0 used no explicit class weight (`scale_pos_weight=1`), so AuthGuard-aug also
uses none, keeping estimator hyperparameters identical — the only differences are the training
DATA (augmented variants) and the source-balancing sample weights. Effective weighted class
totals are reported. AuthGuard-M0 (and the non-aug baselines) train on M0 only at weight 1.0/source.

### T1.5 Threshold selection
Per fold and model: threshold = the max-F1 point (the original paper's objective) on **clean-M0,
family-grouped VALIDATION data drawn from the training portion only** (validation = the next
frozen fold; family-disjoint from both train-fit and test). One threshold is frozen per fold/model
and applied UNCHANGED to every clean and mutated test condition. Never per-tier, per-volume, or
test-derived. Recorded in `advtrain_thresholds.csv`.

### T1.6 Evaluation sets
All models are evaluated on the same held-out test families (the frozen fold). For every mutation
condition, BOTH malicious and benign test contracts are transformed, so every adversarial
evaluation contains paired transformed malicious + benign samples. Retained malicious recall is
NEVER reported without the corresponding benign false-positive rate.

## Fold structure (family-disjoint, reuses frozen folds)
GroupKFold(5) on `family_id`, primary task (malicious 793 vs benign_cleared 1,657). For test fold
`f`: **test** = fold `f`; **validation** = fold `(f+1) mod 5` (threshold only, clean M0);
**train-fit** = the remaining 3 folds (augmented). All family-disjoint.

## Leakage assertions (saved to `advtrain_leakage_assertions.txt`)
1. no source-contract overlap across train/val/test; 2. no frozen-family overlap across
train/val/test; 3. no mutation-instance overlap across train/test; 4. no bytecode-hash overlap
across train/test variants; 5. every mutant inherits its source's frozen `family_id`.

## Models (exact names)
`opcode-histogram RF`, `opcode-histogram XGBoost`, `opcode-histogram XGBoost-aug`,
`AuthGuard-M0`, `AuthGuard-aug`. `-aug` models train on the augmented train-fit with source
weights; non-aug models train on M0 train-fit only. `opcode-histogram XGBoost-aug` uses the SAME
augmentation data as `AuthGuard-aug` (isolates representation vs. mere padding exposure). All
share AuthGuard-M0's frozen XGBoost hyperparameters (RF: n_estimators=300, seed 7702).

## Metrics & statistics
Per condition per model: AUPRC, AUROC, precision, recall, F1, false-positive rate, retained
malicious detection (recall relative to M0), benign transformed-contract flag rate. Reported as
mean ± std and every fold value. Paired analysis (same contracts): fold-level paired differences
and paired bootstrap 95% CIs for AuthGuard-M0 vs AuthGuard-aug; Wilson intervals for proportions.
No superiority claim from overlapping point estimates alone.

## Verdict vocabulary
Exactly one of **RECOVERS AND GENERALIZES** / **PARTIALLY RECOVERS** / **DOES NOT RECOVER**,
citing: clean AUPRC delta, held-out M3, held-out +200%, benign +200% FPR, and the comparison with
`opcode-histogram XGBoost-aug`. Separately state whether evidence supports robustness to the
trained recipe, extrapolation to held-out severity/condition, or neither. No claim of robustness
to arbitrary adversarial transformations.
