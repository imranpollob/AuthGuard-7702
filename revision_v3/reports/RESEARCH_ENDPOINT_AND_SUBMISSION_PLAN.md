# AuthGuard-7702 Research Endpoint and Submission Plan

Date: 2026-08-04
Status: method development is substantially complete; independent final evidence is not.

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
   new legitimate projects, finish post-cutoff project attribution and labels, retrain after all
   mandatory family holds, then report project-level and family-bootstrap uncertainty.]

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

1. Designate the final extractor as
   `bounded-cfg-1.3-jump-fenced-metadata-state-widening` and retain aggregate DCRG.
2. Freeze the project-balanced benign total weight at 8; do not explore more weights after seeing
   new-project outcomes.
3. Freeze all feature groups, baselines, thresholds, metrics, bootstrap unit, and exclusion rules.
4. Version and hash the full code/configuration and record that the existing 150-item proxy is
   development data.

### Build untouched evidence

5. Complete project attribution for the frozen post-cutoff worklist and exclude every overlapping
   benchmark/registry family from every contributing training checkpoint.
6. Select a new score-blind final sample after the exclusions. Include enough bounded-negative
   and legitimate project families to estimate false warnings; do not accept an overwhelmingly
   unsafe-only test set.
7. Have two independent reviewers label each mandatory item without seeing model scores or source
   labels; adjudicate disagreement and preserve `UNCERTAIN` as a result.
8. Collect additional legitimate implementations from projects not among the eight development
   controls, with release, deployment, runtime, and project-family provenance.

### Run once

9. Retrain sequence, capability-only, untyped-guard, full guard-aware DCRG, and weight-8 DCRG after
   all required family/project holds. Do not revive the failed GNN, motif, or fusion paths unless a
   new preregistered hypothesis independently requires them.
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

Engineering and method search: **approximately 80% complete**.

Scientific evidence required for a submission-ready paper: **approximately 55–60% complete**.

The remaining work is no longer open-ended model invention. It is independent annotation,
project-family provenance, one frozen retraining/evaluation, and a manuscript rewrite. Those are
mandatory: without them the work is a promising development study; with favorable results similar
to the current-label proxy, it becomes a defensible method paper.
