# Final Consistency and Static Integration Audit

Audit date: 2026-07-16. Scope: canonical manuscript sources and the complete 13-file Overleaf package. No frozen dataset, family assignment, model output, task-alignment artifact, or experiment implementation was modified.

## Integrated structure

`overleaf/main.tex` uses `\documentclass[conference]{IEEEtran}` and contains directly, in order: Abstract and Index Terms; Introduction; Background and Related Work; Problem Definition and Threat Model; AuthGuard-7702 Design; Dataset and Experimental Methodology; Evaluation; Discussion and Limitations; Conclusion; and References. All section prose, tables, captions, and TikZ architecture source are inline; the driver contains no `\input` command.

The title exactly matches the requested working title. The author field is anonymous. Bibliography style and driver are `IEEEtran` and `references`, respectively.

## Static LaTeX checks

| Check | Result |
|---|---|
| Balanced unescaped braces | PASS for the single consolidated `main.tex` |
| Input resolution | PASS: no `\input` command remains |
| Graphic resolution | PASS: all 3 referenced PDFs found |
| Labels | PASS: 16 unique labels; no duplicates |
| Internal references | PASS: 12 references; none unresolved |
| Citation keys | PASS: 14 used keys; all present |
| BibTeX keys | PASS: 14 unique entries; no duplicate, missing, or unused key |
| Packages | PASS: only `amsmath`, `amssymb`, `graphicx`, `booktabs`, `array`, `tikz`, `url`, and `cite` are loaded |
| Custom commands | PASS: none defined or required |
| Local/absolute paths | PASS: none found |
| Custom style dependencies | PASS: only standard `IEEEtran` and package files are referenced |
| Obsolete sections | PASS: all nine current sections are inline in `main.tex`; no external section file is referenced |
| Formatting constraints | PASS: no negative vertical/horizontal spacing, margin change, geometry override, reduced base font, or page-enlargement command |
| Plain-text parser | PASS: Pandoc parsed the consolidated main driver |
| Figure scripts | PASS syntax check; all four JSON sources parse |

These are static checks, not a LaTeX compilation claim. No TeX engine is installed and no local PDF of the complete paper was produced.

## Terminology and framing

- `AuthGuard-7702`, `task-aligned dataset`, `family-grouped evaluation`, and `rule-silent weak negatives` are used consistently.
- The two lightweight local baselines are named `sensitive-name rule approximation` and `external-call structural over-approximation`; neither is called the full detector.
- The manuscript names the `full USENIX Gigahorse/Datalog pipeline` and states that it was not executed.
- Mutations use the exact checker-scoped phrase `structure-preserving transformations under our opcode-skeleton checker` and explicitly deny dynamic-unreachability and EVM-behavioral-equivalence guarantees.
- Flooding is described as a `STOP` followed by benign-sourced bytes intended to model dead-code padding, not as formally unreachable code.
- The manuscript contains no priority wording, state-of-the-art claim, semantic-preservation claim, formal-verification claim, attacker-identity interpretation of families, or general-evasion claim.
- The standard XGBoost estimator is explicitly not a research contribution.

## Protocol and aggregation consistency

- G-DET, G-MUT, G-VOL, and G-ADV are defined separately in Methodology and remain separate throughout Evaluation and Discussion.
- G-VOL compound F200 recall `.130` is never presented as the baseline recovered to G-ADV `.727`.
- G-DET `.881` is never compared with G-ADV clean `.819/.863` as one experiment.
- G-ADV F200 fold means are labeled as fold means; the `.448→.702` family-pooled recall and paired differences are labeled pooled/family-clustered.
- Clean and M3 recall changes are explicitly not statistically resolved because their intervals include zero.
- The seeded random split is consistently a diagnostic, not a deployment estimate.
- All headline values are task-aligned v1; no old contract-resampled interval or original-cohort headline remains.

## Abstract and contribution consistency

- Abstract body: **167 words**. It contains three principal numerical clauses: family/random G-DET, G-ADV F200 fold means, and the paired family-clustered F200 recall difference.
- The task-aligned family result is primary, the random result is diagnostic, G-ADV F200 is explicitly pure-M0, and label/deployment limitations are visible.
- Introduction contains exactly **three** contribution items: implemented scorer; outcome-blind task alignment plus family-grouped evaluation; checker-defined benchmark plus source-balanced augmentation.
- Contribution wording agrees with the Evaluation and Discussion, and no contribution is assigned to the standard estimator architecture.

## Coherence and implementation-boundary review

- The duplicated score equation was removed from Design; Design now references the formal definition in the preceding threat-model section.
- Low-value malformed-input detail was compressed while retaining deterministic normalization/handling and the no-control-flow-recovery qualification.
- The architecture separates dashed, unevaluated integration context from solid implemented online scoring and offline fitting.
- Runtime prose and the architecture timing boundary include only preloaded-bytecode feature construction and prediction. Parser, RPC/cache, wallet, and warning interaction remain excluded.
- Every table and figure is introduced before or near its source placement, and all internal references resolve statically.
- No absent supplement, non-existent appendix, unimplemented deployment component, or forward reference remains.

## Figure and table review

- Figures: **4** total—one stacked one-column TikZ architecture embedded in `main.tex` and three vector result PDFs.
- Tables: **4** total—dataset composition, G-DET, G-MUT, and G-ADV.
- The architecture was converted from a very wide single row to a stacked layout with readable source font sizes and explicit integration/timing boundaries.
- Result PDFs were inspected through 160-dpi rasterizations. Labels were not clipped; internal titles are compact; protocols are explicit.
- Grayscale redundancy is present: random/family uses marker shape/fill, mutation/flooding uses markers and line styles, and G-ADV uses hatch plus fill.
- PDF metadata is anonymous. Each result PDF is a one-page vector PDF.
- Table results use three-decimal formatting. Captions state protocol and aggregation; threshold dependence is stated where relevant.
- Table I's final row is `global corpus`, and its note warns that subset family counts overlap and must not be summed.
- Table IV uses `table*` because the model names and six columns are not credibly readable in one column. Bolding reflects per-condition metric winners rather than universal dominance.

## Corrections applied in the final integration pass

1. Created the IEEEtran main driver, exact title, anonymous author field, ordered section inputs, and bibliography driver.
2. Built a 14-entry bibliography containing exactly the cited literature, with primary-record metadata.
3. Replaced formal-unreachability wording with post-`STOP` padding language and added dynamic/EVM-equivalence qualifications.
4. Replaced shortcut-blocking wording with the narrower opportunity-reduction statement and retained benign FPR as the empirical check.
5. Converted the architecture to a stacked one-column layout and preserved implemented-versus-integration boundaries.
6. Changed the dataset-table final row from `total` to `global corpus` while preserving the overlap note.
7. Compressed malformed-input/parser detail.
8. Removed a duplicated scorer equation and tightened the Design transition.
9. Removed prohibited priority-like use of “first” and tightened the Discussion's generalization boundary.
10. Converted figure and figure-script paths to package-relative paths; included the four task-aligned JSON sources required by the scripts.
11. Flattened all sections, tables, captions, and TikZ source into one self-contained `main.tex` and removed the now-redundant external TeX fragments.
12. Rechecked every value, caption, reference, citation key, and PDF metadata item.

## Remaining integration risks

1. Final page count, float order, table width, TikZ rendering, reference line breaks, and overfull boxes require the initial Overleaf build.
2. The stacked architecture is source-reviewed but cannot be visually inspected until TikZ is rendered by Overleaf.
3. The current base Python environment lacks Matplotlib/NumPy, so the optional generation scripts were syntax-checked but not re-executed in this pass. The prebuilt anonymous vector PDFs are present and are the compilation inputs.
4. Huang et al. remains an official prepublication; final USENIX page metadata should be rechecked at camera-ready time.
5. The manuscript is approximately 5,880 words before references with four figures and four tables. It may exceed eight pages and needs a measured Overleaf reduction pass.

**Consistency result: PASS for static Overleaf integration, subject to rendered review.**
