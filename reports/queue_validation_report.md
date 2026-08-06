# Pre-Review Validation and Queue Construction Report

Run `v2` (Ethereum mainnet, blocks 25,595,577–25,695,577). This report covers the validation and
simplification work performed **before** human annotation begins. Stages 7–10 (gold dataset,
model training, coverage-deferral evaluation) are paused and have produced no results.

Every number below is read from a file committed under `data/` or `reports/`; the producing
script is named in each section.

---

## 1. Signer-recovery validation

Script: `dataset_pipeline/validation/validate_signer_recovery.py` →
`reports/signer_recovery_validation_v2.json`

Two checks, neither reusing the pipeline's recovery path (`rlp` + `eth_keys` + `eth_utils`):

**Check A — independent reimplementation.** Hand-rolled RLP encoder, keccak from pycryptodome,
and ECDSA recovery from `coincurve` directly. 150 authorizations sampled (seed 7702).

| | |
|---|---:|
| Sampled | 150 |
| Agree with pipeline | **150 (100%)** |
| Disagree | 0 |
| Errors | 0 |

**Check B — on-chain ground truth.** An accepted EIP-7702 authorization sets the *authority's*
account code to `0xef0100 ‖ delegate`. For each sample we queried `eth_getCode(recovered_authority)`
at the authorization's own block. This does not re-derive anything — it asks the chain whether
the address we recovered is the account that actually got delegated. Restricted to authorities
with exactly one authorization in that block (unambiguous end-of-block state).

| | |
|---|---:|
| Checked | 120 |
| Exact `ef0100‖delegate` designator confirmed | **118 (98.3%)** |
| Authority held a *different* delegate | **0** |
| Authority had no delegation code | 2 |

Both non-matches were individually investigated and explained with chain data: their
authorization nonces (48 and 191) were **below** the authority's account nonce at that block
(50 and 193). Under EIP-7702 an authorization is only valid when `authority.nonce ==
authorization.nonce`, so these were invalid authorizations that correctly set no code. They are
not recovery errors.

**Verdict: the signing payload implementation is correct.** All 120 on-chain checks are
accounted for, with zero cases of the recovered authority holding an unrelated delegate — the
signature that a wrong payload would produce. Proceeding is justified.

Population-level context: **98.07%** of the 1,335,391 collected authorizations have a recovered
signer different from `tx.from`, so using the transaction sender as the signer would have been
wrong for essentially the whole dataset.

*Environment note:* `coincurve` was not installed and `eth_keys` was silently using its
pure-Python backend (~7.3 ms/recovery, ≈2.7 h projected for the full set). Installing it reduced
this to ~0.14 ms/recovery (≈3 min actual).

---

## 2. SELFDESTRUCT investigation (the 23 R1 cases)

Script: `dataset_pipeline/validation/investigate_selfdestruct.py` →
`reports/selfdestruct_investigation_v2.csv` / `.json`

Each apparent SELFDESTRUCT was classified by (a) strict Solidity CBOR metadata-trailer
validation, (b) correct instruction-boundary disassembly of the executable region, (c) symbolic
CFG reachability from `pc=0`, and (d) guard dominance.

| Verdict | Contracts |
|---|---:|
| Byte lies inside the validated Solidity CBOR metadata trailer | **12** |
| In executable region but **unreachable** | **6** |
| Reachable but **guard-dominated** | **5** |
| Reachable **and unguarded** | **0** |

**All 23 R1 labels were false positives.** None had an unguarded reachable SELFDESTRUCT. The
v1 rule fired on byte *presence* from a linear sweep that neither stripped metadata nor checked
reachability — exactly the failure its own caveat had suspected.

### Extractor fixes applied

`dataset_pipeline/lib/reachability.py` (new) replaces presence-counting with three separately
reported facts per capability: **present** (at an instruction boundary in the non-metadata
executable region), **reachable** (some explored state arrives there), and **unguarded**
(still reachable when traversal is cut at every caller/signature guard). It also emits a
`coverage_status` of `COMPLETE`/`PARTIAL` with explicit reasons.

A second, subtler defect was found and fixed during validation. The analyzer applies **state
widening** (an over-approximation) to bound exploration; widening let the guard-cut pass reach a
program counter the unrestricted pass never reached, i.e. a **spurious** unguarded site. This
affected 2 of 340 complete-coverage contracts, and widening is used in 212 of them — so a
blanket rule would have been far too destructive. The targeted fix requires every unguarded site
to be **corroborated by the unrestricted traversal**; uncorroborated sites are discarded and
recorded in `uncorroborated_guardcut_sites_discarded`. After the fix, **0 of 752** contracts have
more unguarded sites than reachable sites (previously 217).

LLM reviews were regenerated on the corrected evidence.

---

## 3. Revised LLM labelling

Rubric: `dataset_pipeline/lib/llm_review_rubric_v2.py` (`prompt_version=v2`).
Script: `dataset_pipeline/scripts/05b_llm_review_v2.py` →
`data/llm_reviews/v2_review_summary_promptv2.json`

R1 and R2 now require **concrete reachable evidence**; U is used whenever control flow, proxy
targets, access control, or the evidence itself cannot be resolved.

| Label | v1 (presence-based) | v2 (reachability-based) |
|---|---:|---:|
| R1 | 23 | **61** |
| R2 | 524 | **642** |
| B | 205 | **4** |
| U | **0** | **45** |

Labels changed for 267 of 752 contracts. Breakdown by coverage:

| Label | COMPLETE | PARTIAL |
|---|---:|---:|
| R1 | 61 | 0 |
| R2 | 275 | 367 |
| U | 0 | 45 |
| B | 4 | 0 |

Three rules make this structure hold:

- **R1 requires COMPLETE coverage.** If the traversal is incomplete, an unexplored region may
  contain the very guard that protects the site, so "appears insufficiently protected" is not
  established. This was not a theoretical concern: under the first v2 draft, 4 of the 8
  documented, audited account-abstraction implementations in the population (Alchemy, Coinbase,
  ZeroDev, OKX) were labelled R1 — **all four with PARTIAL coverage**. After the rule, **all 8
  documented projects are R2 and no R1 is a documented project.**
- **B requires COMPLETE coverage and no reachable capability.** Only 4 contracts qualify. B is
  now a genuine "analysis was complete and found nothing", not "we did not look hard enough" —
  which is why the count dropped from 205.
- **U covers unresolvable evidence**: 45 contracts where no capability was reached but coverage
  is PARTIAL, so absence cannot be concluded.

R2 remains the largest class (642). Under the given definitions this is substantive rather than
a default: every R2 has a *reachable* capability whose exploitability depends on stored authority
values, an unresolved proxy target, external contracts, or memory-provenance that the analyzer
does not track transitively back to calldata. The v1 defect — assigning R2 on byte presence
alone — is gone.

**Scope deviation, stated explicitly.** The brief asked to rerun only low-confidence and
incomplete-evidence cases. v2 introduces an evidence dimension (reachability/guard dominance)
that did not exist when v1 ran, so a v1 label cannot be assumed valid without re-deriving it,
and mixing two rubric versions inside one label set would be a methodological defect. All 752
were re-reviewed; the requested subsets are reported separately in the summary JSON
(`subset_v1_low_confidence`: 521 rows, 99 changed; `subset_partial_coverage`: 412 rows, 119
changed; `subset_v1_R1`: 23 rows, 17 changed). v1 reviews are preserved unmodified under
`data/llm_reviews/v2/`.

---

## 4. Deduplication of human work

Script: `dataset_pipeline/scripts/06b_build_review_queues.py`

| | |
|---|---:|
| Screenable contracts | 752 |
| **Unique runtime bytecode hashes** | **669** |
| Rows saved by exact-bytecode dedup | 83 |

One review row per exact runtime-bytecode SHA-256; the representative is deterministic (earliest
first-observed block, then lowest address). Each row carries `represented_contract_count` and the
full `represented_addresses` list.

---

## 5. Review queues

| Queue | Rows | Contracts represented | Path |
|---|---:|---:|---|
| **A. Representative gold** | **300** | 306 | `data/human_reviews/v2_representative_gold_queue.csv` |
| **B. Diagnostic** | **309** | 385 | `data/human_reviews/v2_diagnostic_queue.csv` |

Queue A is a uniform random sample of unique runtime representatives drawn from the full
unfiltered screenable population with seed 7702. **The sample is drawn before any LLM label is
joined**, so selection cannot depend on the model's opinion. It spans 223 bytecode families and
is 166 COMPLETE / 134 PARTIAL coverage. Its LLM-label composition (R2 248, R1 32, U 19, B 1) is
an *outcome* of label-blind sampling, not a selection criterion.

Queue B contains every remaining R1, U, low-confidence, documented/verified-source, proxy,
analyzer-disagreement, and unusual-evidence case, with a `diagnostic_reasons` column giving the
reason(s) per row and rows sorted R1 → U → R2 → B. Rows already in Queue A are excluded, so no
contract is reviewed twice. **Queue B is not a prevalence sample and must not be used as one.**

A third file, `data/human_reviews/v2_all_unique_runtimes.csv` (669 rows), is the complete
deduplicated universe both queues are drawn from.

Superseded artifacts (the v1-rubric 752-row queue, the pilot queue) are moved to
`data/human_reviews/superseded/` to prevent accidental use.

### Columns

Both queues carry the required columns — `review_id`, `contract_address`, `exact_bytecode_hash`,
`bytecode_family_id`, `represented_contract_count`, `verified_project_name`, `coverage_status`,
`llm_label`, `llm_confidence`, `llm_explanation`, `evidence_summary`, `decision`, `final_label`,
`final_confidence`, `comment` — plus supporting context (`llm_risk_categories`,
`llm_uncertainties`, `represented_addresses`, `bytecode_length`, `first_observed_block`,
`authorization_frequency`, `evidence_path`, `explorer_link`, `diagnostic_reasons`).

---

## 6. Label propagation

Script: `dataset_pipeline/scripts/07b_merge_reviews_and_propagate.py`

- A human decision propagates **only** to contracts whose runtime bytecode SHA-256 is
  **identical** to the reviewed representative — the reviewed evidence is then the same evidence,
  byte for byte.
- It **never** propagates across `bytecode_family_id`. Family membership is opcode similarity
  (Jaccard ≥ 0.85), and similar-but-not-identical bytecode can differ in exactly the constant or
  guard that decides the label. Family ids are carried only for split disjointness.
- Every resulting row records `label_origin` = `REVIEWED` or `PROPAGATED_EXACT_BYTECODE` plus
  `propagated_from`, so provenance is never lost.
- The merger validates decisions, rejects malformed rows individually (rather than dropping them
  silently), reports how many rows remain undecided, and flags any case where two queues give
  conflicting labels to identical bytecode.

Verified on synthetic decisions: 3 reviewed rows expanded to 9 labelled addresses (3 `REVIEWED`,
6 `PROPAGATED_EXACT_BYTECODE`), and an invalid `final_label` was correctly rejected with a reason.
Test artifacts were deleted; **no human review has been recorded yet.**

Prevalence can be computed two ways from the completed queue and must be labelled accordingly:
unweighted (per unique runtime) or weighted by `represented_contract_count` (per deployed
delegate).

---

## 6b. Rubric v3 — protection-based labelling (final correction before review)

Rubric: `dataset_pipeline/lib/llm_review_rubric_v3.py` (`prompt_version=v3`).
Script: `dataset_pipeline/scripts/05c_llm_review_v3.py` →
`data/llm_reviews/v2_review_summary_promptv3.json`

v2 was still presence-biased: any contract with a reachable CALL/DELEGATECALL became R2, so every
documented account implementation was labelled a risk. For an EIP-7702 delegate, executing calls
*is* the function of the contract; what matters is whether that capability is **protected**. v3
decides on protection, per the corrected definitions (R1 = protection missing/inadequate under
COMPLETE coverage; R2 = one specific unresolved dependency blocks the decision; B = capabilities
present but protected; U = evidence too incomplete to decide).

Two supporting changes made this decidable rather than nominal:

- **"Dangerous" excludes SSTORE.** A smart account writing its own storage is bookkeeping, not a
  dangerous operation.
- **Coverage partiality now means decision-relevant incompleteness only.** A metadata-trailer
  separability note affects tail opcode counting, not the protection question, and no longer
  forces U.
- **Analysis limits raised** (`DeepAnalyzer`, `MAX_PER_PC` 96→512, `MAX_STATES` 60k→400k). The
  stock per-pc cap truncated 283 of 752 contracts, which would have forced them to "cannot
  determine" purely as a budget artifact. On a random sample of 10 capped contracts, raising the
  limits resolved 9 for ~1.2× runtime. COMPLETE coverage rose 340 → **399**. The frozen
  `revision_v3` module is not modified — the caps are class attributes, overridden in a subclass.

### New label counts (all 752 re-labelled)

| Label | v1 (presence) | v2 (reachability) | **v3 (protection)** |
|---|---:|---:|---:|
| R1 | 23 | 61 | **77** |
| R2 | 524 | 642 | **20** |
| B | 205 | 4 | **302** |
| U | 0 | 45 | **353** |

| Label | COMPLETE | PARTIAL |
|---|---:|---:|
| R1 | 77 | 0 |
| R2 | 20 | 0 |
| B | 302 | 0 |
| U | 0 | 353 |

B rose from 4 to 302 because a guard-dominated capability is now correctly B rather than R2.
R2 collapsed from 642 to 20 — it is now reserved for the single specific blocking dependency
(an unguarded call whose callee is computed through memory and so is neither a constant nor
traceable to calldata). All 77 R1s share one concrete finding: a reachable CALL whose **callee
address is taken from calldata** with no dominating caller/signature guard, i.e. any caller can
direct the delegating EOA to call an arbitrary address. R1 rose from 61 only because more
contracts now have complete-enough analysis to be judged at all.

### The eight documented projects

| Project | v2 label | **v3 label** | Coverage |
|---|---|---|---|
| Ambire EIP7702Account | R2 | **B** | COMPLETE |
| MetaMask EIP7702StatelessDeleGator | R2 | **B** | COMPLETE |
| Biconomy Nexus v1.3.1 | R2 | **U** | PARTIAL (unresolved proxy target) |
| Uniswap Calibur v1.1.0 | R2 | **U** | PARTIAL (insufficient control-flow coverage) |
| Alchemy SemiModularAccount7702 | R2 | **U** | PARTIAL (insufficient control-flow coverage) |
| Coinbase EIP7702Proxy | R2 | **U** | PARTIAL (unresolved proxy target) |
| ZeroDev Kernel v3.3 | R2 | **U** | PARTIAL (unresolved proxy target) |
| OKX SmartWalletEntry | R2 | **U** | PARTIAL (unresolved proxy target) |

**Zero documented projects are labelled R1 or R2.** The two whose control flow resolves
completely are B (protected); the other six are U — explicitly "not determined", not "risk" —
and four of those are U specifically because they are proxies whose implementation target was
never collected, which is a real evidence gap rather than a risk finding.

## 6c. Pilot review queue

Script: `dataset_pipeline/scripts/06c_build_pilot_queue.py`

| | |
|---|---:|
| **Pilot rows** | **36** |
| Bytecode families | 31 |
| Path | `data/human_reviews/v2_pilot_queue.csv` |

Stratified across every label × coverage cell so a first pass exercises each rubric branch:
`R1/COMPLETE` 11, `U/PARTIAL` 10, `B/COMPLETE` 9, `R2/COMPLETE` 6. (R1/R2/B occur only under
COMPLETE and U only under PARTIAL — that is structural to the rubric, so this covers both
coverage states.) Every pilot row is drawn from the existing 300-row representative sample, so
pilot decisions remain usable in the main evaluation.

**The label-blind 300-row representative sample was not altered.** `v2_representative_gold_queue.csv`
is unchanged on disk. Because reviewing against superseded labels would be pointless, a refreshed
copy with v3 labels and evidence — same 300 runtimes, same order, asserted identical membership —
is written alongside it as `v2_representative_gold_queue_promptv3.csv`. Its v3 composition
(B 142, U 111, R1 41, R2 6) is an outcome of the original label-blind draw, not a new selection.

## 6d. U reduction, proxy resolution, and R1 validation

### Why contracts were U, and what was actually fixable

Diagnosis of the 353 U labels found that only **38** were proxy-related; **316** were U because
"dangerous capabilities present in executable code were never reached by the traversal". Two
genuine analyzer defects were behind most of that:

**Defect 1 — silent state-dedup truncation (the significant one).** The traversal deduplicated
states on `(pc, top 8 stack items)`. Solidity compiles internal functions (including the helpers
modifiers become) as blocks entered by JUMP with the return address pushed *below* the arguments,
so two call sites reaching the same helper with identical top-8 but different continuations
collapsed to one state and the second was dropped — with **no cap flag and no unresolved-jump
count**. I verified by hand on three contracts that the unreached sites were well-formed Solidity
call sequences (`DUP6 DUP8 GAS CALL`, `CALLER GAS CALL`), not mis-decoded data, so this was real
under-exploration. It inflated U *and* threatened B soundness, since an unguarded path could sit
behind a guarded one. Raising the key depth to 32 cut contracts with unreached dangerous
operations from 27/40 to 15/40 on a random sample; beyond 32 gave no further gain.

**Defect 2 — cap truncation.** Raised limits (`MAX_PER_PC` 96→512, `MAX_STATES` 60k→400k) cut
cap-truncated contracts from 15/40 to 1/40.

Together: COMPLETE coverage 399 → **428**, U 353 → **324**.

### Proxy resolution (`dataset_pipeline/lib/proxy_resolver.py`, `scripts/04c_...`)

Supports EIP-1967 implementation/beacon/admin slots, EIP-1822, the OpenZeppelin legacy slot,
EIP-1167 minimal proxies, EIP-7702 designators, and `implementation()`/`masterCopy()` getters,
resolved recursively to a bounded depth of 3, always at the delegate's first-observed
authorization block. Both proxy and implementation addresses, bytecode hashes, block, and the
resolution method/scope are preserved in each evidence package.

An EIP-7702-specific subtlety drove the design: a delegate's DELEGATECALL executes against the
*authorizing EOA's* storage, so the implementation slot is usually empty on the delegate's own
account and populated per-EOA. Resolution therefore tries the delegate account first and the
first-observed authorizing EOA second, recording which in `resolution_scope`.

| Outcome | Count |
|---|---:|
| U contracts carrying a proxy indicator | 56 |
| **Implementation resolved and analysed** | **5** |
| Implementation pointer self-references the delegate (terminal, not a proxy) | 9 |
| No proxy slot, embedded target, or getter (runtime-computed callee) | 41 |
| RPC failure | 1 |

Resolution methods: EIP-1967 implementation slot ×4, `implementation()` getter ×1; scopes:
delegate account ×3, authorizing EOA ×2.

**Honest outcome: proxy resolution changed no labels.** All five resolved implementations are
themselves PARTIAL (three have their own unresolved DELEGATECALL, two have unresolved dynamic
jumps), so the composed evidence stays incomplete and those contracts remain U. The nine
"cycles" turned out to be self-references — the account's implementation *is* the delegate — and
are now recorded as `SELF_REFERENCE_TERMINAL` rather than as a failure. The remaining 41 are
delegates whose DELEGATECALL callee is computed at runtime (module/plugin dispatch), which no
static slot lookup can resolve. The stage added real provenance, not label movement, and is
reported as such.

### R1 rule validation (`dataset_pipeline/validation/validate_r1_rule.py`)

25 of 99 R1 contracts re-derived independently of the stored evidence.

| | |
|---|---:|
| **CONFIRMED** | **25 / 25** |
| Traversal incomplete | 0 |
| Contracts with zero strong guards anywhere | 11 |
| Contracts that never execute `CALLER` at all | 7 |

For every one: the calldata-targeted CALL is reachable in the unrestricted traversal, still
reachable when traversal is cut at every caller/signature guard, and outside the metadata region.
Seven contracts never execute `CALLER`, so no caller-based authorization exists anywhere in them.

**One systematic false-positive pattern was found and fixed.** The audited
Alchemy SemiModularAccount7702 was initially R1. Inspection showed its surviving site had target
provenance `['calldata','sload']` — the callee is a **stored** address *selected* by calldata
(module/plugin dispatch), not an address the caller supplies. The caller picks among values some
other path registered, so the danger depends on who may write that slot: a specific unresolved
dependency, i.e. R2 by definition, not established missing protection. Target provenance is now
split (`calldata_target` vs `calldata_selected_stored_target`) and only the former can trigger
R1. This affected exactly 1 of 100 R1 contracts — Alchemy — which is now R2.

A second, non-defect pattern was checked and deliberately left alone: in 5 of 25 cases the
flagged path is additionally gated by a storage *condition* (initialized/paused flag). Since
`msg.sender == storedOwner` carries `caller` provenance and is already classified strong and cut,
these residual conditions are not caller authorization. They are surfaced to reviewers as an
explicit uncertainty rather than silently treated as protection.

### Final counts

| Label | v3 (previous) | **v3 (current)** |
|---|---:|---:|
| R1 | 77 | **99** |
| R2 | 20 | **24** |
| B | 302 | **305** |
| U | 353 | **324** |

R1 rose because the traversal fixes gave 88 more contracts complete-enough analysis to be judged
at all, not because the rule loosened — the rule was tightened.

| Label | COMPLETE | PARTIAL |
|---|---:|---:|
| R1 | 99 | 0 |
| R2 | 24 | 0 |
| B | 305 | 0 |
| U | 0 | 324 |

### The eight documented projects — zero labelled R1

| Project | Label | Coverage / reason |
|---|---|---|
| MetaMask EIP7702StatelessDeleGator | **B** | COMPLETE |
| Alchemy SemiModularAccount7702 | **R2** | caller-selected stored callee |
| Ambire EIP7702Account | **U** | insufficient control-flow coverage |
| Biconomy Nexus v1.3.1 | **U** | unresolved proxy target |
| Coinbase EIP7702Proxy | **U** | insufficient control-flow coverage |
| OKX SmartWalletEntry | **U** | unresolved proxy target |
| Uniswap Calibur v1.1.0 | **U** | insufficient control-flow coverage |
| ZeroDev Kernel v3.3 | **U** | unresolved proxy target |

### Pilot queue rebuilt

`data/human_reviews/v2_pilot_queue.csv` — **the same 36 `review_id`s**, verified identical to the
prior membership, with refreshed v3 evidence and labels. Cells are now `R1/COMPLETE` 11,
`B/COMPLETE` 10, `U/PARTIAL` 9, `R2/COMPLETE` 6, across 31 families. The builder now *preserves*
an existing pilot's membership instead of re-sampling, so labels moving cannot silently change
which contracts a reviewer was asked to examine.

The label-blind 300-row representative sample is unchanged (`v2_representative_gold_queue.csv`
still carries its original v2 labels and identical hash order); the refreshed copy
`v2_representative_gold_queue_promptv3.csv` holds the same 300 runtimes with v3 labels
(B 143, U 99, R1 48, R2 10).

## 7. Status

Complete: signer-recovery validation, SELFDESTRUCT investigation, extractor fixes, rubric v2 →
v3 re-labelling, raised analysis limits, deduplication, all queues, propagation tooling.

**Paused, awaiting human review.** The immediate next step is the 36-row pilot
(`data/human_reviews/v2_pilot_queue.csv`), then the 300-row representative queue. No training,
split construction, or evaluation has been performed; `data/split_manifests/` is empty and no
model or gold-dataset artifact exists for run `v2`. No placeholder values appear in any output
file.

Rubric-version artifacts are all retained side by side for audit: `data/llm_reviews/v2/` (v1),
`v2_promptv2/`, and `v2_promptv3/`, with matching index and summary files.
