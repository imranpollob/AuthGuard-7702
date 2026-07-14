# Independent Malicious-Delegate Evaluation — FROZEN PROTOCOL

**Frozen (UTC):** 2026-07-14T20:10:47Z
**Author role:** senior ML + blockchain-security research engineer (AuthGuard-7702).
**Status:** This document is pre-registered. It is written and timestamped BEFORE any
detector is run on any independent candidate. No criterion below may be changed after
inspecting model predictions. If a criterion proves infeasible, that is reported as a
result, not repaired by loosening the criterion.

**Input integrity (SHA-256, frozen at write time):**
- `scamsonethereum-main/master_blacklist_set.txt` — `388f6e85cf6e99ed628803bca3d6818dd7f5262cf3f8df63436c29d2501352be`
- `scamsonethereum-main/all_across_hard.txt` — `58b1d1e1c0a7cc4d135d109230547b7905ea2a4af8336b3928a2e6acd1c92775`

---

## Evaluated claim
> "AuthGuard generalizes to independently sourced malicious EIP-7702 delegates that were
> absent from its USENIX-derived training set."

The independent set must be sourced and confirmed WITHOUT using the USENIX label-generation
rule (fallback/receive external-call fact + sensitive-name match). The USENIX artifact is
used ONLY as an exclusion reference (to remove overlap), never as positive evidence.

## 1. Data sources
1. `scamsonethereum-main/master_blacklist_set.txt` (7,915 addresses; file mtime 2023-12-05).
2. `scamsonethereum-main/all_across_hard.txt` (495 addresses; file mtime 2023-12-05).
3. Read-only Ethereum-family JSON-RPC (publicnode and equivalent public endpoints) for
   `eth_getCode`, `eth_getTransactionByHash`, `eth_getTransactionReceipt`, `eth_getBlockByNumber`.
   Read-only ONLY: no `eth_sendRawTransaction` or any state-changing call, ever.
4. Keyless block explorers / indexers (e.g., Blockscout-family) if reachable, for
   authorization-list / delegation lookups. Any API used is logged with endpoint + timestamp.
5. USENIX artifact (`eoa_detect/detect_result.jsonl`, the 793 addresses, `capability_dataset.csv`,
   `family_assignment_frozen.csv`) — **exclusion reference only**.

Provenance is preserved per candidate: which file it came from, and every network response
that touched it, are logged to `network_query_log.csv`.

## 2. Inclusion criteria (ALL must hold)
- **I1.** Syntactically valid `0x` + 40 hex address.
- **I2.** Has contract runtime code (`eth_getCode` ≠ `0x`) on ≥1 examined chain.
- **I3. Verified EIP-7702 delegate USAGE.** Positive evidence that the address was the
  *delegate target* of an EIP-7702 authorization, via one of: (a) an EOA whose account code
  equals `0xef0100 ‖ <address>`; (b) an indexed/explorer authorization record naming the
  address as delegate; (c) a type-0x04 transaction whose `authorization_list` names the
  address. **Runtime bytecode alone is NOT sufficient.**
- **I4. Independent maliciousness** (see §4), established without the USENIX rule.

## 3. Chains to examine
The seven chains present in the frozen dataset: Ethereum, Base, BNB Smart Chain, Optimism,
Arbitrum, Polygon, Gnosis. Primary examination is Ethereum mainnet (the scamsonethereum
corpus is Ethereum-focused). Other chains are examined for I2/I3 where a public endpoint is
reachable. Chains examined and endpoints used are logged.

## 4. Definition — independently confirmed malicious EIP-7702 delegate
Satisfies I1–I3 AND has ≥1 of the following maliciousness evidence types, none of which is
the USENIX rule:
- **E-incident:** a documented security incident/report naming the delegate address.
- **E-drain:** an on-chain authorization to the delegate followed by observed asset drainage
  (ETH/ERC-20/NFT) out of the delegating account.
- **E-tx:** transaction-level evidence of exfiltration involving the delegate.
- **E-feed:** a security-feed classification SUPPORTED by transaction evidence (feed label
  alone is insufficient).
- **E-manual:** manual confirmation of an attacker-controlled asset-moving path in the code
  PLUS an observed malicious execution.

Recorded per included contract: evidence source, evidence type, related tx hashes, affected
asset type, attack description, confidence (high/medium/low), reviewer notes. Ambiguous cases
get a second reviewer where possible. **Generic blacklist membership without EIP-7702-specific
evidence is NOT sufficient** and routes the candidate to `uncertain_candidates.csv`.

## 5. Overlap / novelty definitions (computed with the FROZEN pipeline, threshold 0.85)
- **Exact overlap:** SHA-256 of normalized runtime bytecode equals that of any USENIX-793 contract.
- **Family overlap:** the candidate, clustered by the FROZEN MinHash pipeline, joins a
  `family_id` that contains ≥1 USENIX-793 malicious contract; OR its max MinHash-Jaccard
  similarity to any USENIX-793 contract ≥ 0.85 (the frozen family threshold).
- **Truly novel:** independently confirmed malicious delegate (§4) that is NOT one of the 793,
  NOT exact overlap, and NOT family overlap.
- Continuous max-similarity to the nearest USENIX-793 contract is recorded for every candidate.

Subsets emitted: `exact_known`, `known_family`, `truly_novel`, `uncertain_family_boundary`
(0.80 ≤ max-sim < 0.85, a pre-registered band around the frozen threshold). The frozen family
threshold (0.85) is NOT changed after seeing model results.

## 6. Frozen model thresholds
No persisted single-model artifact exists from the prior iteration (models were trained
per-fold inside cross-validation and discarded; features were stored as `.npz`, not
`.parquet`). Therefore, BEFORE scoring any independent candidate, a single frozen instance of
each detector is materialized from the FROZEN training procedure (seed 7702) on the full
USENIX-derived training corpus (malicious 793 vs. benign_cleared 1,657), and its operating
threshold is fixed as the max-F1 point on the TRAINING data only. These thresholds are written
to `reports/frozen_thresholds.json` and hashed before any independent prediction. Thresholds
are never adjusted to the independent set. Detectors: blocklist (exact-hash), sensitive-name
rule approximation, external-call structural over-approximation, selector-LR, opcode-RF,
opcode-XGB, AuthGuard, and the full released USENIX pipeline only if it can be executed
faithfully (otherwise its absence is stated, and no claim is made about what it "would" do).

## 7. Minimum sample counts (stopping/reporting guideline)
Count = independently confirmed, truly-novel delegates.
- **< 10:** insufficient for quantitative superiority claims (case-study only, or INSUFFICIENT DATA).
- **10–29:** exploratory case-study evidence only.
- **30–49:** limited quantitative evidence with confidence intervals.
- **≥ 50:** suitable for a substantive independent evaluation.
These are reporting guidelines, not reasons to discard data.

## 8. Planned statistical reporting
- Per-method detection rate on each subset with **Wilson 95% CI** (and bootstrap CI where n allows).
- Raw score distributions per method; frozen threshold overlaid.
- Pairwise contingency (AuthGuard vs. each rule): both / AuthGuard-only / rule-only / neither.
- False-positive (flag) rates at the SAME frozen thresholds on `benign_AA`, `benign_cleared`,
  `benign_general`, and any independently verified benign delegate control set.
- Detection at matched false-positive rates where score distributions permit.
- Terminology: "sensitive-name rule approximation" and "external-call structural
  over-approximation" are never called "the USENIX detector." No claim that the full USENIX
  pipeline misses a contract unless that pipeline was actually executed and observed to miss it.

## 9. Stopping rule
Surface the T2–T4 funnel BEFORE any model prediction or extensive visualization. The count of
independently confirmed, truly-novel delegates is the primary feasibility result and gates
whether T5–T8 run at all.

## 10. Final verdict vocabulary
Exactly one of SUPPORTED / PARTIALLY SUPPORTED / NOT SUPPORTED / INSUFFICIENT DATA, with exact
counts and CIs, plus a separate statement on superiority over (a) the lightweight rule
approximations and (b) the full USENIX pipeline (only if faithfully executed).
