# Eight-Page Budget

Target compiled length: **7.78 pages**, including references and all floats. This leaves about 0.22 page below the hard eight-page limit for float movement and final IEEE typesetting variation.

## Section allocation

| Section | Target pages | Allowed brief range | Float allocation inside target | Compression rule |
|---|---:|---:|---|---|
| Abstract + Index Terms | 0.25 | 0.25 | none | 150--170 words; at most four numeric results |
| 1. Introduction | 0.75 | 0.70--0.80 | none | three contributions, no roadmap paragraph if space is tight |
| 2. Background and Related Work | 0.78 | 0.75--0.90 | none | three compact subsections; citations over taxonomy prose |
| 3. Problem Definition and Threat Model | 0.45 | 0.40--0.55 | none | one formal task definition plus scoped adversary |
| 4. AuthGuard-7702 Design | 1.05 | 1.00--1.20 | Figure 1 | no pseudocode; describe standard XGBoost in one paragraph |
| 5. Dataset and Experimental Methodology | 0.85 | 0.80--1.00 | Table 1 | protocol groups in one compact paragraph/box |
| 6. Evaluation | 1.95 | 1.90--2.20 | Tables 2--4; Figures 2--3 | results-first RQ structure; no duplicate prose and captions |
| 7. Discussion and Limitations | 0.48 | 0.45--0.60 | none | prioritize limitations; remove generic implications first |
| 8. Conclusion | 0.22 | 0.20--0.30 | none | one compact paragraph |
| References | 1.00 | approximately 1.0--1.3 | bibliography | retain only directly used citations |
| **Total** | **7.78** | hard maximum 8.00 | 4 tables, 3 figures | 0.22-page safety margin |

The section numbering in the final manuscript will count Abstract separately and use Sections I--VIII or the IEEE class’s automatic numbering; the requested content headings remain unchanged.

## Float budget

| Float | Format | Target footprint | Placement |
|---|---|---:|---|
| Figure 1: prototype architecture | one column, vector | 0.26 page | Design |
| Table 1: dataset and family composition | one column | 0.18 page | Methodology |
| Table 2: G-DET family-grouped metrics | one column, small text | 0.30 page | Evaluation/RQ1 |
| Figure 2: random versus family AUPRC | one column | 0.24 page | Evaluation/RQ2 |
| Table 3: G-MUT M0--M3 recall | one column | 0.22 page | Evaluation/RQ3 |
| Table 4: G-ADV AuthGuard outcomes | one column or compact `table*` | 0.30 page | Evaluation/RQ4 |
| Figure 3: G-ADV held-out robustness | one column | 0.25 page | Evaluation/RQ4 |
| **Approximate float total** |  | **1.75 pages** | included within section targets |

Captions should state protocol and metric but not repeat every value in adjacent prose.

## Content density controls

- Main text target: approximately 5,000--5,500 words including captions, subject to actual IEEE compilation. Page count, not word count, is authoritative.
- Abstract: 150--170 words.
- Contribution list: three items, at most two lines each in double-column format.
- Related work: approximately 18--24 carefully chosen citations; avoid a long catalog.
- Method descriptions: no algorithm environment unless a reviewer could not reproduce the split/weighting without it.
- Use one notation set: M0--M3, F25--F200, and G-DET/G-MUT/G-VOL/G-ADV only in methodology/captions where it saves space.
- Put threshold sensitivity, per-fold values, all seen G-ADV conditions, explanation audit, and independent funnel in the anonymous supplement/artifact.

## Cut order if compilation exceeds 7.90 pages

1. Remove Figure 3 and retain Table 4 plus one paired-results sentence.
2. Remove opcode baselines from Table 3 except opcode-XGB.
3. Compress Table 1 label-source prose into footnotes.
4. Replace Figure 1 with a narrow pipeline schematic.
5. Remove secondary-task results and the 76-designator detail from the main text.
6. Shorten related-work exposition while retaining citations.

Do **not** cut:

- the label-provenance limitation;
- the random-versus-family evidence;
- the G-MUT/G-ADV protocol distinction;
- the clean-recall reduction;
- the statement that the full USENIX pipeline was not run;
- the local-latency scope exclusion.

## Build gate

No TeX engine (`pdflatex`, `latexmk`, `xelatex`, `lualatex`, or `tectonic`) is installed in the current environment. The 7.78-page plan is therefore a layout budget, not a compiled verification. Before submission:

1. build with the exact IEEE conference class used by ICTAI;
2. record total pages from the generated PDF;
3. inspect float placement and font embedding;
4. target 7.7--7.9 pages after the bibliography stabilizes;
5. fail the build if the PDF exceeds eight pages.
