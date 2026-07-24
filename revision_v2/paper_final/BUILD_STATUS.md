# Paper v3 build status

`main_final.tex` is the revised manuscript source. `AuthGuard_7702.pdf` is the
superseded pre-v3 PDF and must not be submitted.

## Latest build

`AuthGuard_7702_v3.pdf` was rebuilt successfully on 2026-07-24. It is an eight-page,
letter-size PDF with balanced final-page references, no overfull boxes, and no undefined
references or citations. The remaining LaTeX warnings are the intentionally absent author
block and minor underfull table text.

The isolated v3 build writes:

- `AuthGuard_7702_v3.pdf` -- revised submission PDF;
- `build_v3/AuthGuard_7702_v3.log` -- LaTeX build log; and
- `../logs/paper_final_v3/build.log` -- detached container/build log.

The first build creates the local `authguard-paper-tex:2022` image from
`Dockerfile.paper`; later builds reuse it.

Before release, run `audit_source_v3.py`, inspect the LaTeX log for overfull boxes and
undefined references, and replace the intentionally absent author block with the
submission-specific anonymous or camera-ready author block.
