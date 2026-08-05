# AuthGuard-7702 Submission Blueprint

Status date: 2026-08-04  
Evidence state: method and predictions frozen; independent post-cutoff labels absent.  
Use: authoritative manuscript plan after the multi-path research search. Do not copy bracketed
fields into a submission until the referenced artifact exists.

## Paper identity

Working title: **AuthGuard-7702: Coverage-Audited Delegation-Context Analysis for
Pre-Authorization Screening**

One-sentence paper claim:

> AuthGuard-7702 studies whether delegate runtime bytecode can prioritize EIP-7702 authorization
> requests for warning or deeper review before behavioral history is required, using a guard-aware
> representation whose incomplete analysis explicitly defers.

Never shorten this to malicious-contract detection, safety certification, formal verification,
wallet protection, or production readiness.

## Three contribution paragraphs

### C1: Evaluation resource

We define a bytecode-only EIP-7702 pre-authorization screening task and release a leakage-reduced,
temporally separated evaluation resource. It distinguishes exact runtimes, conservative research
families, development labels, untouched dual-reviewed labels, provenance exclusions, and a locked
replication reserve. Ambiguous or non-screenable cases remain reported outcomes rather than forced
binary labels.

Evidence required before final wording: complete 150-item release; two independent primary reviews
per item; adjudication of every disagreement; raw agreement; Cohen's kappa when defined; final class
and exclusion counts. Describe anonymous family clusters as conservative retraining holds, never as
verified project identities or proof of leakage freedom.

### C2: Coverage-audited DCRG

We introduce a guard-aware Delegation-Context representation for delegate execution. It connects
reachable value movement, arbitrary calls, storage changes, approvals, and creation capabilities to
recognized self-call, signature, stored-authority, fixed-address, EntryPoint, caller-supplied, and
`tx.origin` evidence. The bounded extractor reports `COMPLETE` or `PARTIAL` coverage; unresolved
control flow is not converted into absence of risk. The final XGBoost classifier consumes aggregate
features derived from this representation—it is not a learned GNN and does not learn graph topology.

Strong method wording is permitted only if the preregistered full-DCRG minus untyped-guard AUPRC
interval has lower bound above zero on untouched labels. Otherwise retain DCRG as an auditable task
representation and present typed-guard superiority as unsupported.

### C3: Warning-and-deferral evaluation

We evaluate a deployment-realistic three-way decision contract: `WARN`, `NO_MODEL_WARNING`, and
`DEFER`. Thresholds come from held-out canonical validation data; incomplete analysis or seed
instability can defer. `NO_MODEL_WARNING` means only that the frozen warning criterion was not met
under complete bounded analysis. It is not `SAFE`, low risk, legitimacy, or authorization advice.

Evidence includes post-cutoff authority/delegate pairs, project/family-held retraining, strongest
learned and classical baselines, calibration, coverage/deferral, and a separately preregistered
three-project legitimate-control case study. The latter is descriptive because n=3.

## Novelty boundary against current work

The paper must cite Huang et al., *Revealing the Dark Side of Smart Accounts* (USENIX Security
2026) as the closest EIP-7702 security study. It combines historical transaction filtering,
Gigahorse decompilation, and cross-contract static rules to identify EOA-targeted,
contract-targeted, and composite attacks. It rules out claims to the first EIP-7702 detector,
first bytecode analysis, first cross-chain study, or first attack taxonomy.

Qi et al., *EIP-7702 Phishing Attack* (arXiv:2512.12174), measures authorization and execution
events, persistent-delegation phishing, trigger pathways, ERC-4337 activation, and contract-family
concentration. It rules out first-measurement, first-phishing, and first-ERC-4337-connection claims.

De Rosa et al., *PhishingHook* (DSN 2025), already compare 16 EVM-bytecode model families for
generic phishing-contract detection before interaction. It rules out first bytecode-phishing and
first opcode-model-comparison claims. Its different task and labels make published accuracy
non-comparable; the fair response is the frozen same-split histogram+n-gram and learned-sequence
baselines, not a cross-dataset metric comparison.

The differentiator is the complete conjunction below:

> score-blind bytecode-only screening at the authorization decision before behavioral history is
> required, with analysis-coverage auditing, dependence-aware evaluation, and explicit deferral.

Avoid a “first” claim unless the final bibliography search finds no direct predecessor and the same
sentence includes that entire scope.

## Manuscript structure and evidence map

### 1. Introduction

1. Explain the authorization-time decision: the wallet knows the delegate address/runtime before
   authorizing it, but history, reputation, verified source, and transaction effects may be absent.
2. Motivate warning triage using the EIP-7702 specification's delegate-security pitfalls.
3. Contrast the task with transaction/cross-contract forensic detection.
4. State the three bounded contributions above.
5. State immediately that the output is advisory and incomplete analysis defers.

### 2. Background and related work

- EIP-7702 execution and authority semantics.
- Huang et al. and Qi et al. as direct EIP-7702 work.
- PhishingHook as the closest bytecode-phishing learning study and the reason published metrics are
  not compared across different labels/populations.
- Generic bytecode sequence, CFG/data-flow, contract-graph, and cross-contract detection.
- Selective prediction/reject options as established techniques.
- Legitimate smart-account implementations as external operating cases, not negative ground truth
  for binary accuracy.

### 3. Task, threat model, and labels

- Input: proposed delegate runtime bytecode; optional recovered authority only in the real-context
  evaluation.
- Positive: a concrete authorization-relevant unsafe capability or condition supported by evidence.
- Bounded negative: no concrete unsafe behavior found under the review evidence; never “safe.”
- `INDETERMINATE` and `NOT_BYTECODE_SCREENABLE`: always reported; excluded from binary metrics.
- Out of scope: UI deception independent of code, private-key compromise, unobservable dynamic
  state, and downstream transaction-specific effects that require simulation/history.
- Human procedure: qualifications, separate calibration, blind R1/R2 review, R3 adjudication,
  evidence sources, agreement, conflicts, and immutable submissions.

### 4. DCRG and bounded extraction

- Entry/capability/guard/coverage concepts and fixed aggregate feature groups.
- Authority-relative semantics and why transaction sender cannot substitute for recovered signer.
- Jump-fenced metadata recognition and conservative loop-state widening.
- Soundness boundary: bounded, coverage-observable analysis—not full EVM semantics.
- Coverage correction result: COMPLETE unique-runtime coverage 517/1,665 to 1,063/1,665, with zero
  COMPLETE-to-PARTIAL regressions and inherited-label AUPRC delta -0.00034, 95% CI
  [-0.00617, 0.00423]. This is analyzer-validity evidence, not a performance gain.

### 5. Experimental protocol

- Development corpus and label circularity.
- Score-blind 150-item primary post-cutoff sample, one predeclared exclusion, and locked 150-item
  reserve.
- Conservative research-family/dependence holds and the “leakage-reduced, not leakage-free” claim.
- Seven fixed model variants over three seeds: sequence+dense, histogram+n-gram XGBoost,
  capability-only, untyped guards, actor-removed, full DCRG, and project-balanced DCRG.
- Label-blind seed-consensus decisions frozen before review: at least two warning votes yields
  `WARN`; one warning vote, incomplete coverage, or missing authority yields `DEFER`; otherwise the
  result is `NO_MODEL_WARNING`. The supplemental decision analysis is descriptive and does not
  alter the preregistered AUPRC endpoint.
- Single confirmatory endpoint: mean-seed AUPRC(full DCRG) minus AUPRC(untyped guards), 10,000 paired
  dependence-cluster bootstrap replicates.
- Secondary comparisons, calibration, decision counts, coverage, and error taxonomy are descriptive
  unless their own paired intervals are reported.
- Separate external-control protocol and its project/runtime/lineage distinctions.

### 6. Results

Populate the following tables mechanically from generated artifacts.

#### Table 1: populations and provenance

| Population | Items | Labels available | Independence/hold status | Role |
|---|---:|---|---|---|
| Canonical development | 2,190 rows / 1,665 runtimes | inherited source rule | stored family folds | engineering/training |
| Gold-Test proxy | 150 | provisional; 108 binary | method-selection data | planning diagnostic |
| Post-cutoff primary | 150; 149 score-eligible | `[FINAL COUNTS]` | conservative holds; frozen predictions | confirmatory |
| Replication reserve | 150 | untouched | disjoint locked reserve | replication/replacement only |
| New legitimate projects | 3 | documented operating cases | separate pre-scoring protocol | descriptive warnings |

#### Table 2: final model comparison

| Model | AUPRC | AUROC | Brier | ECE | Recall | Observed FPR | WARN / NO / DEFER |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sequence+dense | `[ARTIFACT]` | | | | | | |
| Histogram+n-gram XGBoost | `[ARTIFACT]` | | | | | | |
| Capability-only | `[ARTIFACT]` | | | | | | |
| Untyped guards | `[ARTIFACT]` | | | | | | |
| Full DCRG | `[ARTIFACT]` | | | | | | |
| Project-balanced DCRG | `[DESCRIPTIVE]` | | | | | | |

Always report binary prevalence beside AUPRC.

#### Table 3: paired contribution tests

| Contrast | Mean AUPRC delta | 95% paired cluster CI | Decision |
|---|---:|---:|---|
| Full DCRG - untyped guards | `[PRIMARY]` | `[PRIMARY]` | typed contribution supported/not supported |
| Full DCRG - histogram+n-gram | `[SECONDARY]` | `[SECONDARY]` | baseline superiority supported/not supported |
| Full DCRG - sequence+dense | `[SECONDARY]` | `[SECONDARY]` | baseline superiority supported/not supported |
| Full DCRG - capability-only | `[DESCRIPTIVE]` | `[DESCRIPTIVE]` | guard context supported/not supported |
| Full DCRG - actor-removed | `[DESCRIPTIVE]` | `[DESCRIPTIVE]` | actor features supported/not supported |

#### Table 4: external legitimate controls

| Project | New project | Canonical-unseen | Observed use | Coverage | Principal decision |
|---|---|---|---|---|---|
| Tangem | yes | yes | yes | COMPLETE | NO_MODEL_WARNING |
| Startale | yes | yes | not measured | PARTIAL | DEFER |
| Rainbow | yes | no; known framework lineage | yes | COMPLETE | NO_MODEL_WARNING |

Report 0 WARN / 2 NO_MODEL_WARNING / 1 DEFER for the principal frozen model. Do not calculate AUPRC,
AUROC, significance, or a population false-positive rate from an all-legitimate n=3 set.

#### Table 5: label quality and analysis boundary

Report R1/R2 marginals, raw agreement, Cohen's kappa when defined, disagreement/adjudication counts,
final label counts, indeterminate reasons, COMPLETE/PARTIAL counts, and decision counts by coverage.
Include a qualitative taxonomy of disagreements and model errors without changing the model.

### 7. Discussion

- What typed guards add or fail to add on untouched labels.
- Why high AUPRC under high positive prevalence is insufficient alone.
- False warnings and deferral on legitimate projects.
- Anonymous family clustering as conservative leakage control, not attribution.
- Negative paths: fusion not reliably better than DCRG, GNN futility stop, motif null, actor-feature
  null, failed low-risk tier, and failed first-`STOP` canonicalization.
- Deployment scope: extraction and inference measured separately; no wallet integration claim.

### 8. Limitations, ethics, and artifact

- Human judgment is evidence-bounded and not ground truth.
- Ethereum-only post-cutoff sample and partial temporal window.
- Bounded CFG/symbolic analysis; unresolved behavior defers.
- Small legitimate-project case study and one shared framework lineage.
- Source-rule training labels can still shape the learned boundary despite independent evaluation.
- Conservative similarity-based holds may overexclude yet cannot prove all project leakage absent.
- Public-chain data only; do not characterize named legitimate projects as secure.

## Result-contingent paper branches

### Branch A: method paper

Use only if the preregistered full-minus-untyped AUPRC interval has lower bound above zero.

Permitted abstract sentence:

> On 149 provenance-eligible post-cutoff delegates with `[N_BINARY]` adjudicated binary judgments,
> guard-aware DCRG changes mean AUPRC by `[DELTA]` relative to the type-erased ablation (95% paired
> dependence-cluster interval `[LOWER, UPPER]`).

Add baseline-superiority wording only for a comparator whose own paired interval excludes zero.
Do not say “beats all baselines” unless every named fair comparison supports that statement.

### Branch B: measurement paper

Use if the primary interval includes zero or points negative.

Permitted abstract sentence:

> On untouched post-cutoff judgments, typed guards did not yield a statistically resolved AUPRC
> improvement over type-erased guard evidence (`[DELTA]`, 95% paired interval `[LOWER, UPPER]`).
> The study nevertheless exposes `[COVERAGE]` bounded-analysis coverage, `[DEFER]` deferral, and
> `[ERROR TAXONOMY]`, establishing concrete limits for bytecode-only authorization screening.

Center C1, coverage correction, false-warning/deferral behavior, legitimate-control case study, and
negative results. Do not disguise this branch as a method win.

### Stop branch

Do not submit the current method claim if the final set has only one binary class, too few binary
items for stable paired analysis, missing dual reviews, unresolved disagreements, provenance-lock
failure, or evidence of label contamination. Use the locked reserve only under its predeclared rule
and document the reason before opening it.

## One-shot execution after review

From the repository root:

```bash
cd revision_v3/annotation_app
python3 export.py postcutoff
cd ../..
python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
  revision_v3/annotation_app/release_postcutoff.json postcutoff \
  --predictions revision_v3/results/postcutoff_retraining/postcutoff_predictions.csv.gz \
  --holdout-plan revision_v3/results/postcutoff_snapshot/postcutoff_family_holdout_plan.json \
  --training-manifest revision_v3/results/postcutoff_retraining/postcutoff_training_manifest.json \
  --sample-lock revision_v3/results/postcutoff_snapshot/postcutoff_review_lock.json \
  --agreement-report revision_v3/annotation_app/agreement_postcutoff.json
python3 revision_v3/experiments/human_label_evaluation/evaluate_frozen_postcutoff_decisions.py \
  revision_v3/annotation_app/release_postcutoff.json \
  --agreement revision_v3/annotation_app/agreement_postcutoff.json
```

Then run the submission-claim audit on the final LaTeX and build the PDF. No feature, threshold,
hold, exclusion, comparator, or endpoint may be changed after reading the labels.

## Final acceptance checklist

- [ ] Three real reviewer roster attestations and qualification descriptions.
- [ ] 300 independent primary judgments and all required R3 adjudications.
- [ ] Complete release and agreement report exactly matching the 150 frozen IDs.
- [ ] One-shot evaluation passes every source/prediction/hold/dependence lock.
- [ ] Supplemental operating evaluation passes its separately frozen decision/source/input locks.
- [ ] Abstract uses Branch A or B exactly as supported.
- [ ] Tables are generated from artifacts, with prevalence and uncertainty.
- [ ] Related work includes the USENIX 2026 and EIP-7702 phishing studies.
- [ ] External-control result remains descriptive.
- [ ] No `safe`, universal robustness, GNN, production, or global baseline-superiority claim.
- [ ] Final LaTeX claim audit has zero blockers.
- [ ] Final PDF is built and visually inspected.
