# DCRG Reviewer-Readiness Audit

Date: 2026-08-04  
Status: implementation and inherited-label engineering evaluation complete; final scientific
claim blocked on human-final and post-cutoff evidence.

> **Superseded technical snapshot:** the coverage and legitimate-control counts below describe
> the original bounded extractor. Use `RESEARCH_ENDPOINT_AND_SUBMISSION_PLAN.md` and
> `EXTENSIVE_RESEARCH_PATHS.md` for the retained jump-fenced v3 extractor and final path decisions.
> This file is preserved as the audit trail that motivated the later corrections.

## Three target contributions

1. **An EIP-7702 Delegation-Context Risk Graph (DCRG).** A typed representation of delegate
   entrypoints, authorization guards, sensitive capabilities, and coverage gaps, with guard
   meaning interpreted relative to the authorizing EOA when that context is available. The
   claim is not “first CFG for smart contracts”; the proposed novelty is the delegation-context
   semantics and explicit distinction among self-call, signature, stored-authority,
   fixed-third-party, caller-supplied, and `tx.origin` checks.
2. **A coverage-aware selective pre-authorization policy.** Fixed monotone fusion of DCRG and
   bytecode-sequence risk, followed by `WARN` / `LOW_OBSERVED_RISK` / `DEFER`. Incomplete
   semantic evidence can never produce `LOW_OBSERVED_RISK`. The claim is bounded triage under
   incomplete bytecode evidence, not proof of safety or replacement of formal analysis.
3. **A provenance-safe evaluation resource and protocol.** Family-held-out checkpoints,
   item-specific validation-derived thresholds, full graph/feature artifacts, adjudicated human
   labels, documented legitimate project-family controls, and post-cutoff malicious and benign
   evaluation. The code and inherited-label artifacts exist; the adjudicated and post-cutoff
   evidence is not yet complete, so this contribution is currently a target rather than a
   submission-ready claim.

## Evidence now implemented

- `dcrg-1.1` extraction completed for 1,665 unique runtimes covering all 2,190 primary rows;
  zero analysis crashes. Coverage is `COMPLETE` for 670 samples (30.6%) and `PARTIAL` for
  1,520 (69.4%).
- Family-held-out, three-seed evaluation is complete. Pooled out-of-fold paired bootstrap gives
  fusion-minus-sequence AUPRC +0.056 (95% CI +0.014 to +0.111) and recall at the
  validation-derived 5%-FPR policy +0.088 (+0.048 to +0.137). The observed-FPR difference
  crosses zero.
- Fusion-minus-DCRG AUPRC is +0.004 (95% CI -0.010 to +0.025); recall and FPR intervals also
  cross zero. The neural sequence view therefore has not shown a statistically supported gain
  over DCRG alone on the inherited labels.
- Full DCRG improves over a capability-only CFG summary by +0.0129 AUPRC (95% CI +0.0019 to
  +0.0269), but not over untyped guard features (-0.00004, -0.00219 to +0.00311). Removing
  protocol-actor/authority-match features also has no supported effect (+0.00040, -0.00097 to
  +0.00325). Typed authority semantics are therefore implemented but not empirically validated.
- The CFG audit corrected a previously unreachable storage-condition category: paths protected
  only by storage-derived conditions are now distinguished from paths with no recognized guard.
  The labeling pipeline also no longer infers an exploit solely from capability opcodes without
  a proven reachable path. Regenerated label projections exactly match the review artifacts.
- Gold-Dev and Gold-Test scoring now uses only the checkpoint whose outer test fold contains
  each sampled family. Unknown family identifiers fail closed; frozen non-primary families are
  recognized as absent from training and may use the external ensemble.
- The old provisional fine-tuned model is excluded from the independent Gold-Test ranking
  because its training provenance does not exclude every Gold-Test family.
- On 30 documented legitimate deployments, the current DCRG+sequence policy produces 14
  majority `WARN` and 16 `DEFER`, with no `LOW_OBSERVED_RISK`; all 30 have partial analyzer
  coverage. Warnings cluster in ZeroDev, Biconomy, and Coinbase account implementations. This
  negative control result currently rejects any broad operational false-positive claim.
- A leave-one-project-out DCRG experiment that excludes the held-out project's deployments and
  known canonical families, then adds deduplicated benign controls from the other seven
  projects, produces the same 14 `WARN` / 16 `DEFER` distribution. This attempted remedy does
  not support a control-training contribution.
- Isolated CPU extraction over all 1,665 unique runtimes completed without analysis errors:
  median 49.9 ms, p95 812.7 ms, p99 1.77 s, maximum 2.64 s, and peak process RSS 166,160 KiB.
  This is bytecode-to-DCRG latency and is reported separately from neural inference.
- The human-final evaluator now fails closed on incomplete adjudication, mandatory dual-review
  violations, manifest mismatch, unknown labels, prediction gaps, and single-class binary data.
  Once labels exist it will use only frozen family-held-out scores and item-specific validation
  thresholds, report
  sequence/DCRG/fusion metrics and selective-policy errors, and compute paired
  family-clustered intervals without selecting on Gold-Test.
- Gold-Test fusion scores and all four predeclared DCRG representation variants are now copied
  into score-only artifacts and SHA-256 locked across exactly 150 items and three seeds while the
  annotation database still contains zero Gold-Test reviews. Final evaluation verifies this
  lock before reading labels and reports full-DCRG paired intervals against capability-only,
  untyped-guard, and protocol-actor-removed variants.
- A frozen post-cutoff Ethereum checkpoint now provides 734 cryptographically recoverable
  signer/delegate pairs and 708 pairs with historical runtime code. Authority-aware DCRG
  extraction covers all 708 without crashes: 222 `COMPLETE`, 486 `PARTIAL`, 27 pairs with a
  hardcoded caller matching the recovered EOA, 295 with a hardcoded caller differing from it,
  and 28 with an ERC-4337 EntryPoint guard. These counts prove that real authority context is
  represented, not that the distinctions improve correct predictions.
- Canonical similarity screening leaves 564 candidate unseen exact-runtime families. A
  deterministic score-blind sample of 150 is frozen, its evidence packets carry neutral signer
  and authorization-event provenance, and a fail-closed project-family audit template is
  initialized. All 150 remain unlabeled and project-family-unresolved.
- The repository-wide revision-v3 suite passes, and the independent frozen-input verifier
  confirms all 144 revision-v2 files are unchanged. Post-cutoff snapshot, sample,
  feature, and graph artifacts carry SHA-256 locks checked before downstream use.

Primary artifacts:

- `results/delegation_context/dcrg_extraction_report.json`
- `results/delegation_context/dcrg_primary_features.csv.gz`
- `results/delegation_context/dcrg_unique_runtimes.jsonl`
- `results/delegation_context/dcrg_fusion_report.json`
- `results/delegation_context/dcrg_fusion_bootstrap.json`
- `results/delegation_context/dcrg_ablation_report.json`
- `results/delegation_context/legitimate_control_report.json`
- `results/delegation_context/legitimate_lopo_report.json`
- `results/delegation_context/dcrg_runtime_report.json`
- `results/human_final/gold_test_scoring_lock.json`
- `results/human_final/gold_test_frozen_predictions.csv.gz`
- `results/human_final/gold_test_frozen_ablation_predictions.csv.gz`
- `results/llm_provisional_opus5/gold_dev_baseline/gold_dev_baseline_report.json`
- `results/llm_provisional_opus5/gold_test/gold_test_report.json`
- `results/postcutoff_snapshot/ethereum_snapshot_report.json`
- `results/postcutoff_snapshot/postcutoff_review_lock.json`
- `results/postcutoff_snapshot/postcutoff_authority_dcrg_report.json`

## Shortcomings a reviewer can still reject

1. **Independent label validity is unresolved.** The inherited primary label partly encodes
   static-analysis behavior that DCRG represents directly. High DCRG accuracy can therefore be
   label-rule reconstruction. No wording can repair this; human adjudication must be completed.
2. **No sufficient post-cutoff labeled evaluation.** The frozen snapshot and sample now exist,
   but legitimate controls measure only false warnings and the 150 new items are unlabeled and
   project-family-unresolved. A credible submission needs provenance-backed malicious and benign
   new families or must narrow the claim to analyzer-rule triage.
   The current legitimate-control result is also poor (14/30 majority warnings), so the method
   needs leakage-safe project-family control training or a narrower decision claim before it is
   operationally credible.
3. **Authority context is absent from the historical labels.** Benchmark rows record delegate
   addresses, not the EOA proposing authorization. The new snapshot supplies 708 real pairs and
   nonzero authority-relative features, but no independent labels yet show that these features
   change a correct decision. That causal evaluation remains mandatory.
4. **Typed semantics do not yet beat untyped guards.** The new ablation supports guard-aware
   context over capability-only CFG features, but not the individual authority/actor types.
   Without real authority pairs and an independent-label gain, typed semantics remain a design
   hypothesis rather than a demonstrated contribution.
5. **The learned DCRG view consumes aggregate graph-derived counts.** The artifact preserves
   typed nodes and edges, but XGBoost does not perform relational message passing. The paper
   must say “graph-derived feature view,” or add and fairly compare a relational encoder; it
   must not imply that the current classifier learns directly over graph topology.
6. **Bounded analysis is incomplete on most samples.** A 69.4% partial-coverage rate is honest
   but operationally expensive: the selective policy defers about half of outer-test items.
   Report risk-versus-coverage curves and analyzer failure categories; do not hide deferral.
7. **Fusion is not better than DCRG alone.** The current experiment supports “context helps the
   sequence model,” not “fusion is the best method.” Either show complementary value on
   independently labeled/post-cutoff data or simplify the paper around DCRG plus selective
   decisions.
8. **Gold-Test is not external data.** It is a blinded label audit sampled from the canonical
   corpus. OOF scoring repairs training leakage, but the paper must not describe it as a new
   population.
9. **Operating FPR shifts on the small provisional audit.** OOF Opus-5 Gold-Test observed FPR
   is 0.10 for the frozen sequence baselines despite nominal 0.05 validation targeting. The
   paper needs uncertainty intervals and a clear “nominal, not guaranteed” statement.
10. **The previous fine-tuning headline is invalid for independent ranking.** Retrain only after
   holding out every Gold-Test family, or remove the fine-tuned model contribution entirely.
11. **Tail latency and partial coverage remain deployment costs.** End-to-end DCRG extraction is
   now measured, but p99 is 1.77 s and 69.4% of benchmark samples terminate with partial
   coverage. A wallet integration needs an explicit timeout budget and user-facing defer path.
12. **Novelty still needs a precise related-work boundary.** Huang et al. already provide
    cross-chain EIP-7702 transaction filtering, Gigahorse decompilation, hook/external-call
    rules, manual confirmation, and an attack dataset; Qi et al. already study phishing trigger
    paths and ERC-4337 activation. Generic smart-contract CFGs, bytecode learning, multi-view
    fusion, uncertainty, and selective classification are also prior art. The paper must make
    only independently validated authority-relative screening consequences the novelty claim.

## Acceptance gates

The three contributions become defensible only if all mandatory gates pass:

| Gate | Required evidence | Pass criterion |
|---|---|---|
| Human Gold-Test | Two blinded reviewers plus adjudication; provenance and agreement report | Adequate class counts; agreement reported; no label leakage; predeclared analysis |
| Post-cutoff families | Complete project-family holds and retraining before scoring | No benchmark project/family in any contributing checkpoint; malicious and benign classes |
| DCRG ablation | Capability-only CFG, untyped guards, typed DCRG, sequence, fusion, and selective policy on independent labels | Paired family-clustered intervals; no cherry-picked fold or seed |
| Authority-context test | Real authorizing EOA/delegate pairs | Demonstrate that authority-relative features change correct decisions, not merely exist in code |
| Selective safety | Risk-coverage curve and error audit | Every low-risk error inspected; partial/unknown never silently mapped to safe |
| Runtime | Full bytecode-to-decision CPU benchmark | Analyzer timeout and deferral included; neural-only latency labeled separately |
| Artifact | Clean-environment rerun | Hash-verified inputs, exact commands, tests, predictions, and tables regenerate |

If human/post-cutoff results do not support DCRG superiority, the scientifically acceptable
fallback is a narrower paper: an EIP-7702-specific contextual analysis and coverage-aware
decision framework with a negative result showing that sequence learning adds no reliable value.
That is stronger than preserving an unsupported “beats all baselines” claim.

The executable human-final gate is:

```bash
python3 revision_v3/annotation_app/export.py gold_test
python3 revision_v3/experiments/human_label_evaluation/evaluate_against_human_labels.py \
  revision_v3/annotation_app/release_gold_test.json gold_test
```
