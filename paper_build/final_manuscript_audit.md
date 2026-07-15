# Final Manuscript Audit and Hostile Review

Audit date: 2026-07-15.

## Concise paper summary

AuthGuard-7702 studies whether delegate runtime bytecode can provide a lightweight warning signal before an EIP-7702 authorization. The work combines an implemented decompiler-free XGBoost scorer with outcome-blind task alignment, frozen bytecode-similarity families, family-grouped evaluation, checker-defined mutation/flooding stress tests, and source-balanced adversarial augmentation. On artifact-derived positives versus rule-silent weak negatives, family-grouped G-DET AUPRC is `.881 ± .028`; random evaluation is more optimistic. Augmentation partially improves held-out pure-M0 F200 performance, but compound G-VOL F200, label circularity, weak negatives, independent validation, and deployment remain material limitations.

## Three strongest contributions

1. **Implemented pre-authorization scoring boundary.** A deterministic bytecode-to-score artifact demonstrates that inexpensive learned screening can operate without decompilation or transaction history, while clearly separating the scoring core from wallet/RPC/UI integration.
2. **Task-valid, dependence-aware evaluation.** The outcome-blind handling of designators and contradictory exact-bytecode labels, together with preserved family folds, makes the empirical task more defensible and exposes a `.094` random-versus-family AuthGuard gap.
3. **Checker-defined evasion and augmentation evidence.** Distinct G-MUT, G-VOL, and G-ADV protocols reveal both retained signal and failure: selector rewriting collapses the name approximation, compound flooding reduces AuthGuard recall to `.130`, and source-balanced augmentation partially improves pure-M0 F200 with family-clustered paired evidence.

## Three strongest reasons for acceptance

1. The paper addresses a timely pre-authorization security decision created by EIP-7702 and positions itself carefully relative to two directly related studies.
2. Its methodological discipline is stronger than the model novelty: task alignment is outcome-blind, family identities are frozen, incompatible protocols are separated, paired uncertainty resamples families, and negative results remain visible.
3. The artifact boundary is unusually candid. The paper does not disguise weak labels, one-case independent validation, an unexecuted full baseline pipeline, checker limitations, residual FPR, or missing wallet integration.

## Five strongest possible reviewer criticisms

1. **Label circularity and weak negatives.** Positives originate from one USENIX artifact and `benign_cleared` means only rule-silent. AuthGuard may learn source-labeling regularities rather than a general malicious-delegate concept.
2. **Insufficient independent validation.** Only one truly novel independently confirmed positive survived the frozen funnel. The `INSUFFICIENT DATA` verdict is honest but leaves external generalization quantitatively unresolved.
3. **Mutation semantics are not established.** The opcode-skeleton checker is syntactic; it does not prove dynamic unreachability, behavioral equivalence, or preservation under execution. This limits conclusions about attacker-realizable evasion.
4. **Incremental AI architecture.** XGBoost over engineered bytecode features is conventional. Reviewers must value the input/evaluation/tool contribution; those seeking a modeling advance may judge the AI novelty modest.
5. **Incomplete systems comparison and deployment.** The full Gigahorse/Datalog pipeline was not executed, and the measured path excludes retrieval, parsing, calibration, warning UI, and users. Thus the paper does not establish operational wallet effectiveness or a full-pipeline accuracy/runtime trade-off.

## Novelty and methodological disposition

- **Unsupported novelty statement:** none found. The manuscript contains no priority, state-of-the-art, or universal-detection statement and explicitly says the estimator architecture is not a contribution.
- **Unresolved methodological issues:** label circularity; possible contamination of weak negatives; family clusters are not attacker identities; no time/chain/ecosystem-shift experiment; one-case independent validation; syntactic rather than execution-aware mutation validation; compound G-VOL F200 remains unresolved; full USENIX pipeline unexecuted; threshold calibration and deployment evaluation absent.
- **AI contribution visibility:** sufficiently visible for an applied AI-tools paper. The paper explains the 773-feature representation, standard estimator, score boundary, family-aware learning protocol, and augmentation trade-offs. Its strength is responsible application/evaluation rather than algorithmic novelty.
- **Tool contribution visibility:** sufficiently visible at prototype level. The architecture, deterministic feature path, local timing boundary, and exclusion list make the implemented artifact concrete. It is not yet a deployed tool.
- **Task-alignment motivation:** clear and central. Designators are invalid delegate-runtime inputs, deterministic bytecode cannot resolve identical-byte conflicts, the policy is outcome-blind, and changed rerun metrics show why task validity precedes comparison.
- **Label-circularity honesty:** clear. The Abstract, Methodology, Evaluation, and Discussion all scope the target and deny verified malicious/benign ground truth.
- **Evaluation support for Abstract/contributions:** yes. The `.881/.975` G-DET values, distinct G-MUT/G-VOL findings, G-ADV fold means, family-clustered F200 interval, residual `.174` FPR, and local timing all trace to task-aligned artifacts and support the scoped statements.
- **Is another experiment necessary before submission?** No additional experiment is logically required to submit the current narrowly scoped claims. However, a larger independently adjudicated external set would provide the largest scientific improvement and may be requested by reviewers. Execution-aware mutation validation and full-pipeline comparison are the next most valuable additions; the paper correctly presents them as future work rather than completed evidence.

## Estimated manuscript footprint

- Approximate prose before references: **5,880 words**, including table/caption text and excluding bibliography entries and plot-internal labels.
- Floats: **4 figures** and **4 tables**.
- References: **14**.
- Estimated IEEE conference footprint without compilation: **approximately 9--10 pages including references**. This is deliberately a range, not a page-count claim. The authoritative count must come from Overleaf.

The manuscript therefore likely needs a measured reduction pass after the initial Overleaf build. Essential methodological qualifications should not be deleted speculatively.

## Prioritized page-reduction plan

Apply only after observing the Overleaf page count and float placement:

1. Remove duplicated explanations across Introduction, Evaluation, and Discussion while preserving each limitation once at its strongest location.
2. Shorten Background and Related Work, especially repeated information-boundary comparisons, without removing directly related EIP-7702 work.
3. Shorten parser and standard-classifier implementation detail; retain feature dimensions, deterministic handling, and the no-control-flow-recovery boundary.
4. Merge Evaluation prose with captions where the same table cells are repeated sentence-by-sentence.
5. Remove the G-ADV bar figure before any unique-evidence float; Table IV and paired-inference prose already carry its values.
6. If still necessary, remove secondary baseline rows from the main tables and summarize them in artifact text, retaining AuthGuard, opcode-XGBoost, and the two rule approximations needed for interpretation.
7. Compress Discussion implications and future-work phrasing, but retain label circularity, independent insufficiency, checker limits, compound G-VOL failure, residual F200 FPR, and full-pipeline non-execution.
8. Combine table abbreviation notes and shorten captions after verifying that protocol and aggregation remain explicit.
9. Shorten references only by removing a citation and its corresponding weakly relevant prose; do not delete bibliography fields or retain uncited entries.

Do **not** cut task alignment, label provenance, family-grouped evaluation, protocol distinctions, compound G-VOL `.130`, residual G-ADV F200 FPR `.174`, independent-validation insufficiency, or the full-USENIX non-execution statement.

## Exact remaining author actions in Overleaf

1. Upload the complete contents of `paper_build/overleaf/` with directory structure preserved.
2. Set `main.tex` as the main document and build with pdfLaTeX/BibTeX.
3. Record the actual total page count, including references and all floats.
4. Inspect the stacked TikZ architecture at one-column scale for arrow overlap, clipped labels, and readable text.
5. Inspect the three result PDFs for one-/two-column readability and grayscale distinction in the compiled document.
6. Check placement/order of the two `figure*` floats and `table*`, especially whether they drift beyond their introducing RQs.
7. Resolve every overfull/underfull box without negative spacing, margin changes, or font reduction below IEEE norms.
8. Confirm all citations render in order and the Huang prepublication entry formats acceptably.
9. If the paper exceeds eight pages, apply the reduction plan iteratively and recheck every protocol/limitation sentence after each cut.
10. Inspect the final PDF properties for author, creator, path, and attachment metadata before submission.

# READY FOR OVERLEAF REVIEW

This label means the source package is statically integrated and ready for rendered review. It does not mean the paper is submission-ready; compilation, page count, float placement, and visual inspection remain incomplete.
