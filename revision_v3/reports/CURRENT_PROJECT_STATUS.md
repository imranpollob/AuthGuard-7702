# AuthGuard-7702 Current Project Status

Date: 2026-08-04

Decision: **the project has a viable strong-paper path; human annotation is the only remaining
evidence-collection blocker.**

## What is complete

- The method, ablations, strongest classical and learned baselines, operating thresholds,
  exclusions, metrics, and bootstrap units are preregistered and hashed.
- The primary post-cutoff sample has 150 items. One predeclared Ambire overlap is excluded, leaving
  149 items for model evaluation. A separate 150-item confirmatory reserve remains locked.
- Conservative score-blind family clustering is complete. It is deliberately overinclusive for
  retraining holds and makes no brand-ownership claim for anonymous clusters. The training pipeline
  reports 146 mandatory canonical family holds and 607 removed canonical rows.
- Frozen three-seed retraining completed: 21 checkpoints, 447 primary prediction rows, and all
  scoring-provenance checks passed before annotation was unlocked.
- A supplemental label-blind operating contract is now frozen over all seven models. It was
  created while the annotation database still contained zero post-cutoff judgments and locks both
  its decision artifact and its later evaluator. For full DCRG, the 149-item pre-label operating
  counts are 62 `WARN`, 51 `NO_MODEL_WARNING`, and 36 `DEFER`; these are outputs, not accuracy or
  safety evidence.
- A separate pre-scoring legitimate-control registry contains three new projects: Tangem,
  Startale, and Rainbow. It distinguishes new projects, new runtimes, and new implementation
  lineages instead of treating them as interchangeable.
- The principal project-balanced model produced 0 `WARN`, 2 `NO_MODEL_WARNING`, and 1 `DEFER` on
  those three projects. This is descriptive evidence, not a significance or safety claim.
- The annotation application is unlocked. R1 and R2 each have 150 pending assignments, model
  scores are hidden, and zero post-cutoff annotations currently exist. A new fail-closed readiness
  audit verifies the locked guide, taxonomy, manifest, assignments, and recursively score/label-free
  evidence. Its current status is `AWAITING_NAMED_REVIEWER_ATTESTATION`: reviewer aliases exist,
  but real qualifications, independence, calibration, and conflict attestations have not been
  supplied.

## Defensible three-contribution target

1. **A leakage-reduced, temporally separated evaluation resource for bytecode-only EIP-7702
   pre-authorization screening.** It separates exact runtimes, conservative research families,
   development labels, untouched human labels, and a locked reserve; it reports `UNCERTAIN` rather
   than forcing ambiguous cases into a binary class.
2. **A coverage-audited, guard-aware Delegation-Context representation.** DCRG connects reachable
   sensitive capabilities with typed guard evidence and exposes incomplete analysis as `PARTIAL`
   instead of silently treating missing evidence as absence. The novelty claim is bounded to the
   EIP-7702 authorization decision and evidence contract, not generic CFG recovery or graph
   learning.
3. **A deployment-realistic warning-and-deferral evaluation.** The frozen interface emits `WARN`,
   `NO_MODEL_WARNING`, or `DEFER`, evaluates family-held-out post-cutoff cases and new legitimate
   projects, and never interprets a low score as proof of safety.

The infrastructure and pre-label artifacts for contributions 1 and 3 are complete, but their human
outcome claims remain conditional on independent review. A strong method claim for contribution 2
is conditional on the preregistered full-DCRG versus untyped-guard result on untouched human
labels.

## Current literature boundary

The novelty cannot be “the first EIP-7702 security analysis” or “the first EIP-7702 malicious
contract detector.” A USENIX Security 2026 study already combines large-scale transaction analysis,
Gigahorse decompilation, and cross-contract rule matching for EOA-targeted, contract-targeted, and
composite attacks. A separate EIP-7702 phishing study measures authorization/execution events and
contract-family concentration. PhishingHook (DSN 2025) already compares 16 bytecode model families
for generic phishing-contract detection, so this paper also cannot claim the first pre-interaction
bytecode phishing classifier or first opcode-model comparison.

The defensible distinction is narrower: AuthGuard-7702 studies score-blind, bytecode-only screening
at the authorization decision before behavioral history is required, explicitly audits analysis
coverage and project-family dependence, and returns warning/no-warning/defer rather than a binary
maliciousness or safety verdict. Any “first” wording must say this complete boundary in the same
sentence and should be retained only after the final bibliography audit.

## Reviewer concerns and current disposition

| Reviewer concern | Current evidence | Remaining requirement |
|---|---|---|
| Labels reconstruct a source rule | Development proxy is explicitly separated from final evidence | Dual blind semantic review, adjudication, agreement, and prevalence |
| Method was selected on the test set | Primary protocol, code, thresholds, and training provenance are frozen before labels | Do not tune after labels; run the endpoint once |
| Runtime split leaks project families | Conservative family holds remove related canonical data without inventing brands | Describe the result as leakage-reduced, not leakage-free |
| Baselines are weak or unfair | Learned sequence and histogram+n-gram XGBoost are included on identical frozen splits | Report all predeclared comparisons, including null results |
| Legitimate implementations trigger warnings | Separate new-project protocol is complete; principal outcome is 0 WARN / 2 NO_MODEL_WARNING / 1 DEFER | Keep this descriptive because n=3 and one case is partial |
| The graph claim is overstated | Failed GNN and motif paths are retained as negative results; final model uses graph-derived aggregates | Use “typed representation with aggregate features” |
| Missing analysis is mistaken for safety | `PARTIAL` coverage and `DEFER` are explicit; Startale demonstrates the behavior | Never rename `NO_MODEL_WARNING` as safe or benign |
| Robustness is universalized | Only Flood-200 is supported; first-`STOP` canonicalization failed | Name the exact transformation and disclose scope |

## Why the provisional labels cannot simply be called human labels

Treating the current proxy as if it were human-labeled predicts a promising endpoint: full DCRG
has mean AUPRC 0.93885, beats the learned sequence baseline, and has a small positive paired
advantage over untyped guards. But those labels informed method selection. Renaming them does not
restore independence and would expose the paper to a decisive post-selection objection.

They justify finishing the project; they cannot close it. The final claim must come from the
already frozen primary items labeled independently without access to model scores or proxy labels.

## Exact remaining path

First complete the roster template at
`revision_v3/protocols/postcutoff_reviewer_roster_template.csv` and run:

```bash
python3 revision_v3/experiments/human_label_evaluation/audit_postcutoff_review_readiness.py \
  --roster revision_v3/protocols/postcutoff_reviewer_roster.csv
```

Do not begin until it reports `READY_FOR_INDEPENDENT_HUMAN_REVIEW`. Then launch the verified
reviewer application from the repository root with:

```bash
uvicorn app:app --app-dir revision_v3/annotation_app --host 127.0.0.1 --port 8420
```

Use distinct R1 and R2 identities for primary review and reserve R3 for disagreement adjudication.
Do not share model-score or proxy-label artifacts with any reviewer.

1. Two qualified reviewers independently label all 150 primary items as `UNSAFE`,
   `NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND`, `INDETERMINATE`, or `NOT_BYTECODE_SCREENABLE`, recording
   evidence and confidence without viewing model scores.
2. Adjudicate disagreements, freeze labels, and report raw agreement, Cohen's kappa, class
   prevalence, uncertain prevalence, and exclusions.
3. Run the preregistered confirmatory evaluation once. Do not change features, thresholds, models,
   holds, exclusions, or the primary endpoint afterward.
   Then run the separately frozen descriptive operating evaluator for the pre-label
   `WARN`/`NO_MODEL_WARNING`/`DEFER` consensus artifact; report Wilson intervals and preserve the
   statement that `NO_MODEL_WARNING` is not safety.
4. Select the paper branch honestly:
   - **method paper** if full DCRG beats the predeclared fair comparator with the required paired
     uncertainty and operational behavior remains credible;
   - **measurement paper** if superiority is null, centering the leakage-reduced resource,
     coverage findings, abstention behavior, legitimate-control case study, and negative results.
5. Rewrite and build the manuscript from the frozen results, then audit every abstract,
   contribution, table, and conclusion claim against generated artifacts.

The result-contingent manuscript structure, artifact-backed table plan, method/measurement branch
wording, one-shot command, and final acceptance checklist are prebuilt in
`revision_v3/manuscript/09_SUBMISSION_BLUEPRINT.md`.

A separate IEEE revision-v3 LaTeX draft now compiles to a seven-page pre-label PDF at
`revision_v3/paper_submission/main.pdf`. It includes the full task, DCRG schema and extraction,
post-cutoff provenance, reviewer protocol, dependence-aware statistics, label-free results,
negative paths, limitations, and reproducibility details. Its 48 label-free macros are generated
from hash-bound frozen artifacts; final-result macros remain deliberately red and unresolved. Its
claim audit has exactly one blocker: incomplete independent human review. The supplied revision-v2
LaTeX remains untouched and still has 20 blockers.

## Claim boundary

AuthGuard-7702 prioritizes EIP-7702 delegate bytecode for warning or deeper review before
authorization. It does not prove malicious intent, exploitability, legitimacy, or safety, and it
does not replace source audit, simulation, reputation, or transaction-based defenses.
