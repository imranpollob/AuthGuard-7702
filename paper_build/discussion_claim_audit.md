# Discussion and Conclusion Claim Audit

## Scope, length, and page estimate

- Files drafted: `sections/discussion.tex` and `sections/conclusion.tex`.
- Discussion prose: **783 words** excluding section/subsection headings (**798** including headings under `pandoc -f latex -t plain | wc -w`). This is within the requested 700--900-word range.
- Conclusion prose: **130 words** excluding its section heading (**131** including the heading). This is within the requested 110--150-word range.
- Estimated IEEE two-column usage, without compiling: Discussion **0.9--1.0 pages**, Conclusion **0.15--0.2 pages**, combined approximately **1.1--1.2 pages**. This is a text-density estimate; Overleaf class settings and surrounding float placement will determine the final pagination.
- No complete manuscript was assembled or compiled.

## Number ledger

Every numerical value or numerical protocol identifier used in the two manuscript files is listed below. Repeated appearances use the same source.

| Number / identifier | Manuscript use | Source artifact and field / record | Aggregation and qualification |
|---|---|---|---|
| `7702` | EIP-7702 mechanism name | `literature_verification.md`, EIP-7702 record; citation key `eip7702` | Protocol identifier, not an empirical result. |
| `0.881` | Primary family-grouped G-DET AUPRC; repeated in Conclusion | `data_hygiene/task_aligned_detection_results.json`, `primary_mal_vs_cleared.leave_family_out.authguard.mean.AUPRC` | Five-fold mean on task-aligned positives versus rule-silent weak negatives. |
| `0.094` | AuthGuard random-minus-family AUPRC gap | Same G-DET JSON, `random_split.authguard.mean.AUPRC` minus `leave_family_out.authguard.mean.AUPRC`; reconciled in `task_aligned_result_provenance.md` | Seeded-random diagnostic on this corpus. |
| `0.321`, `0.551` | Exact-hash blocklist family and random AUPRC | Same G-DET JSON, `leave_family_out.blocklist.mean.AUPRC` and `random_split.blocklist.mean.AUPRC` | Rounded five-fold means; split diagnostic. |
| zero (`0.000`) | Sensitive-name recall after selector rewriting | `data_hygiene/task_aligned_mutation_curve.json`, `usenix_name_rule.M3.mean` | G-MUT only. |
| `0.530` | AuthGuard retained recall at M3 | Same mutation-curve JSON, `authguard.M3.mean` | G-MUT only. |
| `727/727` | Variants passing the implemented checker at each mutation tier | `data_hygiene/task_aligned_mutation_preservation.json`; `task_aligned_result_provenance.md` | Checker-defined opcode-token preservation; not execution equivalence. |
| `0.130` | AuthGuard recall under compound G-VOL F200 | `data_hygiene/task_aligned_mutation_volume.json`, `authguard["2.0"].mean` | Compound metadata/address/selector plus flooding; not G-ADV. |
| `0.561`, `0.484`, `0.217` | AuthGuard-M0 F200 fold-mean AUPRC/recall/FPR | `data_hygiene/task_aligned_advtrain_results.json`, `aggregate["AuthGuard-M0"].F200.mean.{AUPRC,recall,FPR}` | G-ADV pure-M0 F200, five-fold means. |
| `0.758`, `0.727`, `0.174` | AuthGuard-aug F200 fold-mean AUPRC/recall/FPR | Same adversarial-training JSON, `aggregate["AuthGuard-aug"].F200.mean.{AUPRC,recall,FPR}` | G-ADV pure-M0 F200, five-fold means. The `0.174` FPR is repeated as a material residual. |
| `+0.253`, `[0.144, 0.379]` | Pooled recall difference and 95% CI | `statistics/family_clustered_bootstrap.json`, `results.task_aligned_v1.F200.{recall_diff_aug_minus_M0,recall_diff_CI95}` | Paired family-clustered pooled difference, not a fold mean. |
| `-0.049`, `[-0.086, -0.014]` | Pooled FPR difference and 95% CI | Same bootstrap JSON, `results.task_aligned_v1.F200.{FPR_diff_aug_minus_M0,FPR_diff_CI95}` | Paired family-clustered pooled difference. |
| `+0.248`, `[0.177, 0.322]` | Pooled AUPRC difference and 95% CI | Same bootstrap JSON, `results.task_aligned_v1.F200.{AUPRC_diff_aug_minus_M0,AUPRC_diff_CI95}` | Paired family-clustered pooled difference. |
| one (`N=1`) | Truly novel confirmed independent positive | `reports/funnel.json`; `reports/independent_set_report.md` | Verdict is `INSUFFICIENT DATA`; no accuracy is computed. |
| `3.411 ms`, `9.514 ms` | Mean and p95 local processing time | `runtime/runtime_results.json`; `runtime/runtime_protocol.md` | Apple M1, preloaded-bytecode feature extraction and prediction only. |
| `M0`, `M1`, `M3`, `F200`, `G-DET`, `G-MUT`, `G-VOL`, `G-ADV`, `p95`, `95%` | Condition, protocol-group, percentile, and confidence-level notation | `claim_plan.md`; `method_claims_audit.md`; `task_aligned_result_provenance.md`; `family_clustered_bootstrap.md`; `runtime_protocol.md` | Identifiers/statistical notation. `M1` in “Apple M1” is the hardware label; mutation M1 is not otherwise used as a result condition in the prose. |

The qualitative statements that clean and M3 AUPRC improve, their FPR decreases, and their recall confidence intervals include zero are sourced to `task_aligned_advtrain_results.json` and `statistics/family_clustered_bootstrap.json`. The XGBoost/AuthGuard F200 trade-off is sourced to the former artifact (`opcode_xgb_aug` versus `authguard_aug` aggregate F200 entries).

## Explicit limitations included

1. The primary result generalizes only to held-out similarity families within the studied corpus, not universal malicious-delegate detection.
2. The artifact is an evaluation-grade scorer, not a complete wallet defense.
3. Family clusters are not verified attacker groups, do not remove all memorization, and do not justify claims about all earlier random-split studies.
4. The opcode-skeleton checker establishes a syntactic invariant, not EVM execution or behavioral equivalence.
5. Dynamic unreachability of appended post-`STOP` bytes is not formally proved.
6. Compound G-VOL F200 remains a serious weakness and is not recovered by G-ADV.
7. G-ADV evidence is restricted to the tested held-out severity; F200 FPR `0.174` remains material.
8. Clean M0 and M3 recall changes are not statistically resolved because their family-clustered confidence intervals include zero.
9. Positive labels inherit the USENIX artifact's labeling process, and `benign_cleared` is rule-silent weak-negative data rather than verified benign ground truth.
10. Exact-bytecode and family audits, limited sensitive-name coverage, and mutation findings do not eliminate label circularity.
11. Independent validation is insufficient for quantitative external generalization.
12. The full USENIX Gigahorse/Datalog pipeline was not executed; the local sensitive-name and external-call methods are lightweight approximations only.
13. The external-call approximation obtains high recall by flagging many negatives and is poorly discriminative.
14. Timing covers the local scorer core only and excludes parsing, RPC retrieval, caching, warning presentation, and user interaction.
15. Operational threshold calibration, retrieval, packaging, update procedures, and interface design remain unimplemented deployment work.

## Future work included

1. Conservative reachability-aware feature extraction.
2. Larger independently adjudicated malicious and benign EIP-7702 datasets.
3. Time-based, chain-based, and ecosystem-shift evaluation.
4. Execution-aware validation of mutations.
5. Comparison with the full Gigahorse/Datalog pipeline.
6. Calibrated selective warnings or escalation to heavier analysis.
7. Wallet-level latency and user-facing evaluation.

## Compliance confirmations

- **Protocol separation:** G-MUT, G-VOL, and G-ADV remain distinct. The Discussion explicitly identifies G-VOL as compound M3-style F200 and G-ADV as pure-M0 F200, and states that G-ADV does not recover G-VOL.
- **Aggregation labels:** `0.561/0.484/0.217 → 0.758/0.727/0.174` is labeled as fold-mean performance. `+0.253`, `-0.049`, and `+0.248` with their intervals are labeled as pooled, paired family-clustered differences.
- **Clean/M3 inference:** Clean M0 and M3 recall changes are explicitly described as not statistically resolved; no significant recall improvement is claimed.
- **Independent validation:** The verdict appears exactly as `INSUFFICIENT DATA`; no `1/1` accuracy is reported.
- **Baseline boundary:** The full USENIX pipeline is explicitly presented as not executed, with no superiority claim.
- **Deployment boundary:** No wallet, parser, RPC/cache path, warning UI, updater, or other deployment module is presented as implemented. Timing is not described as end-to-end latency.
- **Prohibited claims:** No priority, “first,” state-of-the-art, universal-detection, arbitrary/general-robustness, complete-recovery, external-validation-at-scale, or every-metric-dominance claim appears.
- **Existing-section integrity:** `git diff --name-only` restricted to the protected existing section files, frozen artifacts, figures, and result tables is empty. Only the two requested new sections, this audit, and the permitted evidence-map update are in Prompt 5 scope.
- **Anonymity:** The new manuscript and audit files contain no author name, affiliation, acknowledgment, repository URL, or identifying local filesystem path.
- **Old cohorts:** No original-cohort performance value was introduced; all main empirical values are task-aligned v1 values.
