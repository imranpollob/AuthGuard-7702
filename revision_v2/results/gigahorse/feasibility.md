# Phase 5 — Reference-Analyzer (Gigahorse/Datalog) Feasibility: OPTION B (BLOCKED)

## Decision
Full reproduction of the USENIX Gigahorse/Soufflé/Datalog pipeline is **NOT feasible** in
this environment within the time box. Recorded as Option B with a limited agreement analysis
from shipped intermediate outputs.

## Attempted setup and exact blockers
1. **Soufflé (Datalog engine): absent and not installable in-box.** `which souffle` → none;
   not present via Homebrew; no prebuilt binary. Building from source requires a C++17
   toolchain plus bison/flex/CMake and a lengthy compile — outside the strict time budget and
   unverifiable here.
2. **Container runtime: absent.** `docker`, `colima`, `podman` all missing, so the upstream
   Gigahorse Docker image (the documented reproducible path) cannot be pulled or run.
3. **Gigahorse client library not shipped.** The artifact's `eoa_detect/decompile/analyze.dl`
   begins with `#include "../clientlib/decompiler_imports.dl"`,
   `#include "../clientlib/loops_semantics.dl"`, `#include "../clientlib/guards.dl"`,
   `#include "../clientlib/vulnerability_macros.dl"`. None of these `clientlib/*.dl` files are
   present in the artifact; they live in the full `gigahorse-toolchain` repository. The shipped
   files are only the *client* rules (`analyze.dl`, `run_analysis.sh`, `main.py`, `env.yaml`)
   plus intermediate outputs.
4. **Network fetch of the toolchain unverified.** Even cloning `gigahorse-toolchain` would then
   require the Soufflé build (blocker 1) and a working decompiler front-end; the end-to-end
   path cannot be certified within the budget.

## Estimated remaining work to reach Option A
- Install a container runtime, OR build Soufflé from source (~0.5–1 day incl. deps);
- clone `gigahorse-toolchain`, place client files, resolve `env.yaml` versions (~0.5 day);
- run the decompiler + Datalog on a bytecode subset and reconcile output schema (~0.5–1 day).
Total ≈ 1.5–2.5 working days with a container runtime available; higher risk without one.

## Limited agreement analysis (from shipped intermediate outputs; toolchain NOT executed)
Using `eoa_detect/detect_result.jsonl` (per-address rule firings shipped with the artifact):
`revision_v2/results/gigahorse/limited_agreement.json`.

- Shipped rule-fact addresses: 718 unique.
- Task-aligned malicious with ≥1 shipped fact row: **727/727 (100%)** — consistent with the
  positives being defined by this pipeline (labels ARE the rule output; this is the
  circularity already disclosed, not an independent agreement measurement).
- Task-aligned `benign_cleared` with shipped fact rows: **4/1553** — consistent with these
  being rule-silent weak negatives by construction.
- Dominant shipped finding type on malicious: `UnkownCall` (751 occurrences), i.e. the
  external-call structural signal; a long tail of generic selectors (transfer/approve/
  withdraw/…) accounts for the remainder.

## Interpretation and manuscript consequence
Because the pipeline was not executed, AuthGuard is **not** compared to the full analyzer, and
no speed or coverage claim relative to it is made. The shipped facts only re-confirm label
provenance (circularity), so they cannot serve as independent validation. The manuscript
already avoids a speedup claim (main.tex lines 61, 75); Phase 6C keeps that scoping and
positions AuthGuard and the reference analyzer as **complementary** methods with different
information (bytecode-only vs decompiled Datalog facts) and different analysis boundaries.
No completed experiment depends on this phase.
