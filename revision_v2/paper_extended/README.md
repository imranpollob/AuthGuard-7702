# AuthGuard-7702 Extended Paper

This directory contains a standalone, reviewer-informed extended draft of the revised paper. It
does not modify the frozen manuscript under `paper_build/`.

## Contents

- `main.tex`: complete IEEE conference manuscript, including extended appendices;
- `references.bib`: local bibliography;
- `tables/`: reusable evidence tables;
- `figures/`: TikZ architecture figures and generated PDF result figures;
- `scripts/generate_figures.py`: reproducible chart generator; and
- `audit_source.py`: static LaTeX/path/citation and numerical-provenance audit.

## Rebuild figures

```bash
python3 scripts/generate_figures.py
```

## Audit the manuscript source

From this directory:

```bash
python3 audit_source.py
```

## Compile

With a TeX Live installation that includes `IEEEtran`, `tikz`, and `latexmk`:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

For Overleaf, upload this directory without changing its internal `figures/` and `tables/`
structure and set `main.tex` as the main document.

The current development host does not provide a TeX engine, so repository validation is static;
the source audit checks balanced braces, local inputs and graphics, references, citations,
anonymous author metadata, forbidden overclaims, and headline values against result artifacts.
