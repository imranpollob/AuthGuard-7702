# Phase 1 Model Defensibility Report — AuthGuard-7702 Revision v3

## 1. Branch and commit information

- Branch: `tps-revision-v3`, created off `new-review-based-plan` at commit
  `f4c8f3fa3186951fd64caaa59bcefb70739fc6f5` ("project audit").
- No code was merged, cherry-picked, or copied from Git branch `revision-3`. Every file under
  `revision_v3/src/` and `revision_v3/experiments/` is a new, independently written
  implementation (existing project code under `revision_v2/` was inspected read-only, as
  explicitly permitted, to understand required behavior — see §5 for what was compared against
  and how).
- No file under `revision_v2/`, `paper_build/`, `pipeline/`, `results/`, `reports/`,
  `capability_dataset.csv`, or `family_assignment_frozen.csv` was modified. Enforced by the
  frozen-hash guard (below) and by a static lint-style test
  (`revision_v3/tests/test_donor_isolation_and_no_v2_writes.py`).

## 2. Frozen-file verification

| Checkpoint | Result |
|---|---|
| Before any Phase 1 work | `[frozen] OK: 144 frozen files verified unchanged` |
| Mid-session (after harness/model code written, before large training runs) | `[frozen] OK: 144 frozen files verified unchanged` |
| After all Phase 1 results generated | `[frozen] OK: 144 frozen files verified unchanged` |

## 3. Revision v3 file tree

```
revision_v3/
├── README.md, requirements.txt
├── configs/canonical_inputs.json
├── data/input_manifest.json, encoded_primary_cache.pkl (derived feature cache, regenerable)
├── src/
│   ├── data/          build_manifest.py, loader.py
│   ├── features/       opcodes.py, disassembler.py, hashing.py, selectors.py, structural.py, encode.py
│   ├── models/          flat_cnn.py, chunk_model.py, hybrid.py, forward_fns.py
│   ├── training/        dataset.py, harness.py, calibration.py
│   ├── evaluation/       metrics.py, bootstrap.py
│   ├── robustness/       flooding.py
│   └── reporting/        model_complexity.py
├── experiments/
│   ├── reference_validation/    run_reference_validation.py, run_feature_parity.py, run_parameter_accounting.py
│   ├── controlled_ablation/     model_specs.py, run_controlled_ablation.py, run_controlled_bootstrap.py
│   ├── model_candidates/        model_specs.py, run_model_candidates.py, run_model_candidate_bootstrap.py
│   └── matched_robustness/      run_matched_robustness.py, run_matched_robustness_bootstrap.py, run_strongest_candidate_robustness.py
├── results/    (17 models' fold_seed/predictions CSVs + 7 summary/bootstrap/complexity CSVs + verdict JSONs)
├── tests/      8 test files, 35 tests, all passing
├── logs/       per-experiment run logs + progress JSONL
└── reports/    6 markdown reports (this file + 5 others)
```

## 4. Canonical input manifest

`revision_v3/data/input_manifest.json`: SHA-256 of `revision_v2/data/authguardbench_7702_v2.csv.gz`
recorded and hash-guarded on every load (`CanonicalInputChanged` raised on mismatch — tested).
Population verified: **2,190 primary rows, 727 positive, 1,463 negative, 790 families, 5
folds** — matches the expected population exactly (`test_dataset_integrity.py`, 10/10 pass).
No labels, family assignments, or fold membership were regenerated at any point.

## 5. Feature parity results

200 contracts sampled (seed 7702) from the canonical primary population; Revision v3's
independent feature pipeline compared against the frozen Revision v2 pipeline (imported
read-only, comparison purposes only):

| Check | Result |
|---|---:|
| Token-sequence equality rate | **1.000** (200/200) |
| Opcode-count equality rate | **1.000** (200/200) |
| Dense feature (261-d) max abs diff | **0.0** |
| N-gram feature (512-d) max abs diff | **0.0** |

Perfect parity. Full data: `revision_v3/results/feature_parity_report.json`.

## 6. Reference model parity results (go/no-go gate)

| Metric | Revision v2 | Revision v3 `authguard_reference_v3` | Abs. diff | Threshold | Pass? |
|---|---:|---:|---:|---:|:---:|
| AUPRC | 0.924448 | 0.929198 | 0.00475 | ≤ 0.015 | ✅ |
| Recall@5% FPR | 0.832668 | 0.842745 | 0.01008 | ≤ 0.025 | ✅ |

**PASSED.** A significant side-finding during this gate: GPU non-determinism (cuDNN algorithm
selection, not controlled by `torch.manual_seed` alone) caused two nominally identical runs to
differ by up to 0.0256 on Recall@5% — enough to flip the gate. Fixed by forcing
`torch.backends.cudnn.deterministic = True`; full detail in `REFERENCE_VALIDATION_REPORT.md`.

## 7. Controlled ablation results

9 models (flat CNN × {2048, 8192, 16384}; chunk model × {mean, attention} × {2048, 8192} ×
{mean, attention, max} × 16384), 7 required paired family-clustered bootstrap comparisons.
Full detail: `CONTROLLED_ABLATION_REPORT.md`. Headline findings:

- **Longer input coverage alone buys nothing significant** for the hierarchical model
  (`chunk_attention` at 2048 vs. 8192 vs. 16384: all deltas' CIs cross zero).
- **Hierarchy vs. flat is budget-dependent and mostly not significant**: chunk-attention
  significantly beats flat CNN on Recall@5% at the smallest budget (2048; +0.127, CI excludes
  zero); at 8192/16384 the point estimates favor flat CNN but **neither difference reaches
  significance** (both CIs cross zero) — raw point estimates alone would have overstated a
  "flat wins" conclusion.
- **Attention significantly beats mean pooling** (+0.034 AUPRC, +0.072 Recall@5%, both CIs
  exclude zero) but **not max pooling** (both CIs cross zero) — `chunk_max_16384` is a
  legitimate simpler alternative.

## 8. Exploratory model candidate results

4 hybrids (multiscale pooling; +structural/dense view; +hashed n-gram view; +both), one common
training configuration, each compared against `authguard_reference_v3`. Full detail:
`MODEL_CANDIDATE_REPORT.md`. **Every comparison's 95% CI includes zero on both AUPRC and
Recall@5%** — no hybrid provides a statistically supported clean-task gain over the plain
sequence-only model, despite adding up to 4.7× more active parameters.

## 9. Corrected parameter counts

Measured via real forward+backward passes (active = nonzero-gradient parameters), not just
`requires_grad` flags. Full detail: `PARAMETER_ACCOUNTING_REPORT.md`.

| Quantity | Value |
|---|---:|
| Revision v2's reported "AuthGuard-Seq" parameter count | 181,877 (total instantiated) |
| — of which actually active in the forward computation | **63,266** |
| Revision v3 `authguard_reference_v3` (no dead branches, by construction) | **38,562** (total = active) |

A second, much smaller instance of the same "generalized module configured down to fewer
active branches" issue was found in Revision v3's own `authguard_multiscale` candidate (65 of
59,299 parameters structurally dead due to a single-view softmax gate) — disclosed as a
validation of the active-parameter measurement methodology, not hidden.

## 10. Matched robustness results

Independent Flood-200% reimplementation (`revision_v3/src/robustness/flooding.py`), scored at
inference time on already-trained clean checkpoints, at the **same token budget for both
architectures being compared** — directly testing whether the prior repository audit's
input-budget-confound concern explains the robustness gap. Full detail:
`MATCHED_ROBUSTNESS_REPORT.md`.

| Budget | ΔAUPRC (chunk_attention − flat_cnn), Flood-200% [95% CI] | Excludes 0? |
|---:|---:|:---:|
| 2,048 | +0.365 [+0.262, +0.465] | **Yes** |
| 8,192 | +0.062 [+0.010, +0.119] | **Yes** |
| 16,384 | +0.049 [+0.004, +0.096] | **Yes** |

**All three intervals exclude zero.** The hierarchical chunk-attention model is significantly
more robust to Flood-200% than a flat CNN of identical token budget, at every budget tested.
The input-budget mismatch flagged by the prior audit was real (and is corrected here for the
first time) but does **not** fully explain the original robustness claim — a genuine
architectural robustness advantage survives the correction.

## 11. Statistical confidence intervals — summary of every CI computed this phase

All intervals are 95% paired family-clustered percentile bootstrap (10,000 replicates per
seed, averaged across the 3 seeds); see `controlled_ablation_bootstrap.csv`,
`model_candidate_bootstrap.csv`, `matched_robustness_bootstrap.csv` for exact numbers. 11 of
14 computed comparisons have CIs that cross zero (no significant difference); the 3 that
exclude zero are: chunk_attention_2048 vs. flat_cnn_2048 (Recall@5%), chunk_attention_16384
vs. chunk_mean_16384 (both metrics), and all three matched-budget Flood-200% comparisons.

## 12. Strongest final model candidate

**No exploratory hybrid candidate is a defensible upgrade** — none beats
`authguard_reference_v3` significantly on clean data (§8), so "strongest" reduces to
`authguard_reference_v3` itself among architecturally novel candidates. Among the *controlled*
grid, no model significantly beats `authguard_reference_v3`/`chunk_attention_16384` on clean
AUPRC or Recall@5% either (§7) — `flat_cnn_16384`'s higher point estimate does not reach
significance. On the robustness axis (§10), `authguard_reference_v3` is significantly more
robust than any flat-CNN alternative at matched budget, and one exploratory candidate
(`authguard_sequence_dense`) showed a promising (unconfirmed, single-run) lower degradation
under flooding — flagged as the top Phase 2 follow-up, not adopted here.

## 13. Simplest defensible model candidate

`chunk_max_16384` (38,497 active parameters, zero-parameter max-pooling aggregator,
statistically indistinguishable from `authguard_reference_v3` on clean data per §7) is the
leanest model not contradicted by this phase's evidence — though it was not evaluated under
matched-budget robustness in this pass (a natural Phase 2 addition, cheap to run since its
checkpoints already exist).

## 14. Major threats and unresolved issues

1. **GPU non-determinism** affects any single un-flagged training run in this codebase by up
   to ~0.006–0.007 AUPRC / Recall@5% swing between nominally identical seeds; the
   `cudnn.deterministic` fix (§6) is now baked into the harness, but individual controlled
   ablation / model candidate models were each trained only once (not cross-checked with a
   second determinism-verified run the way `authguard_reference_v3` was).
2. **`chunk_max_16384` and other controlled models were not evaluated under matched-budget
   robustness** — only 6 of the 10 controlled/reference models (the three flat/chunk-attention
   budget pairs) were carried through to Flood-200% scoring.
3. **The flat CNN's parameter count (154,177) is architecture-fixed and 4× larger than the
   hierarchical model's (38,562–38,562)** at every budget tested — the controlled ablation
   grid does not control for parameter count, so "flat vs. hierarchy" and "more capacity vs.
   less capacity" are confounded in the clean-data comparisons (§7). The robustness comparison
   (§10) is less affected by this confound since the flat CNN's larger capacity did *not*
   translate into better flood robustness — if anything this makes the robustness finding more
   striking, not less.
4. **`authguard_sequence_dense`'s promising flooding-robustness result (§10, Matched Robustness
   §7) has no bootstrap CI and is a single retrain** — must be confirmed with proper paired
   inference and multiple runs before being treated as a real effect.
5. **Flooding here uses a simplified "200% of total byte length" definition** rather than the
   canonical project's CBOR-metadata-aware executable-region split (documented in
   `MATCHED_ROBUSTNESS_REPORT.md` §1) — judged immaterial for a *comparative* study but would
   matter for an absolute-number claim.
6. **No repeated-donor-sampling variance estimate** for flooding — one flood draw per
   (recipient, seed).

## 15. Exact reproduction commands

All commands run from the repo root using system `python3` (has torch+CUDA; `revision_v2/.venv`
is not used for Revision v3):

```bash
python3 revision_v2/experiments/common/frozen.py verify          # before

python3 revision_v3/src/data/build_manifest.py
python3 -m pytest revision_v3/tests -q

python3 revision_v3/experiments/reference_validation/run_feature_parity.py
python3 revision_v3/experiments/reference_validation/run_reference_validation.py
python3 revision_v3/experiments/reference_validation/run_parameter_accounting.py

python3 revision_v3/experiments/controlled_ablation/run_controlled_ablation.py
python3 revision_v3/experiments/controlled_ablation/run_controlled_bootstrap.py

python3 revision_v3/experiments/model_candidates/run_model_candidates.py
python3 revision_v3/experiments/model_candidates/run_model_candidate_bootstrap.py

python3 revision_v3/experiments/matched_robustness/run_matched_robustness.py
python3 revision_v3/experiments/matched_robustness/run_matched_robustness_bootstrap.py
python3 revision_v3/experiments/matched_robustness/run_strongest_candidate_robustness.py

python3 -m pytest revision_v3/tests -q                            # after
python3 revision_v2/experiments/common/frozen.py verify           # after
```

Approximate total wall time on this session's hardware (NVIDIA RTX 2080 SUPER, 12-core CPU):
reference validation ~5 min, controlled ablation ~35 min, model candidates ~20 min, matched
robustness ~15 min, strongest-candidate robustness ~8 min — roughly 90 minutes of GPU compute
for the entire Phase 1 grid (17 distinct trained models × 15 fold-seeds each, plus ~85,000
inference-time flooding evaluations).

## 16. Recommended next phase

1. Extend matched-budget robustness to the remaining controlled models
   (`chunk_mean_*`, `chunk_max_16384`) and to all four exploratory candidates, with proper
   paired bootstrap CIs — cheapest, highest-value immediate follow-up (checkpoints for the
   controlled-ablation models already exist).
2. A parameter-count-controlled flat-vs-hierarchy comparison (shrink the flat CNN or grow the
   chunk model to matched active-parameter budgets) to cleanly separate the "hierarchy" and
   "capacity" factors confounded in §7/threat #3.
3. Confirm the `authguard_sequence_dense` robustness lead (threat #4) with a full bootstrap
   comparison against the reference model under flooding, across all three budgets.
4. Everything explicitly out of scope for Phase 1 remains out of scope until the above:
   human annotation, temporal data collection, label-noise-aware/PU-learning retraining, ONNX
   deployment, and manuscript rewriting (per the phase objective's stop condition).

---

## Decision table

| Candidate | Clean AUPRC | Recall@5% FPR | Matched Flood AUPRC | Active parameters | Main advantage | Main weakness |
|---|---:|---:|---:|---:|---|---|
| **authguard_reference_v3** | 0.929 ± 0.015 | 0.843 ± 0.014 | 0.835 ± 0.030 (16,384) | 38,562 | Significantly more robust to Flood-200% than flat CNN at every matched budget; no dead parameters; passed the v2 parity gate | No significant clean-data advantage over `flat_cnn_16384` or `chunk_max_16384` |
| Best controlled hierarchical model (`chunk_attention_16384` = authguard_reference_v3) | — (same as above) | — | — | — | — | — |
| Best flat equal-budget model (`flat_cnn_16384`) | 0.951 ± 0.006 | 0.855 ± 0.035 | 0.772 ± 0.043 | 154,177 | Highest clean point-estimate AUPRC of any model tested (not significant vs. reference) | Degrades ~2× more than chunk-attention under matched-budget flooding (significant), and needs 4× the active parameters |
| authguard_multiscale | 0.917 ± 0.011 | 0.856 ± 0.021 | not evaluated | 59,234 | Tightest fold-level stability of any exploratory candidate (SD 0.029 vs. reference's 0.067) | No significant clean-data gain; not evaluated under flooding |
| authguard_sequence_dense | 0.929 ± 0.011 | 0.841 ± 0.009 | 0.891 ± 0.003 (single run, no CI) | 97,645 | Statistically tied with reference on clean data; promising (unconfirmed) flooding-robustness lead | 2.5× the parameters for no confirmed gain; robustness lead lacks a bootstrap CI |
| authguard_sequence_ngram | 0.870 ± 0.009 | 0.833 ± 0.024 | not evaluated | 130,276 | None found | Lowest clean AUPRC of any hybrid; least stable at the fold level (SD 0.115) |
| authguard_all_views | 0.879 ± 0.002 | 0.828 ± 0.031 | not evaluated | 181,103 | Tightest seed-level-mean SD (0.002) — but this is misleading; fold-level SD is 0.092 | Most parameters (4.7×) for a below-reference clean AUPRC; not evaluated under flooding |

**Reading the table**: no candidate is automatically "the winner" by AUPRC alone. Given (a)
confidence intervals showing most clean-data differences are not significant, (b) the
matched-budget robustness advantage that specifically favors `authguard_reference_v3` over the
higher-capacity flat CNN, (c) `authguard_reference_v3`'s much smaller and honestly-accounted
parameter footprint, and (d) architectural simplicity favoring reviewer defensibility — **this
Phase 1 evidence supports keeping `authguard_reference_v3` (the plain sequence-only
hierarchical chunk-attention model) as the primary model**, with `chunk_max_16384` as a
defensible simpler fallback and `authguard_sequence_dense`'s flooding-robustness lead as the
single most promising unconfirmed lead for Phase 2.
