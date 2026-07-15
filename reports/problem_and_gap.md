# Problem, Existing Solutions, and Gap (Paper §§1–3)

## 1. Problem we are solving

**One-sentence problem statement.** Given only the bytecode of an EIP-7702 delegate contract, decide *before the user signs the authorization* whether delegating to it is dangerous.

**One-paragraph description.** EIP-7702 lets an externally owned account (EOA) install a delegate contract's code into its own account; once the authorization is signed, that code executes with the account's full authority over ETH, ERC-20 allowances, and NFTs. The decisive defense point is therefore the signing moment, not afterward: by the time an on-chain drain is observable, the loss has occurred. A delegate can be freshly deployed with no transaction history, so post-hoc, history-dependent detection cannot protect the first victims. What *is* available at signing time is the delegate's runtime bytecode (fetchable via `eth_getCode` or a cache). This differs from generic smart-contract vulnerability detection: the target is not a bug in a contract the user owns, but the *maliciousness of code the user is about to grant authority over their own account*, and it must be judged from bytecode alone, fast, with no decompiler in the signing path. Because attackers redeploy new delegate families and apply bytecode transformations between deployments, the learner must generalize to unseen families and resist structure-preserving mutation — an AI generalization-and-robustness problem, not a lookup.

**Formal task definition.**
- **Input:** runtime bytecode `b` of a candidate delegate (hex).
- **Output:** risk score `s(b)∈[0,1]` and a binary flag at a frozen threshold `τ`.
- **Available information:** bytecode-derived features only (opcode histogram, opcode 4-grams, selector set, structural EVM stats).
- **Unavailable (by construction):** the delegate's future transactions, victim/signer identity, verified source, decompiler output.
- **Training labels:** 793 malicious delegates labeled by the USENIX rule (positives are rule-derived); negatives are `benign_cleared` (rule-silent, weak) with `benign_general`/`benign_AA` as closer-to-clean sets.
- **Evaluation constraint:** leave-family-out on a frozen family id; no contract or its mutants may straddle a split.
- **Attacker model:** controls the delegate source; between deployments may apply structure-preserving / attack-capability-preserving transformations (metadata rewrite, address-immediate randomization, dead-code flooding, sensitive-selector rename) to evade screening while preserving the drain behavior. Not assumed: bytewise identity or selector preservation.
- **Deployment:** a wallet pre-signing hook or a CLI/service screen, interactive latency, no decompiler.

*Practical motivation (labeled as a known-family observation, not a novelty claim):* an on-chain sweep of an independent 2023 scam blacklist surfaced a live delegate (`0x0727ca…`) to which 39 flagged accounts had delegated and been emptied — a shared-sweeper pattern. It is **known-family** (MinHash 0.883 to the training positives), so it motivates the setting but is not evidence of novel-family generalization.

## 2. Existing solutions

| Approach | Input | Pre-signing? | Needs tx history? | Family generalization | Mutation robustness | Runtime burden | Explanation | Main limitation |
|--|--|--|--|--|--|--|--|--|
| Full USENIX Gigahorse/Datalog pipeline | bytecode → decompiled facts | No (post-hoc study) | Effectively (built from observed attacks) | rule-bound | structural core robust; name-match brittle | heavy (decompiler) — **[NOT MEASURED] here**, deployment concern | rule provenance | post-hoc; heavyweight; name-lexicon brittle |
| Shipped USENIX labels / oracle | precomputed verdicts | No | Yes | n/a (lookup) | n/a | n/a | verdict only | only covers already-seen contracts |
| Sensitive-name rule approximation (ours, reimpl.) | selectors | Yes | No | poor | **0.000 at M3** | ~ms | fired name | fires on ~4% of positives; trivially renamed |
| External-call structural over-approximation (ours) | opcodes | Yes | No | n/a | flat 1.000 but non-discriminative | ~ms | call present | flags 88–92% of benign |
| Opcode/bytecode phishing classifiers (e.g., PhishingHook) | opcodes/bytecode | Yes | No | rarely family-evaluated | rarely tested | light | limited | different surface; leakage-prone splits |
| Transaction-level phishing detectors | tx graphs/features | No | Yes | n/a | n/a | medium | limited | needs history; post-hoc |
| Graph-based phishing-address detectors | tx/interaction graph | No | Yes | address-level | n/a | medium/heavy | limited | needs on-chain graph; post-hoc |
| Blocklists / exact bytecode signatures | address/hash | Yes | No | **none** | **0.000** | trivial | match id | fails on any unseen/mutated variant |

*(Runtime for heavy analysis was not measured locally; treat "heavy" as a deployment concern, not an established number.)*

## 3. Gap in existing solutions

**Demonstrated by our experiments (EXPERIMENT-SUPPORTED):**
1. **Blocklist/signature failure on unseen families** — blocklist AUPRC 0.324 (LFO) vs 0.558 (random); recall 0.000 under family holdout.
2. **Clone leakage under random splits** — AuthGuard AUPRC inflates 0.856→0.961; the memorization gap is real and large.
3. **Rule brittleness under mutation** — sensitive-name approximation retained detection 0.038→0.000 at a byte-level rename (M3); structural over-approximation is robust only by flagging 88–92% of benign.
4. **Learned-model robustness limit** — under heavy padding the M0 model degrades (original M3+flood +200% retained 0.139; pure-M0 +200% recall 0.624), later *partially* recovered by augmentation (0.624→0.790) but with a residual 27.5% benign flag rate.

**Motivated by prior literature only (LITERATURE-VERIFIED / PROVISIONAL):**
5. Post-hoc dependence and heavy deployment cost of decompiler pipelines (PROVISIONAL for runtime — not measured here).
6. Lack of adversarial-robustness evaluation in prior EIP-7702 / phishing-bytecode detectors (LITERATURE-VERIFIED as a gap).

**Not yet evaluated (NOT SUPPORTED as claims):**
7. Signer-context / relational risk (no victim data — synthetic only).
8. Selective escalation / calibration (not implemented).
9. Independent EIP-7702 ground truth at scale (INSUFFICIENT DATA: 1 confirmed novel delegate).

**Why this is not "XGBoost on blockchain data."** The contribution is not the estimator; it is (a) a *pre-signing* problem formulation with a bytecode-only information set, (b) a *frozen, leakage-safe family-grouped* evaluation that quantifies and removes the near-duplicate inflation most prior work reports, and (c) a *verified structure-preserving mutation benchmark* plus a leakage-safe *source-balanced augmentation* protocol whose robustness gains are measured with paired statistics. The estimator is deliberately standard; the methodology is the content.
