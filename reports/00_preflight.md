# Preflight — AuthGuardBench-7702 Ground-Truth Work Order

Date: 2026-07-28. Branch `claude-revision-3` @ `a63e5f8`.
Frozen-artifact guard: `python3 revision_v2/experiments/common/frozen.py verify` →
**OK: 144 frozen files verified unchanged** (checked before and after; nothing modified).

Every number below was produced by direct inspection or a live network call during this
preflight, not copied from existing documentation. Where I am repeating a prior finding I
say so and state whether I re-verified it.

---

## Headline result

**The central question this work order was written to answer has already been answered, in
the negative, and documented in-repo: all 727 positive labels are a deterministic function
of the runtime bytecode the model consumes** (`revision_v2/audit/DATASET_AUDIT_REPORT.md`,
2026-07-18, Part 2). The remaining blocker is that **the behavioral ground truth §3 depends
on cannot be collected as specified**: there are no Etherscan/Dune/Alchemy credentials
anywhere in the repo or environment, only 29% of the corpus is on Ethereum mainnet, and
enumerating type-0x04 authorizations by brute block scan measures at **~5 days per chain,
single-threaded, for Ethereum alone** at the throughput I measured.

## Status

**PARTIAL — proceed to Task 0, but §3 needs a scope decision from you before it starts.**

Task 0 (both gates) is unblocked, not duplicated by existing work, and can run on frozen
folds today. Task 1 is blocked on a credential decision and a corpus-scope decision. Task 2
must not be built until that resolves, per the work order's own rule.

---

## 1. What is in the benchmark today

Primary artifact: `revision_v2/data/authguardbench_7702_v2.csv.gz` — 3,082 rows × 29 columns.

| population | rows | note |
|---|---:|---|
| `PRIMARY_EVALUATION` | **2,190** | 727 positive / 1,463 negative — the modeled task |
| `EXTERNAL_BENIGN_CONTROL` | 797 | PhishingHook general contracts, **not** 7702 delegates |
| `EXCLUDED_UNCERTAIN_INPUT` | 90 | Excel-truncated bytecode, repaired, verdict untrustworthy |
| `QUALITATIVE_CONTROL` | 5 | curated legitimate delegates |

Within `PRIMARY_EVALUATION`:

- 2,190 rows but only **1,972 unique addresses** and **1,665 unique bytecodes**. The unit is
  a (chain, address) pair, not a distinct delegate. The work order's "~2,190 observed
  delegates" overstates distinct delegates by ~11%.
- **790 families**; 477 singletons (60%), 91 families with ≥5 members, max size 58, median
  size 1. Rows living in families of ≥5: 1,147 (52%).
- Positives occupy **209 families**; 25 families carry mixed labels.
- `label_strength` is only ever `C_source_rule_only` (727) or `C_source_unflagged_weak`
  (1,463). There is no tier above C in the primary task.
- **`flag_independent_behavioral_evidence` is set on exactly 1 row.** That is the entire
  stock of non-circular positive evidence in the benchmark today.

### Chain distribution — this contradicts the work order's assumptions

| chain | rows | positives |
|---|---:|---:|
| ethereum | 643 | 232 |
| bnb | 558 | 163 |
| base | 483 | 140 |
| optimism | 212 | 99 |
| arbitrum | 149 | 52 |
| polygon | 99 | 29 |
| gnosis | 46 | 12 |

**Only 29% of the primary corpus is Ethereum mainnet** (366 of 790 families touch Ethereum).
§3.2 (Dune EIP-7702 tables), §3.4 (Etherscan tags), and §3.5 ("all type-0x04 set-code
transactions on mainnet") are all written as if this were a mainnet-only corpus.

---

## 2. How families were constructed — reproducible, yes

`pipeline/01_freeze_families.py`, frozen into `family_assignment_frozen.csv` (3,258 rows).

- Deterministic MinHash (blake2b, seeded; explicitly not Python `hash()`, so
  `PYTHONHASHSEED`-independent) over **opcode 4-grams**, union-find over all pairs with
  estimated Jaccard ≥ threshold.
- **Frozen threshold 0.85.** Alternates at 0.75 and 0.90 are retained in the frozen CSV as
  `family_id_075` / `family_id_090`, so threshold sensitivity is already available.
- Clustering is global across classes and chains — cross-class families are deliberately kept
  intact so they cannot straddle a fold.

Reproducible from repo code. The rationale (three progressively stronger family definitions,
D1 PUSH-skeleton / D2 selector-set / D3 4-gram MinHash) is in `bracket_family_count.py`.

**Consequence for Gate 0B:** the MinHash machinery the gate calls for already exists and is
frozen. Gate 0B must use an *independently built* index over training folds only — reusing
`family_id` would leak, because families were computed globally over all rows including test.

---

## 3. Are the CV folds frozen and family-disjoint? — verified by direct check

I did not trust the documentation. Direct computation on the v2 primary population:

| assertion | result |
|---|---|
| families spanning >1 fold | **0** |
| exact bytecode hashes spanning >1 fold | **0** |
| folds present | 0–4, sizes 446 / 446 / 427 / 447 / 424 |

Both hold. **Confirmed family-disjoint and exact-bytecode-disjoint.**

One thing the documentation does not flag: **fold positive prevalence is badly uneven** —
0.341 / 0.327 / 0.340 / **0.208** / **0.450**. Fold 3 has 93 positives, fold 4 has 191. Any
per-fold metric is noisier than the pooled numbers suggest, and this is a live contributor to
the seed spread reported in `BASELINE_FINAL_SUMMARY.md`. Worth stating in the paper; not a
validity problem.

Canonical evaluation entrypoint is `revision_v2/experiments/baseline_v2/run_baseline_v2.py`
— benchmark = the v2 gz, folds = `fold_id`, seeds = **7702 / 7703 / 7704**. That is the
protocol Gate 0A and 0B must match exactly. Note the older shared harness
(`experiments/common/harness.py::load_corpus`) still loads the **v1** task-aligned dataset
and `outer_fold_primary`; do not mix the two.

---

## 4. What data access do we actually have — tested, not assumed

### Credentials: none

There is **no Etherscan, Dune, Alchemy, QuickNode, or Infura key** in the environment, in
`.env` files (none exist), or referenced by any script. No script in the repo reads an API
key environment variable at all. The only network endpoints referenced anywhere are public
`*.publicnode.com` RPCs used by the truncation-repair pass.

Live tests I ran:

| endpoint | result |
|---|---|
| Etherscan V2, no key | `{"status":"0","message":"NOTOK","result":"Missing/Invalid API Key"}` |
| Dune API, no key | HTTP 401 |
| `ethereum-rpc.publicnode.com` | works, **but only with a browser User-Agent** — default urllib UA gets HTTP 403 |
| `eth.drpc.org` | works, and is the most capable free endpoint found |

### Capability probe on `eth.drpc.org` (free, no key)

| capability | result |
|---|---|
| archive state (`eth_getBalance` @ block 1,000,000) | **works** |
| `trace_block` | **works** (returns full trace array) |
| `trace_filter` by `toAddress` | **works** on Ethereum |
| `eth_getLogs`, 2,000-block range, topic-filtered | **works** |
| `debug_traceBlockByNumber` | times out / unavailable |
| JSON-RPC **batching** (10 or 25 calls) | **HTTP 500 — not supported** |

**So the answer to the work order's specific question — can we retrieve internal transactions
and ERC-20 transfer logs for arbitrary EOAs? — is yes, on Ethereum, one call at a time.**

### But the scale does not work

| measurement | value |
|---|---|
| sequential full-block fetch (`eth_getBlockByNumber`, full txs) | **7.65 blocks/s** |
| type-0x04 txs observed in 6 recent mainnet blocks | 13 (≈2.2/block) — `authorizationList` is fully readable |
| Pectra (22,431,084) → head (25,631,003) | **3,199,923 blocks** |
| brute-force scan of that span at measured rate | **≈5 days, single-threaded, Ethereum only** |

No batching means no easy constant-factor win, and the free tier rate-limits under
concurrency (I hit HTTP 429 during the multichain probe). On the other six chains
`trace_filter` failed on 5 of 6:

| chain | `trace_filter` |
|---|---|
| gnosis | OK |
| bnb | HTTP 429 |
| base | HTTP 408 |
| optimism | HTTP 408 |
| arbitrum | HTTP 400 |
| polygon | HTTP 500 |

**Verdict on §3.2 / §3.5 as specified: not feasible.** Enumerating all type-0x04 set-code
transactions and building per-EOA outflow histories across 7 chains on free public RPC is
weeks of wall time with unreliable trace support on the chains holding 71% of the corpus.
The work order asked me to say so on day one rather than day ten. This is that.

### One thing that did work, and matters

I sampled 8 Ethereum primary delegates and called `eth_getCode` live: **8/8 still have code
on-chain, and 8/8 bytecodes exact-match the stored `runtime_bytecode`.** The corpus is
faithful to the chain. Whatever else is wrong with the labels, the *inputs* are sound.

### The precedent that already exists in-repo

`reports/independent_set_report.md` + `independent_malicious.csv` is a prior, working
instance of exactly the evidence logic §3.3 asks for, done on public RPC without keys: take
a blacklist of 7,915 scam-flagged accounts, `eth_getCode` each on mainnet, find the 49 that
currently carry an `ef0100‖addr` delegation designator, and read off the 9 delegate targets
they point at. 39 of the 49 converge on a single target — victim convergence, observed, not
inferred from bytecode. That funnel yielded **1** truly-novel confirmed malicious delegate,
and the report's own verdict is **INSUFFICIENT DATA**.

This is the cheapest known non-circular evidence channel and it is *reverse-indexed* — it
starts from suspect accounts, not from delegates, so it sidesteps the "who delegated to D?"
indexing problem entirely. It is also, on the evidence, thin.

---

## 5. What already exists that §2 or §3 would duplicate

**Gate 0A (rule emulator): not done. Genuinely new.**
`revision_v2/audit/scripts/shortcut_diagnostics.py` is the nearest thing, but it deliberately
tests only *acquisition/provenance* features — bytecode length, opcode count, CBOR presence,
duplicate-group size, family size, chain — and explicitly **never opcode content**. Best
trivial AUPRC there is 0.51. Gate 0A's hand-coded structural rules (SELFDESTRUCT, hardcoded
call targets, balance-sweep, CALLER guards) are opcode-content features and are untested.
The two are complementary; Gate 0A should cite the 0.51 as its provenance-only floor.

**Gate 0B (similarity kNN): not done.** `gateB` is a different experiment — selective
escalation, where feature-space kNN outlier distance is signal S6, not a classifier.
`family_sensitivity` has reusable MinHash infrastructure. No nearest-neighbor classifier
baseline exists in `baseline_summary.csv` (7 models: Seq, flat CNN, hist+4-gram XGB,
ngram_only, BiGRU, dense_only, Transformer). Given that malicious families are the larger
ones (median 9 vs 4 rows), I expect this gate to be informative.

**Task 2 (labeling app): partially pre-exists, and is stalled.**
`revision_v2/artifact/label_audit/` holds a 170-item stratified blinded review package —
7 strata, seed 7702, 3 reviewers, blinded forms `review_form_R{1,2,3}_BLINDED.csv`, a
`REVIEWER_KEY_do_not_distribute.csv`, and `REVIEWER_GUIDELINES.md`. `agreement_results.json`
reads `{"status": "pending_human_labels", "found": 0}`. **Zero labels have been collected.**

It is CSV-based, sampled at the row level rather than the family level, and its evidence
packets are bytecode-derived — which is precisely the design the work order forbids in §1.3.
The sampling design, blinding discipline, and reviewer guidelines are reusable; the evidence
substrate is not.

**Also reusable:** `revision_v2/experiments/uncertainty/bootstrap_*.py` implements the
family-clustered bootstrap the gates need for paired CIs. `anvil`/`cast`/`forge` are
installed and `run_exec_validation.py` already drives `anvil_setCode` + opcode-level
`debug_traceCall` against corpus bytecode.

**Missing scripts (flag):** `experiments/legitimate_registry_expansion_v1/` and
`experiments/reference_analyzer_cost_v1/` contain only `__pycache__` — the `.py` sources are
gone (`audit_registry_overlap`, `run_reference_analyzer_cost_v1`, `prepare_sample`, and
others). Results for the latter survive under `results/`. If either matters to the paper,
that source loss should be dealt with separately.

---

## 6. Assumptions in the work order that are wrong about this repo

1. **"~2,190 observed delegates."** 2,190 (chain, address) rows; 1,972 unique addresses;
   1,665 unique bytecodes.
2. **Implicit single-chain / Ethereum-mainnet corpus.** It is 7 chains; Ethereum is 29%.
   This breaks §3.2, §3.4, and §3.5 as written.
3. **"Determine whether we can retrieve internal transactions… this determines whether §2.3
   is feasible."** We can, technically, on Ethereum. It is *throughput*, not capability, that
   makes §3.2/§3.5 infeasible — plus missing trace support on 5 of the 6 other chains.
4. **§1.2 frames label circularity as an open suspicion to be resolved.** It was established
   and documented on 2026-07-18. Positives are the output of a Gigahorse fallback/receive →
   external-call reachability rule over the same bytecode the model reads. This changes what
   Gate 0A measures: not *whether* the labels are rule output (they are, by construction) but
   *how much of that rule a trivial hand-coded emulator recovers*. Still worth running — the
   audit's own note that the model scores 0.92 rather than 1.0 implies the rule is not
   trivially recoverable, and Gate 0A is the test of that claim.
5. **§4.2 "family representative (highest-authorization member)."** No authorization counts
   exist for any delegate. Needs a different representative rule — family size / bytecode
   centrality — until §3.2 lands, if it ever does.
6. **§4.4 "priority queue ordered by `unique_authorizer_count` descending"** and §4.6
   "cumulative authorization coverage" have the same dependency and the same problem.
7. **§3.5 "the paper currently has only five [legitimate delegates]."** Correct for the
   benchmark's `QUALITATIVE_CONTROL`, but `benign_7702_bytecode.csv` holds 45 rows spanning
   several projects across multiple chains (MetaMask delegation framework et al.), fetched by
   `fetch_benign_7702_delegates.py`. The starting point for the ≥40-implementation target is
   better than five.
8. **§1.1 "delegate may have no transaction history."** The audit found this is not an edge
   case — `has_execution_history` will be false for a large fraction, and the source artifact
   was **ethics-scrubbed of all transaction, victim, and attack-tx evidence**
   (`exec_validation.json`: *"artifact ships no attack tx / victim state"*). The behavioral
   evidence §3.3 needs was deliberately removed upstream and must be re-collected from chain.
9. **Alembic/Docker/deploy target** — no `DEPLOY_TARGET` was provided, and the repo has no
   container, web, or migration infrastructure of any kind. Task 2 starts from zero.

---

## What this does not show

- I probed one free RPC provider (`drpc.org`) plus a handful of public endpoints. A paid
  Alchemy/QuickNode archive plan with batching and reliable `trace_filter` across all seven
  chains would change the §3 feasibility verdict substantially. My "infeasible" is scoped to
  *free public RPC without credentials*, not to the task in principle.
- I did not attempt to estimate how many corpus delegates have any authorization activity at
  all. That requires the very index that is missing, or a targeted per-delegate probe I have
  not costed.
- The 8/8 bytecode match is a sample of 8 Ethereum rows, chosen with seed 7702. It is
  reassuring, not a corpus-wide integrity proof.
- I verified fold disjointness on the *stored* fold column. I did not re-derive the folds
  from scratch, so I am confirming the stored splits are internally consistent, not that the
  original split procedure was correctly specified.
- I did not evaluate whether Gigahorse/Soufflé can be run locally to reproduce the source
  rule directly. If it can, that is a cleaner Gate 0A than a hand-coded emulator, and
  `results/gigahorse/` suggests someone has looked at this.
- Throughput numbers are single measurements on one evening from one network location.
  Treat ±50% as within noise.

---

## Decisions I need from you before Task 1

1. **Credentials.** A free Etherscan V2 key (one key covers all 7 chains via `chainid`) plus
   a free Dune key would move §3.2/§3.4/§3.5 from infeasible to routine. Without them the
   only viable evidence channel is the reverse blacklist→designator funnel, which has already
   been run once and yielded n=1.
2. **Corpus scope for behavioral evidence.** Ethereum-only (643 rows, 366 families, best
   tooling) or all 7 chains (2,190 rows, degraded and uneven evidence quality)? An
   Ethereum-only ground-truth subset with the rest labeled from weaker evidence is a
   defensible design, but it has to be a stated design, not a silent one.
3. **Whether Task 0 runs now.** Both gates are unblocked and independent of the above. I
   recommend running them while the credential question resolves — if Gate 0A comes back
   ≥0.90 AUPRC, the model paper is not defensible and the entire §3/§4 labeling effort
   changes purpose before anyone spends 40 person-hours on it.

**Stopping here for review, per §2 of the work order.**
