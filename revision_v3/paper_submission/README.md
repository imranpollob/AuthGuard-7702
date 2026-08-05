# Revision-v3 LaTeX submission draft

This is a separate, visibly pre-label manuscript. It does not modify the user-provided
`/home/pollmix/Downloads/main (4).tex` or the revision-v2 manuscript.

The current draft is a seven-page, reviewer-complete pre-label paper. Its label-free population,
coverage, snapshot, decision, and external-control values are generated from frozen artifacts. To
refresh and verify those values before building:

```bash
python3 ../experiments/reporting/generate_prelabel_submission_assets.py
```

Build from this directory with:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

If `latexmk` is unavailable, the repository's verified TeX container can build it:

```bash
docker run --rm -v "$PWD:/work" -w /work authguard-paper-tex:2022 sh -lc '
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
'
```

The red macros at the top of `main.tex` must be populated mechanically from the one-shot
post-cutoff evaluation. Do not set `\resultsreadytrue` until:

1. the named reviewer readiness audit reports ready;
2. all 150 items have two independent primary reviews;
3. every disagreement has one adjudication;
4. the release/agreement files pass the strict evaluator;
5. the frozen evaluation has run once; and
6. the separately frozen operating-decision evaluator has run without a lock failure; and
7. the method or measurement branch in `../manuscript/09_SUBMISSION_BLUEPRINT.md` is selected from
   the primary paired interval.

Before submission, the LaTeX claim audit must report zero blockers and the final PDF must be
visually inspected.

After both locked evaluators succeed, generate the macros without copying values manually:

```bash
python3 ../experiments/reporting/generate_final_submission_assets.py \
  --primary ../results/human_final/dcrg_postcutoff_evaluation.json \
  --decisions ../results/human_final/postcutoff_decision_evaluation.json
```

The generated file records both input hashes, sets `\resultsreadytrue`, and selects `METHOD` only
when the preregistered full-minus-untyped confidence interval has a strictly positive lower bound.
