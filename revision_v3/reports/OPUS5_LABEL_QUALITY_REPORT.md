# Opus 5 Label Quality Report — Class Balance Audit

**LABEL_SOURCE=LLM_PROVISIONAL_OPUS5 · STATIC_ANALYZER_EVIDENCE=VISIBLE · STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW**

PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. Not human labels, not expert labels, not ground truth.


The previous provisional pass produced 9/6/5 (Pilot), 5/42/13 (Gold-Dev) and 7/131/12 (Gold-Test) SAFE/UNSAFE/UNCERTAIN — 87% UNSAFE across the two Gold sets. This report audits whether the imbalance in *this* pass reflects real unauthenticated paths or an artefact of the evidence pipeline. No attempt was made to force a balanced distribution.

## 1. Diagnosis of the previous pass's imbalance

The previous pass's guard tracer (`evidence_pipeline.trace_guards`) scans the contiguous byte window between one dispatch offset and the next for `CALLER|ORIGIN … EQ … JUMPI` within 8 instructions. It cannot follow a jump. It therefore could not see guards in shared internal helpers (what a Solidity `modifier` compiles to), signature checks, or storage-based permission checks, and it could not tell whether the sensitive opcode it was worried about was even reachable from that entry. It returned `OPEN_FOUND` for 50/60 Gold-Dev and 140/150 Gold-Test items, and the labeling step treated `OPEN` as missing access control.

Re-analysing the same 230 bytecodes with a CFG guard-dominance test changes that picture materially:

| set | old OPEN_FOUND | old GUARDED_ALL | old AMBIGUOUS | new UNGUARDED_PATH | new GUARD_DOMINATED | new no-sensitive-op |
|---|---|---|---|---|---|---|
| pilot | 0 | 0 | 0 | 9 | 8 | 3 |
| gold_dev | 50 | 5 | 5 | 21 | 22 | 17 |
| gold_test | 140 | 7 | 3 | 66 | 58 | 26 |

## 2. Support class for every Opus 5 UNSAFE item

Per the labeling instruction, items supported only by `SOURCE_RULE_ONLY_SUPPORT` or `INCOMPLETE_GUARD_EVIDENCE` are UNCERTAIN, not UNSAFE. The framework enforces this structurally: neither class can reach the UNSAFE branch of the decision cascade.

| set | CONCRETE_EXPLOITABLE_PATH | CONCRETE_UNAUTHORIZED_CAPABILITY | STRONG_STATIC_AND_DYNAMIC | SOURCE_RULE_ONLY_SUPPORT | INCOMPLETE_GUARD_EVIDENCE |
|---|---|---|---|---|---|
| pilot | 3 | 8 | 0 | 0 | 0 |
| gold_dev | 19 | 12 | 0 | 0 | 0 |
| gold_test | 45 | 43 | 0 | 0 | 0 |

UNSAFE items resting on weak support: **0**.


## 3. Candidate explanations for the imbalance, checked one by one

| candidate explanation | verdict | evidence |
|---|---|---|
| treating a missing recognized guard as unsafe | NO — an UNSAFE now requires a sensitive operation that survives cutting traversal at every authorization-tainted branch, i.e. a demonstrated unauthenticated path, not an absent pattern | 69/130 UNSAFE items rest on that dominance test |
| decompiler limitations | PARTLY — items whose traversal hit a cap, underflowed, or left a sensitive opcode unreached are pushed to UNCERTAIN, and provenance from a padded stack can no longer support a concrete-exploit claim | 30 items landed UNCERTAIN for this reason |
| incorrect caller/owner extraction | FIXED THIS PASS — the previous analyser never recovered the value a caller check compares against (0 of 268 checks). It now does, which is what separates an owner check from a fixed-third-party check | 68 UNSAFE items turn on a recovered hardcoded literal |
| signature authorization being missed | ADDRESSED — ecrecover-derived branches are recognised as authorization | 28 items credit a signature check |
| self-call authorization being missed | ADDRESSED — msg.sender == address(this) is recognised and treated as the canonical EIP-7702 owner check | 25 items credit a self-call check |
| proxy implementation errors | PARTLY — a DELEGATECALL whose target is read from storage is reported as such, and under EIP-7702 that slot is the EOA's own and empty | 10 UNSAFE items involve a delegatecall |
| source-rule anchoring | CHECKED — see §4; agreement with the source rule is far from total in both directions, so the labels are not tracking the rule | see §4 table |
| repeated bytecode families | CHECKED — see §5; the UNSAFE rate is computed per unique family as well as per item | see §5 table |
| systematic labeling bias | PARTLY MITIGATED — the decision cascade is a single documented procedure applied identically to all 230 items, with every departure recorded in overrides.py; that makes bias auditable, not absent | 5 manual overrides recorded |

## 4. Agreement with the source rule (descriptive only)

| Opus 5 label | source rule = positive | source rule = unflagged |
|---|---|---|
| SAFE | 2 | 29 |
| UNSAFE | 65 | 65 |
| UNCERTAIN | 14 | 55 |

65/81 source-positive items are Opus 5 UNSAFE; 65/149 source-unflagged items are *also* Opus 5 UNSAFE. The second number is the important one: a large share of the UNSAFE labels are on items the source rule never flagged, so these labels are not a restatement of the rule. **This agreement is nevertheless descriptive, not an independent evaluation** — see §7.

Assessment of the analyzer's own verdict per item:

| assessment of the source-rule verdict | count |
|---|---|
| CONFIRMED | 203 |
| CONTRADICTED | 15 |
| PARTIALLY_CONFIRMED | 12 |

## 5. Family-level check (is the imbalance a duplicate-bytecode artefact?)

| set | items | unique families | UNSAFE per item | UNSAFE per family |
|---|---|---|---|---|
| pilot | 20 | 19 | 11/20 (55%) | 10/19 (53%) |
| gold_dev | 60 | 59 | 31/60 (52%) | 31/59 (53%) |
| gold_test | 150 | 126 | 88/150 (59%) | 70/126 (56%) |

The per-family rate tracks the per-item rate closely, so the imbalance is not produced by a handful of duplicated bytecodes.


## 6. What the population actually is

A high UNSAFE rate is expected here and is not by itself evidence of a labeling fault. The sampling frame is the AuthGuardBench-7702 primary population, whose positive class is *defined* as delegates with an external call reachable from `receive()`/`fallback()`, and whose negative class is the rule-silent complement of the same observed-delegate pool with, in the dataset audit's own words, **no benignity verification of any kind**. Gold-Test is population-proportional over that frame (50 positive / 100 unflagged) and Gold-Dev deliberately oversamples informative strata. Many of these delegates are bare executor/forwarder contracts whose whole purpose is to let some party direct calls from the account — which, as an EIP-7702 delegate, is exactly the hazard.


## 7. Static-analyzer comparison limitation (binding)

Because these labels were produced with the source static analyzer's verdict and its per-address rule facts visible:

- the source analyzer **contributed evidence to the provisional reference decision**;
- any static-rule agreement metric computed against these labels is **descriptive**, not an independent evaluation of the analyzer;
- an independent comparison requires the later human-final labels;
- **final paper claims must be regenerated using `human_final_label`.**

This limitation is repeated verbatim in every downstream report produced from these labels.


## 8. Residual risks in these labels

- Memory provenance is not tracked, so a call to a fixed target with a memory-assembled payload cannot be shown to be attacker-controllable; such items are capability findings and never UNSAFE on that basis alone.
- Guard *strength* is not verified: the analyser proves a branch depends on CALLER/ORIGIN/ecrecover/storage, not that it reverts on failure.
- The `hardcoded caller ⇒ third-party access` rule is the single most consequential judgement in this pass. It is right for a delegate and wrong for an ordinary contract, and it is the reason many previously-SAFE items are now UNSAFE. A callback exemption is applied where the entry point is callback-shaped or the address is a recognised protocol contract, but that exemption list is short and certainly incomplete.
- On-chain state (verification status, storage, implementation pointers) is a 2026-07-30/31 snapshot reused from the previous pass.

