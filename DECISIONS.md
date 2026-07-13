# DECISIONS.md — AuthGuard-7702 non-obvious calls & why

Every entry is a decision a skeptical reviewer might question. Seed = 7702 throughout.

## D1. Global (cross-class) family clustering, not per-class M*/N* namespacing
The prior run clustered malicious and negatives separately with namespaced ids. But **23
exact bytecodes carry conflicting class labels** (e.g. one bytecode appears as 12 malicious
rows + 1 benign_cleared row), and many more are near-duplicates across classes. Per-class
family ids would let the *identical* bytecode sit in an M-family (train) and an N-family
(test) of the same leave-family-out split — a direct violation of honesty constraint 6.
**Decision:** cluster all 3,258 together. Any near-duplicate shares one frozen `family_id`
regardless of class, so it can never straddle a split. Side benefit: mixed-class families
fall out as the contamination signal for Task E.

## D2. Deterministic MinHash via seeded blake2b, not Python hash()
`bracket_family_count.py` used `hash((p,g))`, which drifts with `PYTHONHASHSEED` (the cause of
the 250↔275 wobble). Replaced with `blake2b(digest_size=8, salt=seed)` and an xor-permutation
MinHash. Verified: identical `family_assignment_frozen.csv` under `PYTHONHASHSEED=1` and `=999`.

## D3. Freeze threshold 0.85; report 0.75 / 0.90 for sensitivity
0.85 is the D3 "behavioral near-duplicate" choice a reviewer accepts. Family count is
monotone and smooth across 0.75→0.90 (1120→1329→1511 families), so conclusions are not
knife-edge on the threshold. Downstream reads `family_id` (=0.85) only; never recomputes.

## D4. Banned features (never used by any model)
- `chain` — `chain=="ethereum(implied)"` perfectly identifies all 800 benign_general (a split
  leak) and correlates with class in the primary task too. Excluded.
- `cap_value_receiving_hook`, `cap_unrestricted_external_call` — tautological (100% of
  malicious by construction; they restate the detection rule). Using them = fake separation.
- `family_id` — grouping key only, never a feature.
All model features are **bytecode-only**: opcode histogram, opcode 4-gram hashing, selector-set
signals, structural EVM statistics.

## D5. Weak vs. clean negatives are labeled everywhere
`benign_cleared` (1,657) = "USENIX rule did not fire" — NOT verified benign, and demonstrably
contaminated (shares exact bytecode with malicious). `benign_general` (800) / `benign_AA` (8)
are closer-to-clean. Primary detection task = malicious vs `benign_cleared` (the honest, hard,
same-population task); secondary adds `benign_general`. Every metric states its negative set.

## D6. Data-quality edge cases (all on the weak-negative side)
76 `benign_cleared` rows are bare `ef0100…`+address EIP-7702 delegation pointers (46 hex chars,
no real code — chained delegations); ~90 more are Excel-truncated/odd-length. Kept (dropping
biases the negative set) but they produce near-empty opcode features; disasm handles them
gracefully. Documented as a benign-side data-quality limitation, not silently removed.

## D7. Mutation tiers are byte-level and PROVABLY control-flow preserving
All mutations rewrite immediates in place (same width) or append unreachable code after a STOP;
none inserts/removes bytes inside the executable region, so absolute JUMP targets never shift.
Verified: the executable-region (pre-metadata) opcode TOKEN sequence is identical M0 vs mutant
for **793/793** contracts at M1/M2/M3. M1 rewrites only CBOR solc-metadata (not executed);
M2 randomizes PUSH20 address immediates (attacker-redeploy parameter) + appends benign-sourced
unreachable code; M3 rewrites sensitive PUSH4 selectors (verified: 12/12 sample malicious lose
their sensitive selector, name rule -> 0). We claim control-flow / opcode-skeleton identity and
attacker-parameter variation, NOT bitwise data-semantic identity (an attacker DOES change their
destination address each redeploy — that is the modeled behavior).

## D8. Retained-detection is recall on a FIXED held-out malicious set, paired with precision
The mutation metric is recall on the same held-out malicious contracts per tier. It MUST be read
next to Task-C precision: `usenix_struct_rule` "retains" 1.000 recall only because it flags
~everything (precision 0.34, AUROC 0.54) — not a usable detector. The honest headline is that
the learned model is the only method that is BOTH evasion-robust AND discriminative.

## D9b. AuthGuard estimator choice, made on validation not test
AuthGuard = gradient-boosted trees (XGBoost, hist) on the full bytecode feature set
(opcode histogram + hashed 4-grams + structural/selector scalars). Chosen over opcode-only RF/XGB
because it wins on the leave-family-out folds (0.856 vs 0.795 AUPRC) — a train/validation signal,
never a test-set tuning. Operating threshold picked by max-F1 on TRAIN only. No hyperparameter
search against test folds. `has_sensitive_selector` is included as a feature but fires on only ~4%
of held-out malicious, so it cannot be silently reconstructing the label (and M3 removes it, yet
recall stays 0.588 — the model leans on opcode structure, not the rule).

## D9c. `chain` leak confirmed and excluded; secondary task keeps benign_general honest
`chain=="ethereum(implied)"` tags 800/800 benign_general. Excluding `chain` means the secondary
task cannot cheat via provenance; its higher AUPRC (0.882) reflects benign_general being a
closer-to-clean, more-separable negative, not a leak.

## D9. Report the dead-code-flooding limit honestly (authguard loses there)
Added a dead-code volume sweep. Under +100/200% unreachable padding, AuthGuard degrades FASTER
than the opcode histogram (normalized 4-grams dilute). We report this as a limitation, not tune
it away. Models are trained on M0 only (deployed-model robustness question); no adversarial
training (noted as future work).
