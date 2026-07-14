# Independent Malicious-Delegate Evaluation — REPORT

**Protocol frozen:** 2026-07-14T20:10:47Z (`reports/independent_set_protocol.md`,
sha256 `863bb3fb…53d4`). All inclusion/exclusion/novelty criteria were fixed and hashed
BEFORE any detector was run on any candidate. Nothing below was tuned to a result.

**Evaluated claim:** *"AuthGuard generalizes to independently sourced malicious EIP-7702
delegates that were absent from its USENIX-derived training set."*

**Verdict (details in §7): INSUFFICIENT DATA** for the quantitative generalization claim —
only **1** truly-novel, independently-confirmed malicious delegate survived the funnel. The
exploratory case-study evidence is directionally favorable to AuthGuard and is reported as
such, not as proof.

---

## Terminology (strict, per instruction)
- **sensitive-name rule approximation** — bytecode reimplementation firing on a sensitive
  selector (sweep/drain/…). NOT "the USENIX detector."
- **external-call structural over-approximation** — fires on presence of a call opcode. NOT
  "the USENIX detector."
- **full USENIX pipeline** — NOT executed here (no Gigahorse/Soufflé). We therefore make **no
  claim** about what it would or would not catch. "AuthGuard-only" detections below are
  relative to the two lightweight approximations, never to the full pipeline.

## T1 — Independent-source inventory
| file | lines | valid addrs | unique | metadata |
|---|---:|---:|---:|---|
| `master_blacklist_set.txt` | 7,915 | 7,915 | 7,915 | none (bare addresses) |
| `all_across_hard.txt` | 495 | 495 | 495 | none (bare addresses) |

`all_across_hard` ⊂ `master_blacklist`; **union = 7,915 unique**. Both files' mtime is
2023-12-05 — **before EIP-7702 was live on mainnet** (Pectra, 2025). Neither file carries
chain, label, or source metadata. **Blacklist membership alone is not evidence of malicious
EIP-7702 delegate usage** — the labels are generic scam/phishing reputation on *accounts*,
predating the delegation mechanism entirely. Zero of the 7,915 are in the USENIX 793.

## T2 — EIP-7702 delegate-usage verification (read-only mainnet `eth_getCode`)
All 7,915 addresses classified on Ethereum mainnet (every request logged to
`network_query_log.csv`; 0 unfetched after one retry pass):

| class | count |
|---|---:|
| EOA / empty | 6,610 |
| contract code (no delegate-usage evidence) | 1,256 |
| **EIP-7702 designator** (`ef0100‖addr`, i.e. account currently delegating) | **49** |

The 49 designating accounts point to **9 unique delegate targets** (many converge: 39 of the
49 delegate to a single contract `0x0727ca…4836786`). A designator is direct on-chain proof
that the *target* is used as an EIP-7702 delegate — this satisfies inclusion criterion I3 for
the 9 targets. The 6,610 EOAs and 1,256 code-bearing addresses have **no** delegate-usage
evidence and are placed in `unverified_candidates.csv`.

## T3 — Independent maliciousness triage (manual, non-circular)
Maliciousness was judged WITHOUT the USENIX rule, from: (a) manual reading of the delegate's
bytecode interface, (b) on-chain behavior of the delegating accounts (all sampled accounts are
active, nonce>0, and swept to ≈0 balance), and (c) victim convergence. Interfaces that indicate
a **legitimate smart-account wallet** (ERC-1271 `isValidSignature`, ERC-721 `onERC721Received`,
proxy `initialize`) route the target to *likely-benign/uncertain*, because a scam-flagged
account delegating to a legitimate wallet does not make the delegate malicious.

| target | bytes | delegating | max-sim to 793 | novelty | maliciousness | basis |
|---|---:|---:|---:|---|---|---|
| `0x0727ca…4836786` | 1,254 | 39 | 0.883 | known_family | **malicious_high** | 39 independent flagged accounts → one tiny forwarder, all swept: shared sweeper |
| `0xb6785b…15aa02` | 1,837 | 1 | 1.000 | exact_known | **malicious_high** | byte-identical to a USENIX-793 contract |
| `0xa35606…7ac491` | 2,193 | 1 | 0.961 | known_family | malicious_medium | near-duplicate of a known drainer family |
| `0x545940…07a8bf` | 1,302 | 1 | 0.406 | **truly_novel** | malicious_medium | ERC-20 transfer+balanceOf + 3 CALLs, dynamic sink, victim swept (thin: 1 victim) |
| `0x88cf07…188d46` | 1,524 | 2 | 0.742 | truly_novel | uncertain | unusual selectors, single CALL; asset-path not established |
| `0x99c0b9…fb9dce` | 1,469 | 1 | 0.406 | truly_novel | uncertain | has `initialize(address)`; consistent with legit upgradeable wallet |
| `0xa845c7…73c1bf` | 2,303 | 1 | 0.133 | truly_novel | **likely_benign** | ERC-1271 + ERC-721 receiver + ERC-165: legitimate smart-account wallet |
| `0xeb96da…79ce54` | 8,706 | 1 | 0.391 | truly_novel | uncertain | Uniswap-router interface; resembles trading/wallet contract |
| `0x0e0473…c94647` | 717 | 2 | 0.039 | (truly_novel by sim) | uncertain | USDT forwarder BUT already a USENIX **benign_cleared** training negative — NOT absent from training; contested label |

## T4 — Overlap removal & the funnel
Exact overlap = SHA-256 match to a USENIX-793 contract; family overlap = frozen MinHash-Jaccard
≥ 0.85 to any USENIX-793 malicious (threshold NOT changed after seeing results).

```
7,915  unique blacklist addresses
   49  with verified EIP-7702 delegate usage (accounts delegating)
    9  unique delegate targets (candidate delegates, I3-verified)
    4  independently confirmed malicious (I4, medium+ confidence)
    3  … not among the USENIX 793
    3  … not exact-bytecode overlap
    1  … not family overlap        (2 of the 3 are near-duplicate known families)
    1  TRULY NOVEL confirmed        → 0x545940…07a8bf (malicious_medium, single victim)
```
Figure: `figures/fig_independent_funnel.png`.

**Key honest observations.** (1) The single most active independent signal — the 39-victim
sweeper `0x0727ca…` — is a **known family** (sim 0.883), so it validates that AuthGuard's
training distribution is *live in the wild* but is **not** a novelty test. (2) The truly-novel
confirmed count is **1**, with thin single-victim evidence and no rigorously confirmed drain
transaction. (3) Three of the six bytecode-"novel" targets are likely **legitimate wallets**
that flagged accounts delegated to — a reminder that account reputation ≠ delegate maliciousness.

## T5 — Frozen-detector run (EXPLORATORY; N far below quantitative threshold)
Models materialized once from the frozen procedure (seed 7702) on malicious 793 vs
benign_cleared 1,657; thresholds fixed at max-F1 on training data (`reports/frozen_thresholds.json`).
No retraining, no threshold tuning to the independent set. Detection = flag at frozen threshold.
Full per-contract results: `reports/independent_detection_per_contract.csv`.

**Confirmed-malicious detection (Wilson 95% CI):**

| method | truly-novel (n=1) | known-family/exact (n=3) |
|---|---|---|
| blocklist (exact-hash) | 0/1 | 1/3 |
| sensitive-name rule approx. | 0/1 | 0/3 |
| external-call structural over-approx. | 1/1* | 3/3* |
| selector-LR | 1/1 | 2/3 |
| opcode-RF | 0/1 | 3/3 |
| opcode-XGB | 0/1 | 3/3 |
| **AuthGuard** | **1/1** | **3/3** |

*The structural over-approximation "detects" by flagging almost everything (see T6: 88–92 %
false-positive rate); its detections are not meaningful. AuthGuard flagged the one novel
confirmed sweeper that opcode-XGB/RF missed, and flagged the live 39-victim sweeper. With
n=1 novel, these are **anecdotes**, not superiority evidence (Wilson CI on 1/1 is [0.21, 1.0]).

## T6 — False-positive controls (well-powered; the meaningful quantitative part)
Flag rate at the SAME frozen thresholds:

| method | benign_AA (n=8) | benign_general (n=800)† | benign_cleared (n=1657)‡ |
|---|---|---|---|
| sensitive-name rule approx. | 0.00 | 0.00 | 0.002 |
| external-call structural over-approx. | 1.00 | 0.88 | 0.925 |
| selector-LR | 0.25 | 0.29 | 0.34 |
| opcode-RF | 0.125 | 0.034 | 0.014 |
| opcode-XGB | 0.125 | 0.036 | 0.010 |
| **AuthGuard** | 0.125 | **0.013** | 0.013 |

† out-of-training. ‡ in-training (optimistic). AuthGuard has the lowest false-positive rate
among discriminative methods on the out-of-training `benign_general` (1.3 %). The structural
over-approximation is confirmed non-discriminative (flags the overwhelming majority of every
benign set), so a "malware detection rate" from it is not interpretable.

## T7 — Characterization of the novel/near-novel targets
The confirmed sweepers are minimal forwarders (1.2–2.3 KB) exposing ERC-20 `transfer`/
`balanceOf` and 1–3 CALLs, delegated-to by accounts that are subsequently emptied — the
canonical shared-sweeper shape. The excluded "novel" targets carry standard wallet interfaces
(ERC-1271/721/165, proxy `initialize`, Uniswap router), which is why they were not counted as
malicious. `has_sensitive_selector` fired on only 1 of 9 targets, so name-matching remains a
poor signal on independently-sourced delegates.

## T8 — Confounds & hidden overlap
- **Shared delegate:** 39/49 designators share one delegate (`0x0727ca…`); the "independent"
  malicious signal is dominated by a single (known-family) contract, not many independent ones.
- **Label provenance:** the blacklist has no per-address label; entries are generic scam
  reputation on *accounts*, not EIP-7702-delegate labels. This is why I3/I4 verification, not
  list membership, gates inclusion.
- **Blacklist composition:** 84 % EOA/empty, 16 % contracts, 0.6 % currently delegating.
- **Continuous overlap:** max MinHash-Jaccard to the 793 is recorded per target
  (`reports/independent_targets.csv`); two of the four confirmed are ≥ 0.88 (known families).
- **One contested label:** `0x0e0473…` is a USDT forwarder that USENIX shipped as
  `benign_cleared` — a candidate rule false-clear worth separate study, not counted here.

## 7. Final verdict
**INSUFFICIENT DATA.** The pre-registered funnel yields **N = 1** truly-novel, independently-
confirmed malicious EIP-7702 delegate (medium confidence, single victim). This is below the
protocol's threshold (≥10) for any quantitative generalization claim, so the evaluated claim
— that AuthGuard generalizes to independently-sourced malicious delegates absent from training
— **cannot be quantitatively established or refuted from this source.**

Exploratory case-study evidence, reported without superiority claims:
- AuthGuard flagged the 1 novel confirmed sweeper (opcode-XGB/RF did not) and the live
  39-victim in-the-wild sweeper, at a 1.3 % out-of-training false-positive rate.
- The single largest independent signal is a **known family**, so it corroborates that the
  training distribution is active in the wild rather than demonstrating novelty generalization.

**Superiority statements:**
- **vs. lightweight rule approximations:** directionally consistent with the main paper
  (sensitive-name approx. caught 0/4 confirmed; structural approx. is non-discriminative at
  88–92 % FP; AuthGuard caught 4/4 at ≈1.3 % benign FP) — but **N is too small for a
  quantitative superiority claim**; this is exploratory only.
- **vs. the full USENIX pipeline:** **no claim** — it was not executed.

**What would move this to SUPPORTED:** an indexed EIP-7702 authorization dataset (type-0x04
`authorization_list` records) to source delegates directly rather than via a pre-7702 account
blacklist, plus per-target drain-transaction confirmation, to reach ≥30–50 truly-novel
confirmed delegates.

## 10. Reproducibility & environment
```bash
export PYTHONHASHSEED=0
python3 pipeline/ind_01_inventory_getcode.py     # T1 + T2 eth_getCode census (network)
python3 pipeline/ind_02_retry_failures.py        # retry rate-limited fetches
python3 pipeline/ind_03_targets_overlap.py       # T4 target bytecode + overlap vs 793
python3 pipeline/ind_04_maliciousness.py          # T3 on-chain behavioral evidence
python3 pipeline/ind_05_funnel.py                 # funnel + subsets + figure + CSVs
python3 pipeline/ind_06_detectors.py              # T5 frozen detectors + T6 FP controls
```
Env: Python 3.13, numpy/pandas/scikit-learn/xgboost (libomp), matplotlib, pycryptodome.
Network: read-only JSON-RPC (publicnode + fallbacks), `eth_getCode`/`eth_getBalance`/
`eth_getTransactionCount` only; all requests in `network_query_log.csv`. No writes, ever.

### Deliverable files
`reports/independent_set_protocol.md`, `reports/independent_set_report.md`,
`independent_malicious.csv`, `unverified_candidates.csv`, `uncertain_candidates.csv`,
`network_query_log.csv`, `reports/independent_targets.csv`,
`reports/independent_detection_per_contract.csv`, `reports/funnel.json`,
`reports/frozen_thresholds.json`, `figures/fig_independent_funnel.png`.
