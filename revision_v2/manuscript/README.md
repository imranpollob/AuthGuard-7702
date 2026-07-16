# Revision-v2 manuscript build

The frozen manuscript under `paper_build/` is never edited. Phase 6 writes the revised source
and generated result tables here.

Rebuild order:

```bash
revision_v2/.venv/bin/python revision_v2/experiments/manuscript/generate_tables.py
revision_v2/.venv/bin/python revision_v2/experiments/manuscript/integrate_manuscript.py
cd revision_v2/manuscript
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

`tables/numbers_provenance.json` maps every generated table to machine-readable v2 sources.
`integration_provenance.json` records the source manuscript hash, applied claim corrections,
and result files used by the integration step.

The manuscript remains a pre-freeze draft until independent human label adjudication and the
corpus redistribution/licensing decision are complete.

No TeX engine is installed on the finalization host. `static_audit.json` therefore verifies
source structure and local inputs, graphics, bibliography, anonymity, and retired wording;
the four-command TeX build above remains an external verification step.
