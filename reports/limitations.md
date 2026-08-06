# Limitations

Run `v2`. Written against measured artifacts; every figure cited is in `data/` or `reports/`.

## 1. The headline result is null, and the test set is small

All three experiments score at chance (AUPRC 0.201–0.227 against a prevalence of 0.205; AUROC
0.486–0.549). Every confidence interval contains the baseline. The test set is **51 contracts, 44
decidable, 9 positive**. With 9 positives, the 95% CI on AUPRC spans roughly [0.11, 0.43] — wide
enough that this evaluation could not have detected a moderately good model either. **The correct
reading is "no evidence of skill", not "proof of no skill".**

Per-quartile and per-label breakdowns rest on 1–4 positives per cell and are noise.

## 2. Labels are LLM-proposed and human-accepted, not independently derived

All 300 reviewed runtimes were accepted as proposed (`ACCEPT_LLM_LABEL`, 0 changed, 0
unresolved). The gold labels therefore measure agreement with the v3 rubric, not an independent
semantic judgement. Two consequences:

- Inter-rater agreement cannot be computed — there is one reviewer and one pass, so no kappa,
  no adjudication, no disagreement statistics are reportable.
- A 100% acceptance rate is itself a caution: it is consistent either with a well-calibrated
  rubric or with insufficiently adversarial review. Nothing in this dataset distinguishes those.

## 3. The features cannot express what the labels encode

Labels turn on guard dominance — whether a reachable dangerous capability is dominated by an
authorization check. The model sees 36 structural opcode/selector counts, which do not encode a
control-flow dominance relation. The null result is therefore partly a statement about this
feature class, not only about sample size.

Using the reachability/guard features that define the labels would be circular and was
deliberately avoided; see `reports/model_results.md`.

## 4. Coverage: 43% of the population is not adjudicable from bytecode

324 of 752 screenable delegates are U. The dominant cause is a DELEGATECALL whose callee is
computed at runtime (module/plugin dispatch), which no static slot lookup resolves — proxy
resolution recovered only 5 implementations out of 56 candidates, and all 5 implementations were
themselves incomplete, so **no label changed**. This is a ceiling on any bytecode-only screening
claim, not a temporary gap.

## 5. Temporal separation is real but short

Test contracts are all first-observed at or after block 25,660,356, and no family crosses splits.
But the whole collection spans ~100,444 blocks (~2 weeks), so "temporal generalisation" here means
across days, not releases. 11 development contracts were observed after the cutoff because their
family began before it (kept in development, never in test).

## 6. Population scope

Ethereum mainnet only, one ~2-week window, 760 distinct delegates. Not a census of EIP-7702
usage; other chains and earlier periods are absent.

## 7. Propagation assumption

Labels propagate across identical runtime bytecode (6 of 306 gold rows). This assumes identical
bytecode implies an identical security verdict, which is sound for code-level review but ignores
per-account state: the same delegate bytecode can hold different storage per authorizing EOA. No
label propagated across similarity families.

## 8. Analyzer limits are bounded but not eliminated

Two real defects were found and fixed during this work (silent state-dedup truncation at stack
depth 8; cap truncation), and one over-approximation artifact (state widening producing
uncorroborated guard-cut sites) is now discarded by a corroboration rule. Residual limits remain:
memory provenance is not tracked transitively back to calldata, so `unresolved_target` sites
cannot be adjudicated; and 15/40 sampled contracts still contain a dangerous op the traversal
never reached.

## 9. Single reviewer, single rubric version, no external validation

No second annotator, no external ground truth (no incident data, no confirmed exploits), and no
comparison against a reference analyzer such as Gigahorse on this population. R1 was validated
internally (25/25 confirmed, one systematic false-positive pattern found and fixed), but internal
validation of a rule against its own analyzer is weaker than external corroboration.
