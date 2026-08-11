# Gate 0C — Reference analyzer cost

## Headline result

The pinned Gigahorse decompiler costs a **median 2.687 s per contract** (p95 5.618 s, max 28.07 s, 60/60 succeeded) against AuthGuard-Seq's measured 4.121 ms — a **652× median ratio** — which clears the >1 s bar and means the surrogate framing is viable *in isolation*; but Gate 0A independently shows a 2.6 ms hand-coded emulator matches the model, so the speedup accrues to the emulator, not to AuthGuard-Seq.

## Status

**PASS on its own terms, moot in combination.**

The decision rule says analyzer median >1 s ⇒ surrogate framing viable, speedup ratio becomes a headline number. 2.687 s clears that comfortably. But the framing requires a second premise: that the learned model is the cheapest adequate approximation of the analyzer. Gate 0A falsifies that premise. A 15-feature logistic regression is statistically indistinguishable from AuthGuard-Seq (Δ = −0.0211, CI [−0.0780, +0.0353]) and runs in 2.626 ms. The correct conclusion from Gates 0A and 0C read together is: **a fast surrogate for this rule is worth having, and it does not need to be a neural network.**

---

## Method and provenance

### Source recovery (housekeeping item, completed first)

The work order recorded that `revision_v2/experiments/reference_analyzer_cost_v1/` and `.../legitimate_registry_expansion_v1/` had only `__pycache__` surviving, and directed a `pycdc`/`decompyle3` recovery attempt.

**No decompilation was necessary or performed.** All six `.py` sources — and the complete result set — are present in git commit **`a79a7ea` ("revision 3", 2026-07-25)**, on branch `revision-3`, which is not an ancestor of the current `claude-revision-3` HEAD. The files were never deleted from history; they were simply absent from this branch. (`decompyle3`/`uncompyle6` would in any case have failed: the bytecode is CPython 3.12, which neither supports.)

Recovered with `git checkout a79a7ea -- <paths>`:

- 6 Python sources, 4 shell scripts, 4 markdown documents, the 60-input frozen sample, and `revision_v2/protocols/reference_analyzer_cost_v1.md`
- the full result set: `per_contract.csv`, `summary.json`, `REFERENCE_ANALYZER_COST_REPORT.md`, `VERIFICATION.json`, `ARTIFACT_MANIFEST.json`, and per-stage `results.json` / `run_meta.json` / `container_inspect.json` / `resource_stats.jsonl`

Bulk `work/` fact dumps and compiled Soufflé caches (≈295 MB total tree) were deliberately not restored; the scientific outputs were.

**Integrity verified.** SHA-256 of all three restored primary artifacts match `VERIFICATION.json` exactly:

| Artifact | SHA-256 (restored) | Matches VERIFICATION.json |
|---|---|---|
| `per_contract.csv` | `eef56afd7581033a…` | yes |
| `summary.json` | `4ce95472ac902957…` | yes |
| `REFERENCE_ANALYZER_COST_REPORT.md` | `72cbdb947bf18432…` | yes |

`VERIFICATION.json` status is `PASS` with `warm_records: 60`. The frozen-artifact guard reports `OK: 144 frozen files verified unchanged` before and after restoration.

Nothing was rewritten from scratch, so the measurement below is the original run's, not a reproduction.

### Does Gigahorse run locally?

**Yes.** The pinned image
`ghcr.io/nevillegrech/gigahorse-toolchain@sha256:f676ca8a…910743` (2.69 GB) pulls and runs on this host; the recovered `EXECUTION_LOG.md` documents four attempts converging on a passing smoke test, and all three stages (smoke, cold, warm) exited 0.

The image also carries the `clientlib/` that `USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl` needs: its `#include "../clientlib/…"` paths resolve correctly from `/opt/gigahorse/gigahorse-toolchain/clients/`, and `gigahorse.py` accepts `-C/--client`. So running the actual source rule is mechanically feasible. **It was not run** — the containerised invocation was declined during this session. See "What this does not show."

### Measurement configuration

- One job (`-j 1`), 120 s per-phase timeout, default decompilation / fallback / inlining / signature-resolution settings.
- **No downstream client rule attached** — this is decompilation cost only.
- Warm stage reuses Datalog binaries compiled during the cold stage (`--reuse_datalog_bin`).
- Sample: 60 inputs, one per family, deterministically selected (SHA-256 salted by `AUTHGUARD_REFERENCE_ANALYZER_COST_V1`), balanced 30/30 by label and stratified across three opcode-length bands × 5 folds.
- Host: AMD Ryzen 5 3600, 12 logical cores, Docker 29.6.2, Linux 7.0.0-28.

---

## Results

### Warm serial bulk — the primary observation

| Statistic | Internal analysis time |
|---|---|
| **Median** | **2.687 s** |
| Mean | 3.474 s |
| p90 | 5.166 s |
| p95 | 5.618 s |
| Max | 28.067 s |
| Status counts | **SUCCESS: 60 / 60** |
| Failures / timeouts | **0 / 0** |

Container wall time 210.59 s for 60 inputs (3.510 s per submitted input including one container start and batch overhead). Peak sampled container memory 262.9 MiB.

### By bytecode length

| Length stratum | n | Median | Mean | p95 | Max |
|---|---|---|---|---|---|
| ≤ 2048 opcodes | 20 | 1.902 s | 1.849 s | 2.285 s | 2.331 s |
| 2049–4096 | 20 | 2.687 s | 2.700 s | 3.150 s | 3.295 s |
| > 4096 | 20 | 4.525 s | 5.873 s | 9.795 s | 28.067 s |

Cost scales with program size, and the tail is entirely in the largest stratum. Every stratum's median exceeds 1 s.

### By label

| Label | n | Median | Mean | p95 | Max |
|---|---|---|---|---|---|
| 0 (source-unflagged) | 30 | 2.586 s | 3.016 s | 5.394 s | 8.833 s |
| 1 (source-flagged) | 30 | 2.713 s | 3.932 s | 7.110 s | 28.067 s |

### Cold start — not pooled with the above

| | Value |
|---|---|
| Container wall time | 264.23 s (1 contract, empty cache) |
| Internal analysis time | 2.841 s |
| Peak memory | 10,393.6 MiB |
| Compiled cache produced | 91.4 MB, 9 files |

The 264 s is first-use Soufflé Datalog compilation, amortised across every subsequent contract. It is reported separately and must not be presented as per-contract cost. Image pull adds a further 71.16 s once.

### Comparison against AuthGuard-Seq

| | Median | Source |
|---|---|---|
| Gigahorse decompilation | 2.687 s | this measurement, 60 contracts |
| AuthGuard-Seq full local screening | 4.121 ms | `robustness_operational_v2`, 1,500 calls |
| **Ratio** | **652×** | |
| Gate 0A hand-coded emulator | 2.626 ms | this session, 300-contract sample |
| **Ratio (emulator)** | **1,023×** | |

**Correction to the recovered report.** `REFERENCE_ANALYZER_COST_REPORT.md` states a 913× ratio using an AuthGuard-Seq median of 2.942 ms. That figure does not appear anywhere in the current results tree. The authoritative operational measurement — used in `FINAL_CLAIMS.md`, `FINAL_TABLES.md`, and `PAPER_REWRITE_HANDOFF.md` — is **4.121 ms** median over 1,500 calls, which gives **652×**, not 913×. If any cost claim reaches the manuscript it should use 652×, and the recovered report's paragraph needs correcting.

---

## What this does not show

- **This is decompilation cost, not the source rule's cost.** No client rule was attached. The measured figure is what Gigahorse costs to lift bytecode to TAC; running `analyze.dl` on top would add client time. Observed `client_time` with no client supplied is ~0.001 s, and Datalog clients of this size are cheap relative to decompilation, so the total is unlikely to move much — but that is an inference, not a measurement.
- **The sample is 60 contracts, not the ≥100 the work order specifies.** Extending to 120 (`prepare_sample.py --per-cell 4`) and attaching `analyze.dl` was the plan for this session; the containerised run was declined, so the gate rests on the recovered 60-contract measurement. The shortfall matters most for the tail statistics (p95, max), which rest on 20 rows in the largest stratum; the median is robust.
- **The source rule was never executed against the corpus.** This remains the highest-value unfinished item across all three gates. Running `analyze.dl` over the 2,190 benchmark bytecodes would (a) confirm end-to-end, rather than by audit inference, that the stored labels are exactly reproducible from the input, and (b) give the true cost of "just run the rule," which is the alternative the paper must argue against. Both are currently unmeasured.
- **No semantic-equivalence claim.** Gigahorse reconstructs far richer program semantics than either AuthGuard-Seq or the Gate 0A emulator emits. A 652× or 1,023× ratio compares a full decompiler against a triage score; the two are not interchangeable and the ratio is descriptive, not a statement that one replaces the other.
- **Single host, single job.** `-j 1` was used deliberately for clean per-contract attribution; a production deployment would parallelise, reducing effective per-contract cost by roughly the core count. The 652× ratio is against a deliberately serial configuration.
- **Timeout and error rows remain in the denominator.** There were none, but at a 120 s timeout a harder corpus would produce them, and the zero failure rate should not be generalised beyond these 60 family-distinct delegates.
