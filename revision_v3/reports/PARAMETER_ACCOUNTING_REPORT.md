# Parameter Accounting Report — Revision v3 Phase 1

Measured via `revision_v3/experiments/reference_validation/run_parameter_accounting.py`, which
imports the frozen Revision v2 `AuthGuardFusion` (read-only, for comparison) plus every
Revision v3 model, and reports for each: **total instantiated** parameters (every parameter
the module owns), **trainable** parameters (`requires_grad=True` — identical to total for
every model here), and **active forward** parameters (parameters that actually receive a
nonzero gradient from one real forward+backward pass on a dummy batch — measured, not
inferred). Checkpoint/state sizes are measured by serializing the actual model.

## 1. Headline correction

The Revision v2 paper reports **181,877 trainable parameters** for "AuthGuard-Seq"
(`revision_v2/experiments/baseline_v2/baseline_model_complexity.csv`). That number is the
total instantiated size of the shared `AuthGuardFusion` module with `active_views=(True,
False, False)` — it **includes the n-gram and dense view branches, which are never on the
active computation path** for this configuration.

| Quantity | Value | Source |
|---|---:|---|
| v2 AuthGuardFusion, all views active | 181,877 total / 181,877 trainable / **181,103 active** | `v2_authguardfusion_all_views_active` |
| v2 "AuthGuard-Seq" as reported in the paper (`active_views=(True,False,False)`) | 181,877 total / 181,877 trainable / **63,266 active** | `v2_authguard_seq_as_reported_181877` |
| **Revision v3 standalone reference model** (`authguard_reference_v3`, no dead branches by construction) | **38,562 total / 38,562 trainable / 38,562 active** | `authguard_reference_v3_standalone` |

**The honest standalone-sequence-model parameter count is 38,562, not 181,877.** The
181,877 figure measures a *different, larger object* (the shared multi-view module with two
branches switched off at the data level but still fully instantiated and weight-carrying);
63,266 of those 181,877 are architecturally reachable from the loss (they are on the path
`sequence_view -> gate -> fusion -> risk_head`, which processes the zero-padded ngram/dense
slots too) but the module as a whole is 4.7× larger than the standalone model needs to be.
Revision v3's `authguard_reference_v3` (`revision_v3/src/models/chunk_model.py`) never
instantiates the unused branches in the first place, so 38,562 is both its total and active
count — this is the number that should be quoted as "the sequence-only AuthGuard model's
parameter count" going forward.

## 2. Full table

See `revision_v3/results/model_complexity.csv` for the complete data (median forward latency
included per model on this session's CUDA GPU — NVIDIA GeForce RTX 2080 SUPER — not
comparable to the CPU-only latency numbers reported for the frozen v2 operational benchmark,
which used an AMD Ryzen 5 3600 single CPU thread; no cross-hardware latency claim is made
here).

| Model | Total | Active | Checkpoint bytes |
|---|---:|---:|---:|
| v2 AuthGuardFusion (all views active) | 181,877 | 181,103 | 737,868 |
| v2 "AuthGuard-Seq" as reported (dead branches included) | 181,877 | 63,266 | 737,868 |
| **authguard_reference_v3** (standalone) | **38,562** | **38,562** | **159,356** |
| flat_cnn_2048 / 8192 / 16384 | 154,177 (identical across budgets, by design — same architecture) | 154,177 | 619,985 |
| chunk_mean_2048 / 8192 / 16384 | 38,497 | 38,497 | 158,402 |
| chunk_attention_2048 / 8192 / 16384 | 38,562 | 38,562 | 159,356 |
| chunk_max_16384 | 38,497 | 38,497 | 158,402 |
| authguard_multiscale | 59,299 | 59,234 | 243,824 |
| authguard_sequence_dense | 97,646 | 97,645 | 398,436 |
| authguard_sequence_ngram | 130,276 | 130,276 | 528,868 |
| authguard_all_views | 181,103 | 181,103 | 734,226 |

## 3. A second, smaller instance of the same phenomenon — found in Revision v3's own code

`authguard_multiscale` shows 59,299 total vs. **59,234 active** (a 65-parameter gap). Root
cause, verified by inspection of `revision_v3/src/models/hybrid.py`: `HybridModel`'s gate
layer is `nn.Linear(view_dim * n_views, n_views)`. For `authguard_multiscale`, only the
sequence view is active (`n_views=1`), so the gate is `Linear(64, 1)` (65 parameters,
64 weights + 1 bias) followed by `softmax(dim=1)` over a **single-element** vector — softmax
of one logit is always exactly 1.0 regardless of the logit's value, so its gradient with
respect to that logit is structurally zero. The gate's 65 parameters are instantiated but
architecturally inert whenever only one view is active. This is the same *class* of issue as
the v2 finding above (an honest byproduct of writing a generalized N-view fusion module and
then configuring it down to one view) — caught here because this report measures active
gradient flow directly rather than trusting `total_instantiated_params`. It is disclosed
rather than silently patched, since patching it would change `authguard_multiscale`'s
architecture after results were produced; a future revision should special-case `n_views==1`
to skip the gate entirely.

`authguard_sequence_dense` shows a 1-parameter total-vs-active gap (97,646 vs. 97,645) — at
this magnitude (1 parameter out of ~97.6k) this is very plausibly float32 gradient underflow
on a single dummy random batch rather than a structural dead weight, and is not investigated
further; it is not material to any reported conclusion.

## 4. Active-parameter budget summary for the final decision table

| Model family | Active parameters |
|---|---:|
| Reference / all controlled single-view chunk & flat-CNN models | 38,497 – 154,177 |
| Exploratory two/three-view hybrids | 59,234 – 181,103 |
| v2 AuthGuard-Seq as previously reported (misleading) | 181,877 (only 63,266 truly active) |

`PHASE1_MODEL_DEFENSIBILITY_REPORT.md`'s decision table uses **active forward parameters**,
not `total_instantiated_params`, for every Revision v3 candidate.
