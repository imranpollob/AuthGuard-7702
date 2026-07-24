# AI review verification and ROI roadmap

## Executive decision

The review correctly identified the paper's largest threat: the old comparison confounded
token budget, hierarchy, and attention, and the transformed-input path did not enforce the
declared cap. Those points are now resolved by the v3 controlled experiment. The resulting
claim is narrower but stronger: learned chunk attention is supported over mean aggregation
on clean bytecode and is substantially more robust than a parameter- and budget-matched flat
encoder under cap-correct Flood-200%. Clean hierarchy superiority is not supported.

## Review-by-review verification

| Review item | Verdict | Evidence or action |
|---|---|---|
| 1. Add architecture ablations | Valid; completed | Five controlled variants isolate budget, layout, and aggregation across 90 model/seed/fold units. |
| 2. Fix Flood-200% budget confound | Valid; completed | Clean and transformed rows now obey each model's declared cap. The surviving 16K attention-vs-flat F200 difference is +0.098 AUPRC, 95% CI [0.059, 0.154]. |
| 3. Promote first-STOP as an attack/result | Overstated | The existing semantic audit shows post-first-STOP code is executed in 92/100 bounded calls; first-STOP truncation preserves the fingerprint in only 22/100. It is a predictive but semantically unsafe shortcut, not the proposed zero-cost canonicalization or a demonstrated recall-collapse attack. |
| 4. Expand legitimate EIP-7702 controls | Valid; unresolved | The five curated cases remain qualitative. The 797-contract external set gives transfer evidence but is not the deployment population. Expansion requires provenance-backed project registries or verified deployments, not relabeling source-unflagged rows as benign. |
| 5. Measure source-analyzer cost | Valid; prepared | Docker is now usable, the official Gigahorse image digest is pinned, and a balanced 60-family sample is frozen. The decompilation cost run remains pending and cannot yet support a runtime comparison. |
| 6. Manually validate labels | Valid; package ready, human-dependent | The source rule defines the positive class and source silence defines weak negatives. A blinded 170-item, three-reviewer package already exists under `revision_v2/artifact/label_audit/`; no completed human form is present. Independent adjudicators are required, and automated relabeling would not solve circularity. |
| 7. Add a temporal split | Valid in principle; unavailable | The frozen corpus contains no timestamp, collection date, or block-height field. A temporal split must not be synthesized from row order. |
| 8. Test Qi et al. data | High value if obtainable | This would address independent-label transfer, but no task-compatible bytecode/label artifact is currently present in the repository. |
| 9. Improve baseline credibility | Valid; substantially completed | The paper no longer relies on “first among seven.” It centers parameter-matched Flat-16K, Flat-2K, attention-2K, mean-16K, and attention-16K controls plus XGBoost. The Transformer budget error was corrected from 2,048 to 1,024. |
| 10. Package artifact and browser runtime | Valid; partially completed | Runs are resumable and auditable with per-row predictions, donor ledgers, checkpoints, and verifiers. Local complete-path latency is measured; ONNX/WASM and a releasable anonymous artifact remain future work. |
| 11. Tighten framing and title | Valid; completed | The title is shorter, repeated priority claims were removed, and the paper leads with the controlled clean--robustness finding rather than model-count ranking. |

## Completed high-ROI strengthening

1. Fixed the transformed-input capacity bug and audited retained-token counts.
2. Ran the parameter-controlled long-context study: 90 units and 78,840 predictions.
3. Used fold-stratified, family-clustered intervals that mirror fold-then-seed reporting.
4. Tested a frozen multi-statistic follow-up only on folds 1--4 and retained its negative
   robustness result rather than continuing test-fold architecture search.
5. Replaced the 181,877-parameter reference architecture with the supported 30,050-parameter
   attention model.
6. Re-measured external controls and the complete local path for the promoted checkpoint.
7. Rewrote the title, abstract, contributions, methods, result tables, discussion,
   limitations, conclusion, and architecture figure around the new evidence.

## Remaining work ordered by expected paper value

### Priority A — complete the staged-analysis motivation

Run the pinned Gigahorse cost experiment on the frozen 60-contract sample. Report cold and
warm latency, failures/timeouts, peak memory, and output size. This directly answers why a
millisecond-scale triage layer may be useful before deeper analysis. Do not claim equivalence
to the source study's client rule.

### Priority B — improve real benign-population evidence

Expand the curated EIP-7702 control set from documented project deployment registries with
address, chain, source URL, retrieval block, bytecode hash, and deduplication provenance. A
smaller high-confidence set is preferable to a large unverifiable scrape. Freeze it before
scoring.

### Priority C — independent label evidence

Pursue one of two clean paths:

1. obtain a task-compatible independent EIP-7702 phishing/delegate corpus and perform a
   locked cross-dataset test; or
2. have at least two independent reviewers adjudicate the existing 170-item stratified
   label-audit package and report agreement and model performance against consensus.

### Priority D — artifact and deployment packaging

Create the anonymous release bundle, environment lock, one-command reproduction path, and
generated paper tables. After the scientific claims are frozen, export the compact model to
ONNX/WASM and measure browser-extension preprocessing plus inference. This is deployment
evidence, not a substitute for Priorities A--C.

## Work not worth forcing

- Do not fabricate a temporal split without time metadata.
- Do not enlarge the benign set by treating source-unflagged delegates as verified benign.
- Do not promote first-STOP truncation as semantically safe.
- Do not tune another architecture on the already used confirmatory folds.
- Do not restore broad “state of the art,” universal robustness, or end-to-end wallet
  latency claims.
