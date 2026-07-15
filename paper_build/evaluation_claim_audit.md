# Evaluation Claim Audit

Audit date: 2026-07-15. Reviewed files:

- `paper_build/sections/evaluation.tex`
- `paper_build/tables/gdet_performance.tex`
- `paper_build/tables/gmut_robustness.tex`
- `paper_build/tables/gadv_results.tex`
- the three figure-generation scripts and generated PDFs
- the Prompt 4 additions to `paper_build/claim_to_evidence.md`

Task-aligned machine-readable artifacts were treated as authoritative. Earlier sections, datasets, folds, implementations, and saved experiment results were not edited.

## Draft size

- Pandoc-rendered Evaluation count: **1,123 words**, including input tables, captions, and notes; raw plot-internal labels are excluded.
- Estimated IEEE footprint: **approximately 2.65 pages**, including three tables and three figures. This is a planning estimate because no TeX engine is installed.

## Claim checks

| Risk | Finding | Disposition |
|---|---|---|
| Unsupported superiority | AuthGuard is described as having the highest G-DET AUPRC only among the seven directly evaluated non-tautological methods. | Supported by G-DET `.881`, above `.784` and all other included rows. No comparison with the full USENIX pipeline or external papers. |
| Every-metric dominance | G-ADV prose explicitly states that opcode-XGBoost-aug has higher F200 recall `.756` versus `.727`, while AuthGuard-aug has higher AUPRC and lower FPR. | No dominance claim; Table 4 bolding exposes the metric-specific winners. |
| Unsupported robust/generalizes language | The only affirmative robustness wording is scoped to improvement under tested held-out transformations. “Arbitrary-transformation robustness” is explicitly denied. | Acceptable. Flat structural-rule recall is not called useful robustness. |
| Semantic-equivalence overclaim | The manuscript does not use “semantics-preserving.” | Uses checker-scoped structure preservation and immediately states that execution/behavior equivalence is not proved. |
| G-VOL/G-ADV conflation | G-VOL `.130` appears only in RQ3; G-ADV `.484→.727` appears only in RQ4. Figure 3 caption states that G-VOL is not pure-M0 G-ADV F200. | No before/after conflation. |
| G-DET/G-ADV conflation | G-DET `.881` and G-ADV clean `.819/.863` occur in separate RQs, tables, and captions. | No same-protocol comparison. |
| Fold mean / pooled conflation | Figures and Tables 2–4 identify fold means. Family-bootstrap prose explicitly calls `.448→.702` pooled and separates its paired intervals from fold means. | No mixed aggregation row or unlabeled interval. |
| Superseded inference | Only task-aligned family-clustered intervals from 10,000 family-resampled replicates are used. | No original-family or contract-resampled CI in paper prose, tables, figures, or captions. |
| Full USENIX reproduction | RQ1 states that the local rules do not reproduce the full Gigahorse/Datalog pipeline and that it was not run. | No reproduced-system or superiority claim. |
| Independent validation | RQ1 reports one confirmed novel positive only to conclude that quantitative external validation is insufficient. | No accuracy, generalization, or at-scale validation claim. |
| End-to-end latency | RQ5 calls the result scorer-core timing and lists all excluded integration stages. | No wallet, network-inclusive, complete, deployed-real-time, or Gigahorse-speedup claim. |
| Hidden clean trade-off | Clean G-ADV AUPRC/recall/FPR is reported for both AuthGuard variants. The clean recall CI is reported as including zero. | Trade-off and uncertainty visible. |
| Hidden false positives | Residual F200 FPR `.174` is called material; opcode-XGBoost-aug FPR `.386` is shown. | No omitted residual FPR. |
| Rule-label circularity | RQ1 preserves artifact-positive and weak-negative scope; leakage assertions are not used to claim ground-truth validity. | No universal malicious-delegate detection claim. |
| Family interpretation | RQ2 calls families bytecode-similarity groups rather than attacker identities and denies removal of all memorization. | No attacker-independence claim. |
| Dynamic unreachability | Evaluation uses “post-STOP flooding intended to model padding.” | Does not claim dynamic unreachability. |

## Protocol-separation checks

- **G-DET:** only task-aligned family/random detection values appear in RQ1–RQ2, Table 2, and Figure 2.
- **G-MUT:** only clean-model held-out-positive M0–M3 retained recall appears in Table 3 and Figure 3(a).
- **G-VOL:** only compound metadata/address/selector plus flooding retained recall appears in Figure 3(b) and its RQ3 paragraph.
- **G-ADV:** only clean-validation-threshold values and paired family-bootstrap inference appear in RQ4, Table 4, and Figure 4.
- No figure overlays incompatible groups. Figure 3 contains G-MUT and G-VOL as separately titled panels with an explicit non-equivalence caption.

## Statistical-language checks

- AUPRC is treated as threshold-free; precision, recall, F1, and FPR are tied to the correct protocol threshold.
- Population SD is shown only for G-DET AUPRC.
- No SD is presented as a confidence interval.
- Family-bootstrap intervals use the family as the resampling unit and preserve pairing.
- F200 recall, FPR, and AUPRC intervals exclude zero; prose says those intervals support aggregate improvement under that condition.
- Clean and M3 recall intervals include zero; prose says those recall changes are not statistically established.
- Clean and M3 FPR intervals exclude zero; prose limits support to their FPR reductions.
- The word “significant” is not used.

## Figure checks

- Each script loads numerical values from the named task-aligned JSON at runtime; no result array is hard-coded.
- PDFs are vector, PDF 1.4, one page each, with embedded subset TrueType fonts.
- Repeated generation produced byte-identical PDFs after suppressing creation/modification timestamps. SHA-256 values are `97ea8cc8...9063b33a` (random/family), `5385f86f...47e3351a` (mutation/flooding), and `8f14cc62...013d030` (G-ADV).
- Random/family uses circle versus open-square encoding and direct method labels.
- Mutation/flooding uses distinct markers and line styles in addition to a colorblind-safe palette.
- G-ADV uses black-edged bars and hatching in addition to color.
- Figures have no oversized internal title and remain readable in the inspected 180-dpi rasterizations.
- `pdfinfo` reports `Author: Anonymous` and anonymous creator metadata for all three PDFs.
- String scans found no personal filesystem path, user name, email, institution, or nonanonymous author metadata.

## Table checks

- All values use three-decimal formatting and match their task-aligned JSON after rounding.
- Every caption names G-DET, G-MUT, or G-ADV, the aggregation, and threshold policy where applicable.
- The G-MUT caption contains the checker qualification.
- Table 4 is `table*` because full model names and six columns are not legible at one-column width.
- Table 4 bolds per-condition metric winners; this exposes opcode-XGBoost-aug's M3/F200 recall advantage rather than bolding every AuthGuard value.

## Anonymity and scope

- No generated source or PDF contains a personal name, email, affiliation, home-directory path, wallet address, or repository URL tied to an author.
- The scripts use paths derived from `__file__`, not hard-coded local paths.
- No Discussion, Limitations, or Conclusion section was created.
- Corrected Sections 1–5 and all frozen artifacts remain unchanged.

## Unresolved issues

1. No TeX engine is installed, so float placement, final table width, cross-references, and compiled page count are not verified. Pandoc parses the Evaluation section and all input tables, and brace/diff checks are used instead.
2. Figure 3, Figure 4, and Table 4 are double-column floats. Their exact placement must be inspected in the final IEEE build.
3. The estimated Evaluation footprint is a layout estimate, not a PDF measurement.
4. The G-DET saved artifact does not contain FPR; G-MUT/G-VOL contain retained recall only. These are marked `[NOT MEASURED]` in the number audit rather than inferred.
5. The bootstrap JSON provides AUPRC difference intervals only for F200, not clean M0 or M3. No missing interval is synthesized.
6. Independent external validation remains numerically unresolved (`N=1`); Evaluation uses it only as a validity qualification.
7. Section inputs and figure paths are repository-root-relative. A final driver compiled from another working directory must set `\input@path`/`\graphicspath` or adjust those paths.

## Final verdict

The Evaluation claims are supported under their stated task-aligned protocols. No old-cohort headline, priority claim, universal detection claim, arbitrary-transformation claim, semantic-equivalence claim, full-USENIX reproduction claim, large-scale independent-validation claim, or end-to-end wallet-latency claim appears in the manuscript deliverables.
