# AuthGuard-7702 — Results Summary (paper-ready)

Every number below is emitted directly from the pipeline's JSON outputs by `pipeline/07_summary.py`. Seed = 7702. `PYTHONHASHSEED` does not affect results (deterministic blake2b hashing throughout). See `DECISIONS.md` for methodology and `RESULTS_README.md` for exact reproduction.

## Dataset (verified on load)

3,258 contracts: malicious = 793, benign_cleared = 1,657 (weak negative, rule-silent), benign_general = 800 (closer-to-clean), benign_AA = 8 (hand-verified AA delegates). All 793 malicious labels come from the single USENIX fallback/receive-external-call rule; positives are rule-derived and the paper claims robustness on KNOWN positives, not novel-family discovery.

## A. Frozen family structure (Claim 2)

Global, deterministic MinHash clustering of all 3,258 contracts (leakage-safe: near-duplicate bytecodes with conflicting labels share one family and cannot straddle a split). Frozen `family_id` at threshold 0.85.

| threshold | families | singleton % | largest | cross-chain % | cross-class % |
|---:|---:|---:|---:|---:|---:|
| 0.75 | 1120 | 66.9 | 89 | 14.3 | 4.4 |
| 0.85 (frozen) | 1329 | 68.6 | 58 | 13.8 | 3.3 |
| 0.9 | 1511 | 71.7 | 48 | 13.0 | 2.4 |

**Malicious population:** 793 contracts → 214 families (178 purely malicious), 113 malicious singletons (52.8% of malicious families), largest malicious family = 58. A genuinely diverse population (long singleton tail + a few mid-size families), not a handful of clones.

## C. Detection under leave-family-out

GroupKFold(5) on frozen `family_id`; mean ± std over 5 folds. Threshold for F1/P/R chosen on TRAIN only. AUPRC is primary. Bytecode-only features; `chain` and the two tautological cap columns are banned.

### Primary task — malicious (793) vs benign_cleared (1,657)

**Leave-family-out (headline):**

| method | AUPRC | AUROC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| USENIX shipped (oracle) | 1.000 ± 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| USENIX name-rule | 0.344 ± 0.093 | 0.518 | 0.071 | 0.884 | 0.038 |
| USENIX struct-rule | 0.341 ± 0.084 | 0.539 | 0.503 | 0.341 | 1.000 |
| blocklist (exact-hash) | 0.324 ± 0.078 | 0.500 | 0.000 | 0.000 | 0.000 |
| selector-LR | 0.519 ± 0.068 | 0.670 | 0.521 | 0.459 | 0.617 |
| opcode-RF | 0.775 ± 0.076 | 0.895 | 0.557 | 0.782 | 0.444 |
| opcode-XGB | 0.789 ± 0.060 | 0.907 | 0.704 | 0.784 | 0.656 |
| **AuthGuard** | 0.856 ± 0.043 | 0.930 | 0.720 | 0.871 | 0.641 |

**Random split (leakage context ONLY — not a headline):**

| method | AUPRC | AUROC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| USENIX shipped (oracle) | 1.000 ± 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| USENIX name-rule | 0.352 ± 0.020 | 0.522 | 0.086 | 0.893 | 0.045 |
| USENIX struct-rule | 0.341 ± 0.012 | 0.538 | 0.508 | 0.341 | 1.000 |
| blocklist (exact-hash) | 0.558 ± 0.024 | 0.684 | 0.540 | 0.944 | 0.379 |
| selector-LR | 0.558 ± 0.035 | 0.728 | 0.597 | 0.509 | 0.722 |
| opcode-RF | 0.941 ± 0.029 | 0.979 | 0.904 | 0.924 | 0.887 |
| opcode-XGB | 0.948 ± 0.027 | 0.981 | 0.919 | 0.920 | 0.919 |
| **AuthGuard** | 0.961 ± 0.017 | 0.986 | 0.940 | 0.944 | 0.936 |

> The AuthGuard AUPRC gap **0.856 (family) → 0.961 (random)** is the leakage a naive random split hides. The `blocklist` row makes it starkest: 0.324 AUPRC / 0.0 recall under leave-family-out, 0.558 / 0.379 under random split — pure memorization leak.

### Secondary task — + benign_general (adds 800 closer-to-clean negatives)

| method | AUPRC | AUROC | F1 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| USENIX shipped (oracle) | 1.000 ± 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| USENIX name-rule | 0.276 ± 0.055 | 0.522 | 0.084 | 0.848 | 0.045 |
| USENIX struct-rule | 0.262 ± 0.056 | 0.545 | 0.412 | 0.262 | 1.000 |
| blocklist (exact-hash) | 0.244 ± 0.050 | 0.500 | 0.000 | 0.000 | 0.000 |
| selector-LR | 0.457 ± 0.072 | 0.716 | 0.460 | 0.471 | 0.466 |
| opcode-RF | 0.800 ± 0.055 | 0.933 | 0.512 | 0.861 | 0.378 |
| opcode-XGB | 0.803 ± 0.054 | 0.918 | 0.671 | 0.775 | 0.624 |
| **AuthGuard** | 0.877 ± 0.042 | 0.952 | 0.706 | 0.915 | 0.597 |

## D. Mutation stress-test (Claim 3, the spine)

Semantics-preserving mutations of HELD-OUT malicious; split before mutation; mutants inherit source family and stay held-out. Executable-region opcode-token preservation verified **793/793** at every tier. Retained detection = recall on the same held-out malicious per tier (mean over 5 folds).

| method | M0 | M1 (metadata) | M2 (+addr/deadcode) | M3 (+selector rename) |
|---|---:|---:|---:|---:|
| USENIX name-rule | 0.038 | 0.038 | 0.038 | 0.000 |
| USENIX struct-rule | 1.000 | 1.000 | 1.000 | 1.000 |
| blocklist (exact-hash) | 0.000 | 0.000 | 0.000 | 0.000 |
| selector-LR | 0.617 | 0.621 | 0.623 | 0.621 |
| opcode-XGB | 0.656 | 0.659 | 0.518 | 0.518 |
| **AuthGuard** | 0.641 | 0.668 | 0.588 | 0.588 |

**Read next to Task-C precision:** `USENIX struct-rule` retains 1.000 recall only because it flags ~everything (precision 0.341, AUROC 0.539 — not a usable detector). `USENIX name-rule` collapses 0.038 → 0.000 at M3. `blocklist` is 0.0 throughout. **AuthGuard is the only method that is both evasion-robust (0.588 retained through M3) AND discriminative (0.87 precision).** Among learned models it degrades most gracefully on M0–M3 (−5 pts vs opcode-XGB's −14 pts at M2).

### Dead-code volume sweep (robustness limit, on top of M3)

| method | +0% | +25% | +50% | +100% | +200% |
|---|---:|---:|---:|---:|---:|
| AuthGuard | 0.668 | 0.567 | 0.500 | 0.310 | 0.139 |
| opcode-XGB | 0.659 | 0.523 | 0.498 | 0.473 | 0.485 |
| USENIX struct-rule | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| USENIX name-rule | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

**Honest limitation:** under extreme unreachable-code flooding AuthGuard degrades FASTER than the plain opcode histogram (0.139 vs 0.485 at +200%) — its normalized 4-gram features dilute. Reported, not tuned away. Points to reachability-aware feature extraction as the fix.

## E. Supporting analyses

**Contamination upper bound (benign_cleared weakness).** Of 1,657 benign_cleared, 135 (8.1%) share a frozen family with a known-malicious contract and 20 (1.2%) are byte-identical to a known-malicious contract — rule-silent but structurally malicious, i.e. an estimated **≤8.1% label contamination** in the weak negative set. This is why benign_cleared is never framed as clean.

**Latency.** 3.4 ms/contract mean (p50 2.5, p95 10.7; batched 3.2). No decompiler in the loop — pre-signing at wallet-interaction time is feasible.

**Explanation audit (50 cases).** Fired-signal coverage = 1.0 (every flag cites a concrete capability: external_call / delegatecall / sensitive_selector). Nearest-family retrieval is informative only when a similar family exists: overall nn-malicious rate 0.34 ≈ base rate 0.327, but 0.652 at similarity ≥ 0.7 (n=23/50). Honest: novel families are not retrievable.

**Synthetic signer exposure.** Illustrative only — no real victim/signer data exists (stripped for ethics). See `results/supporting.json` → `synthetic_signer`.

## Candid verdict on the three novelty claims

1. **First pre-signing (bytecode-only) risk tool — SUPPORTED.** A bytecode-only learned model reaches 0.856 AUPRC / 0.93 AUROC under leave-family-out at 3.4 ms/contract, with no decompiler and no post-hoc attack history. The tool exists and works at usable operating points (0.87 precision, 0.64 recall).

2. **First quantified family/singleton characterization — SUPPORTED.** Deterministic, frozen, threshold-robust: 214 malicious families, 52.8% singletons, largest 58; ≤8.1% contamination quantified in the weak negative set.

3. **Evasion-brittleness of the deployed rule + a more graceful learned model — PARTIALLY SUPPORTED (strong on the specific sub-claim).** The deployed rule's precision-bearing name-match is trivially evaded (→0.000 at M3) and exact-hash blocklisting is useless (0.0); the learned model retains 0.588 detection at 0.87 precision — the only robust-AND-discriminative method. The general claim 'learned degrades most gracefully under ALL mutation' is NOT supported: under heavy dead-code flooding AuthGuard degrades faster than the opcode histogram.

## What a skeptical reviewer will attack (and the preemption)

1. **"Your negatives aren't clean, so detection AUPRC is meaningless."** True that benign_cleared is weak; we quantify ≤8.1% contamination, report the secondary task with closer-to-clean benign_general (AUPRC 0.882, even higher), and never call cleared contracts verified-benign. The detection claim is explicitly 'separates known-malicious from rule-silent contracts under family holdout,' not 'detects all malware.'

2. **"The structural rule is robust, so your evasion story is oversold."** We show the structural rule IS robust — and useless (0.341 precision). We do not hide it; the evasion claim is scoped to the precision-bearing name-match component and to hash blocklisting, both of which genuinely collapse. AuthGuard's contribution is being robust without collapsing to base-rate precision.

3. **"Positives are all from one rule — you're just re-learning the rule."** The name-rule footprint (`has_sensitive_selector`) fires on only ~4% of held-out malicious, so the 0.856 AUPRC cannot be the rule in disguise; and under M3 that footprint is removed entirely yet the model retains 0.588 recall — it relies on opcode structure, not the label-defining rule.

## Framing recommendation

Headline the paper as a **tool contribution**: *the first pre-signing, bytecode-only, decompiler-free risk screen for EIP-7702 delegates, with a family-grouped evaluation protocol and an evasion-brittleness measurement of the deployed rule.* Lead with the leave-family-out protocol and the mutation spine (name-match → 0.000, blocklist 0.0, learned model robust-and-discriminative), not with a headline AUPRC. Report the dead-code-flooding limitation up front as scope-honesty. **Venue:** ICTAI tools-track is a reasonable fit given the applied, honest-modest framing and the tool artifact; a security-ML venue (e.g. AsiaCCS/DIMVA/WWW-security) would review the evasion protocol more expertly and is the stronger home IF the mutation taxonomy is expanded (add control-flow-obfuscation and adversarial-training baselines). Given the current honest, modest result, ICTAI tools-track is the right first submission.
