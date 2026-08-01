# LLM Provisional Labeling Protocol

**Status: LABEL_SOURCE=LLM_PROVISIONAL. These are not human labels, expert labels, gold
labels, ground truth, or independently verified labels.** They are a documented, reproducible
provisional reference used to develop and exercise the full research pipeline while human
review (`revision_v3/human_eval/Pilot_Code_Review.xlsx` and its Gold-Dev/Gold-Test
counterparts) proceeds separately, on its own timeline.

This is the single protocol used consistently across the Pilot (20 items), Gold-Dev (60
items), and Gold-Test (150 items) sets. Every provisional label produced anywhere in
`revision_v3/` traces back to this document.

## Model identifier and generation date

- Model: Claude (Sonnet 5)
- Protocol authored / first applied: 2026-07-30 (Pilot), extended to Gold-Dev and Gold-Test
  2026-07-30/31
- Each generated record carries its own `generated_at_utc` timestamp; this document is the
  fixed methodology, not a per-run log.

## Two-stage process

1. **Automated evidence collection** (deterministic, no LLM judgment): live verified-source
   checks (Sourcify v2, Blockscout v2), proxy/implementation resolution (`eth_getStorageAt`
   at the EIP-1967 slot and, for Safe-style proxies, slot 0), full `evmole` decompilation
   (disassembly with byte offsets, resolved selectors via 4byte.directory, storage layout),
   ASCII-string and address-constant extraction, and an automated **guard tracer**
   (`revision_v3/experiments/excel_review/guard_tracer.py`) that follows every dispatched
   function's jump target and classifies its entry as `GUARDED` (a `CALLER`/`ORIGIN`
   comparison feeds a `JUMPI`/`REQUIRE`-style branch, with the compared constant extracted),
   `OPEN` (no such comparison found anywhere reachable from the entry, confirmed by
   exhaustively scanning the function body), or `AMBIGUOUS` (the guard tracer could not
   resolve the control flow, e.g. non-standard dispatch, deeply nested jumps, or a guard that
   depends on unresolved external state).
2. **LLM judgment**, applied only on top of the stage-1 structured evidence: given the
   automated findings for one item, the model assigns `llm_provisional_label`,
   `llm_provisional_reason_category`, `llm_provisional_confidence`, and writes the analysis
   fields below. The model is never shown raw bytecode without the structural findings
   already computed, and never asked to re-derive what the guard tracer already determined
   deterministically — it interprets and contextualizes, it does not re-discover.

## Input evidence fields available to the LLM

- `chain`, `address`, `runtime_bytecode_length_bytes`, `explorer_link`
- `verified_source_status` (`VERIFIED` / `NOT_VERIFIED`, with provider and, if verified,
  contract name + compiler version)
- `implementation_resolution` (proxy type, resolution method, resolved address if any,
  whether the resolved address itself was decompiled)
- `dispatched_functions` (selector, resolved signature if 4byte.directory has a match,
  bytecode offset, state mutability)
- `guard_tracer_results` per dispatched function: `GUARDED` (with the compared address
  constant and the offset of the comparison) / `OPEN` / `AMBIGUOUS`, plus which opcode
  (`CALLER` vs `ORIGIN`) was used when guarded
- `storage_layout` (slot count, read/write counts per slot)
- `ascii_strings` extracted from the raw bytecode (revert reasons, etc.)
- `address_constants` found in the bytecode
- `known_project` (name + documentation URL) **only when independently confirmed** via a
  verified-source project match or an official deployment registry — never inferred from a
  name alone

## Forbidden fields (never shown to the labeling LLM)

`source_rule_label`, `authguard_score`, `authguard_prediction`, `raw_score`,
`calibrated_score`, `model_score`, `is_false_positive`, `is_false_negative`,
`gold_dev_stratum`, `gold_test_sampling_metadata`, `pilot_reason`, any `family_id`-derived
hint about how the item was sampled, and any prior label from any other source (source-rule,
a different LLM pass, or a human reviewer). Enforced structurally: the evidence-packet
builder (`revision_v3/src/evidence/packet_builder.py`) and the new
`revision_v3/experiments/excel_review/guard_tracer.py` / labeling scripts never read these
columns from the manifests when constructing the LLM-facing evidence object — this is a
schema-level omission, not a runtime filter, so there is no code path that could leak them.

## Label taxonomy

| Label | Definition |
|---|---|
| SAFE | The evidence supports that sensitive actions are appropriately restricted and no concrete EIP-7702 authorization-related danger was identified. |
| UNSAFE | The evidence identifies a concrete dangerous condition that can make EIP-7702 authorization unsafe. |
| UNCERTAIN | The available evidence is insufficient, ambiguous, unresolved, or dependent on unavailable state. |

### UNSAFE reason categories
`MALICIOUS_OR_DRAINER`, `UNAUTHORIZED_ASSET_MOVEMENT`, `DANGEROUS_APPROVAL_OR_TRANSFER`,
`ARBITRARY_EXTERNAL_CALL`, `UNSAFE_INITIALIZATION`, `OWNER_OR_PRIVILEGE_TAKEOVER`,
`DANGEROUS_DELEGATECALL_OR_UPGRADE`, `TX_ORIGIN_AUTHORIZATION_RISK`,
`UNRESTRICTED_CONTRACT_CREATION`, `AUTHORIZATION_SPECIFIC_MISUSE`, `OTHER_UNSAFE`

### SAFE reason categories
`DOCUMENTED_LEGITIMATE_IMPLEMENTATION`, `OWNER_OR_SELF_CALL_RESTRICTED`,
`SIGNATURE_AUTHORIZATION_CONFIRMED`, `ACCESS_CONTROL_APPEARS_APPROPRIATE`,
`INITIALIZATION_APPEARS_SAFE`, `UPGRADE_AUTHORIZATION_APPEARS_SAFE`,
`NO_CONCRETE_DANGEROUS_PATH_FOUND`, `OTHER_SAFE`

### UNCERTAIN reason categories
`UNRESOLVED_PROXY`, `EXTERNAL_OR_DYNAMIC_DEPENDENCY`, `STATE_DEPENDENT_BEHAVIOR`,
`DECOMPILATION_AMBIGUITY`, `NO_RUNTIME_CODE`, `FUTURE_OR_COUNTERFACTUAL_CODE`,
`INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, `OTHER_UNCERTAIN`

## Confidence taxonomy

`high` / `medium` / `low` — `high` requires every sensitive function's guard status to be
individually resolved (not `AMBIGUOUS`) by the automated tracer; `low` is used whenever the
tracer left any sensitive function `AMBIGUOUS` or the item's own complexity (very large
contract, non-standard dispatch) limited how much could be responsibly traced.

## Output schema (per item)

```
item_id, llm_provisional_label, llm_provisional_reason_category, llm_provisional_confidence,
contract_purpose, sensitive_functions, access_control_analysis, initialization_analysis,
proxy_and_upgrade_analysis, asset_operation_analysis, authorization_specific_analysis,
concrete_finding, evidence_references, unresolved_questions,
alternative_plausible_label, alternative_label_condition
```

`access_control_analysis` covers general caller/owner restriction findings.
`authorization_specific_analysis` is EIP-7702-specific: does the guard pattern make sense
for an account-delegation context (e.g. `ADDRESS()==CALLER()` self-call checks, which are
meaningful specifically because `ADDRESS()` returns the EOA's own address under 7702), and
are there authorization-specific misuse patterns (tx.origin auth, unrestricted
initialization that would let a front-runner claim ownership before the real authorizer's
first transaction, etc.)?

## Full field separation (maintained at every stage)

Every record — Pilot, Gold-Dev, Gold-Test, and later temporal items — carries all eight
fields, never fewer:

```
source_rule_label, llm_provisional_label, llm_provisional_confidence, llm_provisional_reason,
human_final_label, human_final_confidence, human_final_reason, human_review_status
```

`human_final_label` is never populated by any script in this pipeline and is never copied
from `llm_provisional_label`. `human_review_status` defaults to `NOT_REVIEWED` for every
item until a human reviewer's workbook import changes it (allowed values: `NOT_REVIEWED`,
`UNDER_REVIEW`, `FINAL_SAFE`, `FINAL_UNSAFE`, `FINAL_UNCERTAIN`).

## Retry policy

Each item is processed once per pipeline run. If the automated evidence-collection stage
(source check, decompilation, guard tracing) fails for an item (network error, decompiler
exception), that failure is recorded verbatim in the item's evidence record
(`evidence_collection_error`) and the item is labeled `UNCERTAIN` /
`INSUFFICIENT_EVIDENCE` — it is not silently skipped, and it is not retried with degraded
evidence substituted invisibly. A single automatic retry (network calls only, not the LLM
judgment step) is permitted for transient HTTP/RPC errors.

## Uncertainty policy

When the guard tracer returns `AMBIGUOUS` for any function whose capability (asset
transfer, arbitrary call, contract creation, self-destruct, delegatecall/upgrade) would be
severity-relevant if unguarded, the item defaults toward `UNCERTAIN` unless a different
sensitive function on the same item provides an independently sufficient, unambiguous
UNSAFE finding. Confidence is capped at `low` whenever any material `AMBIGUOUS` result
remains.

## Evidence-citation requirement

Every factual claim in `access_control_analysis`, `initialization_analysis`,
`proxy_and_upgrade_analysis`, `asset_operation_analysis`, `authorization_specific_analysis`,
and `concrete_finding` must cite one of:
- a verified-source file and function/line, or
- a decompiled function and bytecode offset, or
- on-chain storage evidence (slot + resolved value), or
- official project documentation (only when `known_project` was independently confirmed).

## Hard rules

- Do not label UNSAFE solely because CALL, DELEGATECALL, SELFDESTRUCT, CREATE, fallback,
  receive, token selectors, or unverified code exists — the guard tracer's `GUARDED`/`OPEN`
  finding on the specific capability is what matters, not the capability's mere presence.
- Do not label SAFE solely because a known project name or documentation exists — the
  underlying selector/guard evidence must independently support it.
- `tx.origin` use is not automatically UNSAFE — identify the concrete exploitable path (does
  the guarded function reach an irreversible or asset-moving operation? is the check the
  *only* authorization mechanism?) before applying `TX_ORIGIN_AUTHORIZATION_RISK`.
- Interface or selector similarity to Safe or another known wallet is not sufficient to
  establish identity or safety — it is reported as a structural observation
  (`DOCUMENTED_LEGITIMATE_IMPLEMENTATION` requires independently verified source, not
  selector-set matching alone; selector-matching-only findings use
  `ACCESS_CONTROL_APPEARS_APPROPRIATE` or remain `UNCERTAIN` with the caveat stated).
- An absence-of-caller-check claim (`OPEN`) must be supported by the guard tracer's
  confirmation that it exhaustively scanned the relevant entry path's reachable body, not a
  truncated prefix.
- When evidence is insufficient, use UNCERTAIN. There is no confidence or completeness
  penalty for doing so.

## Quality checks (run automatically after generation)

1. Schema completeness: every one of the 16 output fields is present and non-null for every
   item.
2. Label/reason-category consistency: `llm_provisional_reason_category` is a member of the
   list for the assigned `llm_provisional_label`.
3. Forbidden-field absence: none of the forbidden fields appear anywhere in the evidence
   object passed to the LLM step (checked structurally, not just in the output).
4. Evidence-citation presence: `concrete_finding` contains at least one of a bytecode offset
   (`offset \d+`), a storage-slot reference, a file:line reference, or an explicit
   `INSUFFICIENT_EVIDENCE`/`UNCERTAIN` statement.
5. No raw full bytecode reproduced verbatim in any narrative field (only short, cited
   snippets/pseudocode).
6. `human_final_label` is null/blank for every generated record; `human_review_status` is
   `NOT_REVIEWED` for every newly generated record.
7. Confidence/ambiguity consistency: no item has `llm_provisional_confidence=high` while any
   of its sensitive functions is `AMBIGUOUS` in the guard tracer output.

These checks are implemented in
`revision_v3/tests/test_provisional_labeling_pipeline.py` and run as part of the standard
test suite.
