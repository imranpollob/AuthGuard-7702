# Retained Title and Abstract Direction

Status date: 2026-08-04
Evidence status: development only; replace bracketed outcomes after untouched human evaluation.

## Recommended title

**AuthGuard-7702: Coverage-Audited Delegation-Context Analysis for Pre-Authorization Screening**

This title avoids unsupported claims of safety, learned graph topology, fusion superiority, or
universal robustness. It makes the intended decision point and the retained technical
contribution explicit.

## Provisional abstract skeleton

EIP-7702 allows an externally owned account to execute delegate-contract code in the account's
storage, balance, and identity context. This creates a security decision before authorization,
when transaction history, reputation, and verified source code may be unavailable. We present
AuthGuard-7702, a bytecode-only warning and triage framework built around a Delegation-Context
Risk Graph (DCRG). DCRG links reachable sensitive capabilities to recognized guard evidence and
preserves unresolved control flow as an explicit coverage state. Its bounded extractor combines
conservative state widening with jump-fenced Solidity-metadata recognition: metadata is excluded
from the opcode backstop only when its structure, instruction boundary, predecessor, and jump
targets satisfy the stated safety conditions.

On 1,665 unique runtimes, these corrections increase complete bounded-analysis coverage from
31.1% to 63.8% without converting any previously complete runtime to partial coverage. The
coverage repair does not improve inherited-label AUPRC, separating analyzer validity from model
tuning. **[Replace after the single final run: on an untouched, independently adjudicated,
family- and project-held-out test set, compare guard-aware DCRG with capability-only, untyped,
sequence+dense, and classical bytecode baselines using paired signer/deployer/project-clustered
intervals.]** We further
evaluate documented legitimate projects and post-cutoff signer/delegate pairs, and map incomplete
analysis to `DEFER`. AuthGuard-7702 is an advisory pre-authorization screener; it neither proves
malicious intent nor certifies a delegation as safe.

## Development evidence that must not be promoted to the final abstract

- Treating current provisional labels as human-like, DCRG reaches 0.93885 AUPRC and exceeds the
  sequence model by +0.04615 (95% CI [+0.00449, +0.09178]).
- DCRG exceeds untyped guards by +0.00427 ([+0.00076, +0.01023]) but does not significantly exceed
  capability-only or histogram+n-gram XGBoost.
- The provisional labels belong to the separate Gold-Test development set; they informed method
  selection and therefore cannot be the final test set. The post-cutoff 150-item set remains
  unlabeled and untouched.
- A low-risk/safe tier failed; the final interface is warning/no-warning/defer, never a safety
  certificate.
