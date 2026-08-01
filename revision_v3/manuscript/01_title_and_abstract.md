# Title Options

1. AuthGuard-7702: Compact Neural Triage for EIP-7702 Delegate Safety
2. Screening EIP-7702 Delegates at Scale: A Lightweight Sequence Model with Semantic Escalation
3. AuthGuard: Fast, Calibrated Risk Scoring for Account-Abstraction Delegate Contracts

## Abstract (provisional metric placeholders)

EIP-7702 lets externally-owned accounts temporarily execute code from an arbitrary delegate
contract, creating a new class of authorization-time risk: a wallet owner may sign an
authorization without any tooling that evaluates whether the delegate is safe to run with
their identity and assets. We present AuthGuard, a compact neural classifier
(`authguard_sequence_dense`, 97,646 active parameters) that scores EIP-7702 delegate bytecode
for authorization-risk in **[PROVISIONAL: 2.83ms median CPU latency]**, alongside a
semantic-analysis evidence pipeline (verified-source retrieval, decompilation, automated
guard-tracing) used both to construct evaluation labels and to demonstrate that AuthGuard's
role is triage-and-escalation, not replacement, for deeper analysis.

We evaluate AuthGuard against **[PROVISIONAL, LLM-generated reference labels — independent
human review in progress]** on two held-out samples: Gold-Dev (60 items, AUPRC
**[0.925 PROVISIONAL]**) and Gold-Test (150 items, AUPRC **[0.963, 95% CI 0.928-0.991,
PROVISIONAL]**), compare against a source-derived static rule (Gold-Test precision
**[0.978 PROVISIONAL]**, recall **[0.344 PROVISIONAL]**), and show that a simple
score-threshold cascade reduces the fraction of items requiring the more expensive static
rule check to **[63% PROVISIONAL]** while matching the rule's false-positive rate. We
release the full evidence-collection pipeline, the LLM-provisional labeling protocol, and
[PROVISIONAL — extend once human review completes] independent human-adjudicated labels for
230 delegate contracts.

**All quantitative claims in this abstract are placeholders pending independent human
review; see `revision_v3/reports/LLM_VS_HUMAN_AGREEMENT_REPORT.md` (currently
`PENDING_HUMAN_LABELS`) before any submission.**
