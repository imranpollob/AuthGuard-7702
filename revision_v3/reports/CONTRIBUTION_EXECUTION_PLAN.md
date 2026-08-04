# Three-Contribution Submission Plan

Date: 2026-08-04  
Decision: the evaluation infrastructure is ready, but the project-family audit and independent
reviews are unfinished; the paper is not yet ready to claim semantic validity or baseline
superiority.

## Estimated final contribution list

### C1. Authority-relative Delegation-Context Risk Graph

**Target claim.** We introduce DCRG, a bytecode-derived representation for EIP-7702 delegate
screening that connects externally reachable sensitive capabilities to typed authorization
evidence—self-call, signature, stored authority, fixed third party, ERC-4337 EntryPoint,
caller-supplied comparison, and `tx.origin`—while preserving COMPLETE/PARTIAL/UNKNOWN analysis
coverage.

**What is actually novel.** The narrow candidate novelty is the semantics of guards relative to
the authorizing EOA and delegate-execution context. CFG recovery, program graphs, bytecode ML,
EIP-7702 attack detection, hook rules, and graph/sequence fusion are prior art.

**Reviewer attack.** “This is a feature-engineered reconstruction of the Huang et al. rule, and
the labels were produced from that rule.”

**Required answer.** On independently adjudicated and post-cutoff labels, compare: the Huang et
al. hook/external-call rule; sequence+dense; a capability-only CFG; DCRG with untyped guards;
DCRG without protocol-actor features; full DCRG; and fixed fusion. Use the frozen folds,
family-clustered paired intervals, and no Gold-Test selection. Full DCRG must improve a
meaningful endpoint over the capability-only/untyped variants, or the typed-semantics novelty
claim is withdrawn.

### C2. Coverage-gated pre-authorization decision contract

**Target claim.** We operationalize bytecode screening as `WARN` / `LOW_OBSERVED_RISK` /
`DEFER`, with an invariant that incomplete semantic analysis can never produce a low-risk
decision. This makes analyzer incompleteness visible at the wallet decision boundary.

**What is actually novel.** Selective classification is not new. The contribution is the
EIP-7702 pre-authorization policy and its empirical error/coverage behavior under bounded
semantic analysis.

**Reviewer attack.** “DEFER merely hides errors, and `LOW_OBSERVED_RISK` will be read as safe.”

**Required answer.** Predeclare the threshold, show the complete risk-coverage curve, count and
inspect every human-UNSAFE item assigned low risk, report deferral by contract family/project,
and preserve the qualified name in the abstract, UI, tables, and artifact. The claim fails if
partial/unknown items can become low risk or if the low-risk error bound is operationally
unacceptable. The current primary benchmark already shows 47.4% deferral, so coverage cost
must remain prominent.

### C3. Provenance-audited benchmark and evaluation protocol for pre-authorization screening

**Target claim.** We release a reproducible evaluation resource that joins bytecode-family
holds, item-specific validation thresholds, dual-review/adjudicated labels, legitimate
project-family controls, authority/delegate authorization pairs, post-cutoff dual-reviewed
families spanning both classes, complete prediction artifacts, and paired uncertainty.

**What is actually novel.** This is not the first EIP-7702 attack dataset: Huang et al. already
publish a seven-chain dataset and 924 manually verified attacks. The candidate contribution is
the pre-authorization screening task, strict training/test provenance, and coverage-aware
evaluation against both malicious and legitimate delegate families.

**Reviewer attack.** “Gold-Test is sampled from the training-era corpus; legitimate controls
contain no malicious positives; authority context is absent; and project families leak.”

**Required answer.** Complete all 150 frozen Gold-Test annotations with two blinded primary
reviewers and third-reviewer adjudication, publish agreement, and run the fail-closed evaluator.
Then assemble a later-time checkpoint containing malicious and benign delegates plus real
authorizing-EOA/delegate pairs. Before scoring, retrain every contributing checkpoint after
holding out all exact hashes and related project families. The post-cutoff set must remain
untouched until the protocol, feature groups, and thresholds are frozen.

## Current evidence and stop/go decisions

| Evidence | Current result | Submission interpretation |
|---|---:|---|
| DCRG extraction | 2,190/2,190 rows; 1,665 runtimes; 0 errors | Engineering pass |
| Complete coverage | 670/2,190 (30.6%) | Large deferral cost; not safety coverage |
| Fusion vs sequence, inherited labels | AUPRC +0.056, 95% CI +0.014 to +0.111 | Context helps the sequence baseline only on circular labels |
| Fusion vs DCRG, inherited labels | AUPRC +0.004, CI crosses zero | Fusion is not a contribution yet |
| Full DCRG vs capability-only CFG | AUPRC +0.0129, CI +0.0019 to +0.0269 | Guard-aware context helps on circular labels |
| Full DCRG vs untyped guards | AUPRC -0.00004, CI crosses zero | Typed semantics not validated |
| Full DCRG vs no protocol actors | AUPRC +0.00040, CI crosses zero | Authority/EntryPoint value not validated |
| Legitimate controls | 14 WARN / 16 DEFER / 0 low risk | Reject broad low-false-warning claim |
| Legitimate leave-one-project-out | Same 14 WARN / 16 DEFER | Control augmentation failed |
| CPU DCRG extraction | median 49.9 ms; p95 812.7 ms; p99 1.77 s | Feasible median, expensive tail |
| Human Gold-Test | 0/150 finalized | Mandatory blocker |
| Gold-Test score freeze | 150 items, 3 seeds, 4 DCRG variants; score-only SHA-256 lock verified | Prevents post-label model/ablation selection |
| Post-cutoff review set | Authoritative snapshot; 150 score-blind exact-runtime families frozen; all project families unresolved and all items unlabeled | Project-audit/retraining/review blockers remain |
| Real authority/delegate pairs | 708 extracted; 27 authority-match / 295 mismatch pairs | Representation is nontrivial; correctness untested |

## Execution order

1. **Freeze the method after ablation.** Complete: Gold-Test now has score-only fusion and all
   four representation variants locked before any annotation, with manifest/artifact hashes and
   exact seed/model coverage. Make only analyzer-correctness fixes after this point; every such
   change must increment the schema and invalidate/regenerate the lock before review begins.
2. **Finish independent review.** Two primary reviewers complete Gold-Test; disagreement gets a
   third adjudicator. Export must contain exactly 150 manifest IDs and pass the strict
   dual-review gate. Report class counts, raw agreement, Cohen/Fleiss statistics where valid,
   adjudication rate, and exclusion reasons.
3. **Run the predeclared human-final analysis once.** The fail-closed evaluator now verifies the
   pre-label lock and evaluates full DCRG against capability-only, untyped-guard, and
   actor-removed variants as well as sequence/fusion, using item-specific thresholds, paired
   family bootstrap, and the selective error audit. Do not tune on Gold-Test. If DCRG does not
   beat the capability-only/untyped baselines, narrow C1.
4. **Complete the later-time checkpoint audit.** The frozen Ethereum checkpoint now yields 708
   signer/delegate pairs with code and 564 candidate unseen exact-runtime families; a score-blind
   sample of 150 is locked. Complete the generated project-family audit, dual review, and
   adjudication. Hold every related family out of all training before scoring.
5. **Validate authority consequences.** Real-context extraction shows nontrivial features (27
   authority-match pairs, 295 mismatch pairs, and 28 EntryPoint-guard pairs). After provenance
   holds and labeling, report how often those features change a correct decision; feature
   presence alone is insufficient.
6. **Repair or bound legitimate false warnings.** Audit ZeroDev, Biconomy, and Coinbase warnings
   by path and guard type. Correct analyzer errors, but do not tune to named test projects. If a
   leakage-safe development-control set cannot reduce warnings, narrow the scope to analyst
   triage rather than wallet automation.
7. **Submission gate.** Promote results into the abstract only if human and post-cutoff tests
   support at least one DCRG-specific improvement, low-risk errors are acceptable and fully
   audited, and no test family contributes to training. Otherwise submit the honest narrower
   result: a contextual analyzer plus explicit-deferral framework and a negative finding that
   sequence fusion adds no reliable value.

## Wording that should survive review

- Say “family-held-out on the canonical corpus,” not “external,” for Gold-Test.
- Say “validation-derived nominal 5%-FPR threshold,” not “5% FPR guarantee.”
- Say “low observed risk under complete bounded analysis,” never “safe.”
- Say “typed authority-relative representation,” not “first graph model.”
- Say “improves over the sequence baseline on inherited labels,” not “beats all baselines.”
- Describe human/post-cutoff contributions as targets until the artifacts exist.
