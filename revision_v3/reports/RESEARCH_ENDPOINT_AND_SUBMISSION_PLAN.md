# AuthGuard-7702 Research Endpoint and Submission Plan

Date: 2026-08-04
Status: method, project-family holds, retraining, and external controls are frozen; independent human labels remain incomplete.

## 2026-08-04 execution update (authoritative)

The score-blind preparation and model execution stages are complete. The primary set contains 150
items, of which one predeclared Ambire overlap is excluded and 149 were scored by three seeds. A
conservative, deliberately overinclusive family audit assigns the 148 anonymous nonexcluded items
to research clusters without asserting brand ownership; the retraining pipeline reports 146
mandatory canonical family holds and removes 607 canonical rows. This is a leakage-reduced design,
not proof of perfect project independence.

Locked retraining produced 21 checkpoints and 447 primary prediction rows. All protocol, source,
feature, hold-plan, checkpoint, and prediction provenance checks passed before annotation was
unlocked. Neither reviewer has submitted a post-cutoff label, so no final accuracy, AUPRC, AUROC,
calibration, or method-superiority result exists yet.

The separate, pre-scoring legitimate-control protocol is also complete. It contains three new
projects (Tangem, Startale, and Rainbow), two observed-use controls, and two canonical-unseen
controls. The frozen project-balanced model produced zero `WARN`, two `NO_MODEL_WARNING`, and one
`DEFER` across the three new projects. This is encouraging descriptive evidence only: the sample is
small, Startale has incomplete signer-relative coverage, and Rainbow shares a known runtime lineage
with a revision-v2 family. It is not an estimate of population false-positive rate or a safety
claim.

The sole remaining evidence-collection blocker is dual independent human review and adjudication.
The annotation gate is open, model scores remain hidden from reviewers, and both R1 and R2 have 150
pending assignments. Once those labels are frozen, the predeclared confirmatory evaluation can be
run once and the paper can take either the method-paper or measurement-paper branch below.

## 2026-08-04 final-freeze snapshot (historical)

The primary post-cutoff set is a score-blind sample of 150 exact-runtime families and remains
untouched: all 150 items are seeded in the annotation system and have zero annotation rows. It is
disjoint from the separate 150-item Gold-Test proxy whose provisional labels informed method
selection. A second 150-family sample, drawn with a different seed from the 414 eligible families
remaining after the primary selection, is now cryptographically locked as a replication reserve;
it has no item or exact-runtime-family overlap with the primary set.

The final protocol is frozen in
`revision_v3/protocols/final_evaluation_preregistration_v1.json`. It declares full DCRG versus
untyped guards as the single confirmatory AUPRC endpoint, uses 10,000 paired seed-aware
signer/deployer/project-cluster bootstrap replicates, and treats all baseline, operating,
calibration, coverage, and error-taxonomy analyses as secondary or descriptive. This prevents
selecting the paper's hypothesis after reading the human result.

The final retraining path now includes the strongest classical baseline from revision v2
(225-bin normalized opcode histogram + 512-bin hashed opcode 4-grams with XGBoost), alongside an
honestly named learned sequence+dense baseline. The frozen project-balanced repair is a separate
`dcrg_project_balanced` variant with total benign-control weight 8 per eligible project. The base
DCRG/baseline comparison does not receive these extra controls, avoiding a training-data
confound. All control runtimes, projects, weights, bytecode hashes, feature hashes, exclusions,
checkpoints, thresholds, and source hashes are recorded in the pre-label training manifest.

Statistical dependence is no longer equated with exact-runtime uniqueness. The primary 150 items
form 124 conservative score-blind clusters after linking repeated recovered authorities,
shared EOA deployers, and audited project families; 19 clusters contain multiple items and the
largest has four. These clusters, not the 150 runtime IDs, are the bootstrap unit.

To make the remaining provenance audit tractable without silently automating ownership claims,
`postcutoff_project_family_candidates.csv` now proposes the same 124 conservative research
families: 45 items are in strong on-chain must-link clusters, 12 are verified-source singletons,
and 93 remain explicit anonymous singletons requiring research. The proposal never edits the
authoritative audit and warns that verified source names do not establish legitimacy or official
brand association. Public Blockscout/Sourcify collection is complete for all 150 primary items;
20 have verified source-name leads. At this historical snapshot the audit was only 2/150
terminal; the authoritative execution update above supersedes that state with conservative,
non-attribution research-family holds.

## Bottom-line reviewer verdict

The project is finishable as a strong conference paper, but not with the revision-v2 story.
The defensible paper is not "a hierarchical sequence model that beats six baselines." That
architecture is incremental, its original baseline comparison mixes sequence length and
aggregation, and the benchmark's inherited target can reward reconstruction of the source static
rule rather than semantic risk assessment.

The strongest surviving direction is a **coverage-audited, guard-aware pre-authorization
screening study**. The core technical object is an auditable Delegation-Context Risk Graph (DCRG)
reduced to explicit graph-derived features. Its strongest scientific value is the combination of
an EIP-7702-specific decision boundary, guard/capability evidence with visible analysis gaps, and
dependence-aware evaluation. Sequence learning remains a baseline. Fusion, a GNN, low-risk
certification, and protocol-actor superiority are not supported headline claims.

## Estimated final three contributions

These are the contributions to target. Bracketed text states what is still required before each
can be written as a result rather than a goal.

1. **A leakage-controlled benchmark for bytecode-only EIP-7702 pre-authorization screening.**
   The benchmark separates exact/runtime families, project families, and time; records an
   explicit ambiguous class; and evaluates a decision available before behavioral history or
   reputation exists. [Required: complete independent dual human review and adjudication, publish
   agreement and class prevalence, and keep a new post-selection test set untouched.]
2. **A coverage-audited, guard-aware Delegation-Context representation.** DCRG links reachable
   sensitive capabilities to recognized guard evidence and retains unresolved control flow as an
   observable coverage state. Its extractor uses jump-fenced Solidity-metadata handling and
   conservative loop-state widening. The novelty is the EIP-7702 delegation semantics and
   explicit evidence boundary—not CFG recovery, metadata stripping, or graph learning in
   general. [Required: on the new human set, confirm the predeclared typed-versus-untyped endpoint;
   otherwise narrow this to guard-aware, coverage-audited representation.]
3. **A deployment-realistic evaluation and decision contract.** The study evaluates family-held
   out baselines, new legitimate project families, post-cutoff signer/delegate pairs, calibration
   shift, and abstention. The interface emits `WARN`, `NO_MODEL_WARNING`, or `DEFER`; it never
   equates a low model score with safety. [Required: freeze the weight-8 development rule, collect
   new legitimate projects, family holds, and retraining are complete; independent labels and the
   one-shot project/family-bootstrap evaluation remain required.]

## What the completed path search established

| Path | Result | Paper decision |
|---|---|---|
| Hierarchical sequence model | Strong inherited-label baseline, but generic and confounded by a longer input view | Retain as a learned baseline; do not center novelty on it |
| Fixed sequence+DCRG fusion | Better than sequence, not reliably better than DCRG | Supporting ablation only |
| Relational GNN | Futility stop after 9/15 runs; typed mean AUPRC 0.610 versus 0.636 untyped | Negative result; exclude from headline |
| Typed local graph motifs | No paired gain over aggregate DCRG or untyped motifs | Negative result; exclude from headline |
| Risk-controlled `LOW` tier | Failed badly under the current-label proxy | Remove any safe/low-risk certification claim |
| Coverage-correct CFG extraction | COMPLETE unique-runtime coverage increased 517/1,665 to 1,063/1,665 with zero regressions | Retain as technical validity contribution |
| Authority-relative extraction | 708 real signer/delegate pairs; 317 have decidable fixed-guard relations | Retain as capability/audit until labels prove decision value |
| Project-balanced legitimate controls | Development warning count fell 14/30 to 1/30 at weight 8 with small primary-metric change | Freeze and test on new projects; not final evidence yet |

The final coverage correction does not inflate performance: inherited-label mean DCRG AUPRC is
0.95375 versus 0.95409 under the old extractor (delta -0.00034, 95% CI
[-0.00617, 0.00423]). This is reassuring for validity and prevents a reviewer from interpreting
the analysis repair as performance tuning.

## If the current provisional labels are treated as human labels

This counterfactual answers what the likely endpoint looks like; it does not turn the labels into
independent human evidence. Of 150 items, 88 are `UNSAFE`, 20 `SAFE`, and 42 `UNCERTAIN`, leaving
108 binary decisions with 81.5% positive prevalence.

With the final jump-fenced extractor, full DCRG reaches mean AUPRC 0.93885 and AUROC 0.73788. It
beats untyped guards by +0.00427 AUPRC with a paired family-bootstrap 95% CI
[+0.00076, +0.01023]. This direction stays positive when every uncertain item is assigned either
class. The full-versus-capability delta is +0.01371 but its CI [-0.00531, +0.03851] crosses zero;
removing protocol-actor features changes AUPRC by -0.00091 and also crosses zero.

Against learned baselines on the same proxy labels, DCRG AUPRC is 0.93885 versus 0.89270 for the
sequence model (delta +0.04615, 95% CI [+0.00449, +0.09178]) and 0.90730 for histogram+n-gram
XGBoost (delta +0.03154, 95% CI [-0.01116, +0.08209]). Thus it provisionally beats the sequence
model, but not the strongest classical baseline with statistical confidence.

Therefore, under the requested human-label assumption:

- **yes**, there is a plausible paper endpoint around guard-aware DCRG;
- **no**, the evidence does not support protocol-actor/authority-feature superiority;
- full-DCRG superiority over capability-only features is **not yet supported**;
- **no**, a `LOW` or "safe to authorize" output is viable;
- these 150 labels **cannot** serve as final confirmatory evidence, because their results were
  used to choose the surviving method.

The assumption justifies completing the project. It does not justify stopping the labeling work.
The needed final set can be smaller and more focused because the method is now frozen, but it must
be genuinely untouched.

## Individual shortcomings and exact fixes

1. **Construct validity of labels.** The inherited positive class follows a source analyzer; DCRG
   encodes related static evidence. High performance may be rule reconstruction. Fix: dual blind
   semantic review, explicit `UNCERTAIN`, adjudication, evidence provenance, and agreement.
2. **Post-selection contamination.** The 150 provisional items have guided method selection. Fix:
   never call them final; freeze code/hyperparameters now and use a newly sampled post-cutoff set.
3. **Incremental novelty in revision v2.** Chunking, attention, CFGs, graph features, and
   selective classification all have prior art. Fix: frame novelty at the EIP-7702 authorization
   decision, the delegation-specific guard/capability schema, and the audited evidence boundary.
4. **Unfair architectural attribution.** The old hierarchical model sees up to 16K opcodes while
   nonhierarchical neural baselines see 2K sampled positions. Fix: describe that result as a
   system comparison, not proof that hierarchy or attention is superior; add equal-view controls
   only if sequence architecture remains a contribution.
5. **Graph overclaiming.** The retained classifier consumes graph-derived counts; it does not
   learn topology. Fix: say "typed representation with aggregate features." The tested relational
   and motif alternatives failed and should be disclosed briefly.
6. **Coverage and soundness.** Metadata bytes, loops, and unresolved jumps can distort capability
   counts. Fix implemented: exact known-shape CBOR plus instruction-boundary, terminal-predecessor,
   and no-trailer-`JUMPDEST` fences; state widening; residual gaps remain `PARTIAL`.
7. **Authority semantics not validated.** Historical rows lack the authorizing EOA, and aggregate
   authority-match counts do not vary among the 20 multi-authority runtimes. Fix: evaluate actual
   signer/delegate pairs after project attribution; drop authority superiority if decisions do not
   change correctly.
8. **Legitimate false warnings.** Unit-weight training warns on 14/30 known legitimate
   deployments. The chosen development repair reduces this to 1/30, but the same eight projects
   selected it and the eight-project CI reaches zero. Fix: freeze weight 8 and evaluate wholly new
   projects without retuning.
9. **Unsafe operating language.** Proxy-unsafe items frequently fall into the attempted low-risk
   group. Fix: use warning triage; incomplete analysis always defers; `NO_MODEL_WARNING` means only
   that the fixed warning threshold was not crossed.
10. **External-validity gap.** Family-disjoint folds are not temporal or project-external. Fix:
    complete the frozen post-cutoff project-family audit and report separate outcomes for malicious,
    legitimate, ambiguous, and unresolved cases.
11. **Class imbalance and metric interpretation.** The current-label binary proxy is 81.5%
    positive, so a high AUPRC alone can mislead. Fix: always report prevalence, AUROC, precision,
    recall, observed FPR with intervals, calibration error, and project/family-level counts.
12. **Robustness scope.** Bytecode flooding is one synthetic transformation, not universal
    adversarial robustness. Fix: call it Flood-200 or the exact transformation; retain failed
    first-`STOP` canonicalization as a negative finding, not a defense.
13. **Deployment claim.** Neural inference latency is not end-to-end analysis latency. Fix: report
    bytecode acquisition, DCRG extraction, model inference, timeout, and deferral separately.
14. **First/system claims.** Recent EIP-7702 studies already detect attacks using transactions and
    cross-contract analysis. Fix: use "to our knowledge, the first evaluated bytecode-only model
    at the pre-authorization decision boundary" only after the final literature audit, and make
    the distinction explicit in the same sentence.

## Ordered completion plan and acceptance gates

### Freeze now

1. **Done:** designate the final extractor as
   `bounded-cfg-1.3-jump-fenced-metadata-state-widening` and retain aggregate DCRG.
2. **Done:** freeze the project-balanced benign total weight at 8; do not explore more weights after seeing
   new-project outcomes.
3. **Done:** freeze all feature groups, baselines, thresholds, metrics, bootstrap unit, and exclusion rules.
4. **Done:** version and hash the full code/configuration and record that the separate 150-item
   Gold-Test proxy is development data.

### Build untouched evidence

5. **Done conservatively:** materialize score-blind research-family holds for the frozen worklist
   and exclude every detected overlapping benchmark/registry family from contributing checkpoints.
   Anonymous clusters remain non-attribution research groups, so the claim is leakage-reduced.
6. **Done:** preserve the score-blind primary sample and disjoint replication reserve, plus a
   separately frozen set of three new legitimate projects for descriptive external evaluation.
7. Have two independent reviewers label each mandatory item without seeing model scores or source
   labels; adjudicate disagreement and preserve `UNCERTAIN` as a result.
8. **Done:** collect legitimate implementations from projects not among the eight development
   controls, with release, deployment, runtime, and project-family provenance.

### Run once

9. **Done:** retrain sequence+dense, histogram+n-gram XGBoost, capability-only, untyped-guard, full
   guard-aware DCRG, and weight-8 DCRG after all required family/project holds. Fusion remains
   exploratory; do not revive the failed GNN or motif paths.
10. Evaluate the frozen endpoints once: full versus untyped AUPRC as the representation endpoint;
    full versus strongest learned/classical baseline as performance endpoints; new-project warning
    rate; post-cutoff recall; deferral/coverage; calibration; and paired family/project intervals.
11. Perform an error taxonomy by analysis coverage, proxy/delegate pattern, guard type, compiler,
    bytecode length, and project novelty without changing the model.

### Choose the paper honestly

12. **Method-paper gate:** the full DCRG must beat the strongest fair baseline or its predeclared
    untyped ablation with a paired interval excluding zero on untouched labels, while new-project
    false warnings remain credible. Then use all three target contributions.
13. **Benchmark/measurement gate:** if the interval crosses zero, publish the benchmark,
    coverage-correct analysis, legitimate-control failure, and negative method results. Do not
    manufacture a method-superiority claim; the measurement paper can still be strong.
14. Rewrite the manuscript only after Gate 12 or 13 is known. Replace the revision-v2 abstract,
    contribution list, method description, results tables, limitations, and title together so the
    claims match one coherent paper.

## Recommended title and claim boundary

Working title: **AuthGuard-7702: Coverage-Audited Delegation-Context Analysis for
Pre-Authorization Screening**

One-sentence claim boundary: AuthGuard-7702 prioritizes EIP-7702 delegate bytecode for warning or
deeper review at authorization time; it does not prove malicious intent, exploitability, or safety,
and it does not replace source audit, simulation, reputation, or transaction-based defenses.

## Current completion status

Engineering and method search: **complete for the frozen revision-v3 experiment**.

Scientific evidence required for a submission-ready paper: **approximately 75–80% complete**.

The remaining work is no longer open-ended model invention or provenance engineering. It is dual
independent human annotation/adjudication, the one-shot preregistered evaluation, and a manuscript
rewrite whose claims follow that result. Without independent labels the work remains a strong
development study; with favorable untouched-label results it becomes a defensible method paper. If
the method endpoint is null, the frozen benchmark, coverage audit, legitimate-control experiment,
and disclosed negative paths still support a narrower measurement paper.
