# Prompt 2 Audit — Abstract through Threat Model

Audit date: 2026-07-15. Scope: only the Abstract, Index Terms, Introduction, Background and Related Work, and Problem Definition and Threat Model. Later paper sections were not drafted or modified.

## Length and page estimate

Word counts use whitespace-delimited prose after excluding section/environment command lines. Inline TeX is counted conservatively as written, so the counts may differ slightly from a publisher's counter.

| Component | Words | Requested target | Estimated IEEE pages |
|---|---:|---:|---:|
| Abstract | 167 | 160--190 | 0.22 |
| Index Terms | 11 | concise | 0.03 |
| Introduction | 703 | approximately 650--800 | 0.75 |
| Background and Related Work | 769 | approximately 700--900 | 0.83 |
| Problem Definition and Threat Model | 402 | approximately 400--550 | 0.45 |
| **Total drafted material** | **2,052** | -- | **2.28** |

The page estimates follow `paper_build/page_budget.md`; no TeX engine is installed, so 2.28 pages is a layout allocation rather than a compiled measurement. The 0.05-page increase accommodates the directly related study without materially changing the full-paper budget of 7.78 pages or its approximately 7.7--7.9-page compiled target.

## Numeric-value ledger

| Numeric value or notation used | Meaning | Location(s) | Source |
|---|---|---|---|
| `7702` | EIP identifier in EIP-7702 and tool name | All drafted components | Official EIP-7702 standard; identifier, not an experimental result. |
| `0xef0100 || address`; `23-byte` | Three-byte delegation prefix plus a 20-byte address | Introduction; Background; Problem Definition | Official EIP-7702 standard; locally reconciled by `data_hygiene/task_alignment_protocol.md` and `designator_audit.csv`. |
| `0.881 ± 0.028` | AuthGuard family-grouped AUPRC mean ± population SD | Abstract; Introduction contribution 2 | `data_hygiene/task_aligned_detection_results.json`, G-DET primary family folds. |
| `0.975 ± 0.012` | AuthGuard seeded-random diagnostic AUPRC mean ± population SD | Abstract; Introduction contribution 2 | `data_hygiene/task_aligned_detection_results.json`, G-DET primary random diagnostic. |
| `0.484 / 0.561 / 0.217` | AuthGuard-M0 F200 fold-mean recall/AUPRC/FPR | Abstract; Introduction contribution 3 | `data_hygiene/task_aligned_advtrain_results.json`, G-ADV held-out pure-M0 F200. |
| `0.727 / 0.758 / 0.174` | AuthGuard-aug F200 fold-mean recall/AUPRC/FPR | Abstract; Introduction contribution 3 | Same G-ADV artifact and condition. The residual FPR is explicitly retained. |
| `+0.253`; `95% CI [0.144, 0.379]` | Family-clustered pooled F200 recall difference and percentile interval | Abstract; Introduction contribution 3 | `statistics/family_clustered_bootstrap.json`, task-aligned-v1 F200, 10,000 paired family-resampled replicates. The replicate count is provenance, not printed in the drafted TeX. |
| `M0`, `M3`, `F200`, and `M3-plus-F200` | Clean/held-out mutation and flooding condition names | Abstract; Introduction; Problem/Threat Model | `data_hygiene/task_aligned_mutation_curve.json`, `task_aligned_mutation_volume.json`, and `task_aligned_advtrain_results.json`. G-VOL compound and G-ADV pure-M0 conditions remain distinct. |
| `[0,1]` and `1[s >= tau]` | Score codomain and indicator warning definition | Problem Definition | Formal task definition; not an observed value. |
| `two` | Number of evaluation hazards discussed in sequence | Introduction | Rhetorical organization, not an empirical value. |

The abstract has exactly three numeric result clauses: the family/random AUPRC pair, the F200 fold-mean operating-point change, and the family-clustered pooled recall difference.

## Citation audit

- New key: `qi2025eip7702phishing` — Minfeng Qi, Qin Wang, Ruiqiang Li, Tianqing Zhu, and Shiping Chen, “EIP-7702 Phishing Attack,” arXiv:2512.12174 [cs.CR], v1 submitted 13 Dec. 2025, DOI `10.48550/arXiv.2512.12174`. Metadata was verified against the primary arXiv record.
- Citation keys used: `eip7702`, `qi2025eip7702phishing`, `huang2026darkside`, `chen2025ptxphish`, `derosa2025phishinghook`, `wang2021contractward`, `chen2020ijcai`, `chen2020toit`, `pendlebury2019tesseract`, `jordaney2017transcend`, `grosse2017adversarial`, `pierazzi2020problemspace`, `grech2019gigahorse`, and `tsankov2018securify`.
- Every key has a verified row in `paper_build/literature_verification.md`.
- Citations marked `[VERIFY CITATION]`: none.
- Administrative recheck before camera-ready: replace or confirm the official USENIX Security 2026 prepublication metadata if final proceedings metadata changes. This is not an unresolved substantive citation.
- TESSERACT and Transcend were separately audited. The old misleading `pendlebury` key for Transcend was not retained.

## Novelty and implementation-overstatement audit

Provisional novelty statements: **none**. The drafts make no priority, universal novelty, or state-of-the-art claim, and explicitly state that the standard estimator architecture is not a contribution.

Sentences that could be overread without their surrounding qualification were reviewed as follows:

1. “AuthGuard-7702 is an evaluation-grade research prototype that deterministically extracts bytecode features and returns a risk score without decompilation.” This is supported by `pipeline/ag_features.py`, `pipeline/03_detection.py`, and the task-aligned rerun. The same abstract explicitly excludes wallet, network, parser, and warning-interface integration.
2. “Runtime bytecode, by contrast, is a directly inspectable artifact that an integration can obtain at screening time.” This describes the assumed integration boundary, not persistent runtime behavior, an implemented RPC path, proxy resolution, or execution-context analysis; the introduction later identifies the artifact as a scorer rather than a wallet or RPC service.
3. “We implement a bytecode-only, decompiler-free risk-scoring prototype for screening delegate runtime code at the EIP-7702 pre-authorization decision point.” The following sentence scopes the output to a local score/warning for an external integration and denies complete wallet protection.
4. “The scorer is intended to inform a signer before authorization, while assuming only that an integration can supply or retrieve the runtime.” The next sentence states that parsing and retrieval are not performed by the scorer.
5. “The defender is assumed to obtain the corresponding runtime before authorization and run the local scorer.” This is explicitly a threat-model assumption; the same paragraph and the out-of-scope paragraph exclude production retrieval and wallet integration.
6. “These bytecode methods show that static learned representations can support screening without transaction histories.” This is a literature-level capability statement, not a claim that AuthGuard is a deployed screen; adjacent sentences distinguish task labels and boundaries.

No sentence claims a standalone CLI, serialized deployable model, authorization parser, production RPC/cache adapter, warning UI, wallet, user study, or end-to-end wallet latency.

## Correction-pass sentence ledger

This is the complete ledger of manuscript prose sentences changed in this pass; changes confined to citation metadata, evidence tables, and this audit are summarized afterward.

| File | Previous sentence | Revised sentence |
|---|---|---|
| `sections/introduction.tex` | “A malicious or inadequately constrained delegate can therefore transfer assets, issue external calls, or exercise privileges that other contracts associate with the EOA.” | “A malicious or inadequately constrained delegate can therefore transfer assets, issue external calls, or exercise privileges that other contracts associate with the EOA~`\\cite{eip7702,qi2025eip7702phishing,huang2026darkside}`.” |
| `sections/introduction.tex` | “Runtime bytecode, by contrast, is a stable input that an integration can receive or retrieve before requesting the authorization.” | “Runtime bytecode, by contrast, is a directly inspectable artifact that an integration can obtain at screening time.” |
| `sections/introduction.tex` | “An active attacker can also change a deployed program without abandoning its intended attack structure.” | “An attacker can deploy or select a transformed bytecode variant without abandoning the intended attack structure.” |
| `sections/background_related.tex` | The five-sentence paragraph beginning “The closest EIP-7702 security study” was removed. | “Two directly related studies examine complementary EIP-7702 risks.” |
| `sections/background_related.tex` | Not present. | “Qi et al. study phishing at the authorization layer: a user signs an authorization tuple whose delegated code may later be activated through user-driven, attacker-driven, or protocol-triggered calls~`\\cite{qi2025eip7702phishing}`.” |
| `sections/background_related.tex` | Not present. | “They also analyze ERC-4337-related activation, chain-agnostic authorization risk across networks, and empirical EIP-7702 activity on major EVM chains.” |
| `sections/background_related.tex` | Earlier wording called Huang et al. the closest study. | “Huang et al. classify EOA-targeted, contract-targeted, and composite attacks and combine historical transaction analysis with cross-contract static analysis~`\\cite{huang2026darkside}`.” |
| `sections/background_related.tex` | Earlier wording contrasted only Huang et al.'s boundary with AuthGuard. | “AuthGuard addresses a different boundary: bytecode-only scoring of a candidate delegate before authorization, without relying on its future transaction history.” |
| `sections/background_related.tex` | Earlier wording combined artifact provenance and boundary comparison. | “Huang et al.'s released detection artifact uses Gigahorse-derived intermediate facts and Datalog rules and establishes the source of our positive labels.” |
| `sections/background_related.tex` | “We did not execute the full USENIX Gigahorse/Datalog pipeline.” | Unchanged text, repositioned as a separate sentence after the two-study comparison. |
| `sections/background_related.tex` | “Our sensitive-name rule approximation and external-call structural over-approximation are intentionally local bytecode baselines; neither reproduces that pipeline, and their performance cannot establish superiority to it.” | “Our sensitive-name rule approximation and external-call structural over-approximation are intentionally local bytecode baselines; neither reproduces that pipeline, and their performance cannot establish superiority to it or to Qi et al.'s analysis.” |
| `sections/problem_threat.tex` | “The attacker may deploy a new delegate or reuse an existing runtime and may attempt to preserve its harmful structure while changing its representation.” | “The attacker may deploy a new transformed runtime variant or select an existing one while attempting to preserve its harmful structure.” |

The Index Terms line changed only `adversarial robustness` to `adversarial training`; it remains six terms. `literature_verification.md` gained the verified Qi et al. row and BibTeX-ready entry, and its Huang et al. row now says “directly related” rather than “closest.” `claim_to_evidence.md` added Qi et al. to the delegated-code claim, added an authorization-phishing evidence row, and removed the closest-study characterization.

## Terminology, protocol, and anonymity checks

- Required phrases used: “task-aligned dataset,” “family-grouped evaluation,” “controls related-bytecode leakage and provides a more demanding generalization estimate,” “structure-preserving transformations under our opcode-skeleton checker,” “sensitive-name rule approximation,” “external-call structural over-approximation,” and “full USENIX Gigahorse/Datalog pipeline.”
- Prohibited claims/phrases were absent after a case-insensitive scan, including priority language, semantic-equivalence claims, arbitrary-evasion robustness, and deployed-wallet latency language.
- The new related-work prose reports Qi et al.'s mechanisms and measurement scope without adopting that paper's priority language. No general-robustness or superiority claim was introduced.
- G-DET, G-MUT, G-VOL, and G-ADV remain distinct. No G-VOL value is presented as the baseline for the G-ADV augmentation result.
- Original-cohort headline values were not used. In particular, the old `0.856`/`0.961` AUPRC pair and superseded runtime/robustness headlines are absent from all four TeX fragments.
- The drafted manuscript fragments remain anonymous: no author block, author identity, affiliation, acknowledgment, institution name, email, username, personal repository URL, or local absolute path appears. Third-party author names occur only in normal related-work prose/citation metadata, not as manuscript authorship.
