# Matched-Budget Robustness Report — Revision v3 Phase 1

Independent reimplementation of Flood-200% (`revision_v3/src/robustness/flooding.py`), scored
at **inference time only** (no retraining on flooded data in this Phase 1 pass) against the
already-trained, checkpointed clean models from `controlled_ablation` and
`reference_validation`, under the **same token budget the model was trained with** in every
case — directly answering the confound flagged by the prior repository audit
(`PROJECT_AUDIT_FOR_TPS.md` §7: "AuthGuard-Seq was scored on flooded inputs with no cap while
Flat CNN stayed capped at 2,048 tokens... the reported gap is potentially confounded by
input-budget mismatch, not purely architecture"). Full data:
`revision_v3/results/matched_robustness_summary.csv`,
`matched_robustness_predictions.csv.gz`, `matched_robustness_bootstrap.csv`,
`transformed_length_distribution.csv`.

## 1. Flooding implementation

- **Donor population**: `EXTERNAL_BENIGN_CONTROL` (benign_general, 795 usable rows after a
  ≥32-byte filter) — entirely outside the primary train/val/test population, so donor content
  cannot leak primary-fold information into any model's training set. (This Phase 1 pass only
  evaluates flooding at inference time; no model here is retrained on flooded data, so the
  train/test donor-role partitioning the canonical project uses for its own G-ADV augmentation
  experiments does not apply — noted as a scope difference, not an omission.)
- **Donor selection**: deterministic, seeded (`blake2b` keyed on `condition:sample_id:seed`),
  excludes any donor sharing the recipient's `family_id`, rotates through multiple donors with
  a random per-donor byte offset until the target length is reached. Verified deterministic and
  family-isolated by `revision_v3/tests/test_donor_isolation_and_no_v2_writes.py` (3 tests, all
  pass).
- **"200%" definition**: 200% of the recipient's own total runtime-bytecode byte length
  (a documented simplification of the canonical project's CBOR-metadata-aware executable-region
  split — using total length instead of metadata-excluded length very slightly overstates the
  donor budget for the minority of contracts with metadata trailers; not judged material for a
  Phase 1 comparative study since it is applied identically across all six matched models).
- **Construction**: `recipient_bytes + STOP(0x00) + donor_bytes[:target_len]`, truncated to
  the exact target length; donor bytes are drawn from the donor's own *executable* region.

## 2. Matched-budget results

| Model | Budget | Clean AUPRC | Flood-200% AUPRC | Absolute degradation | Clean Recall@5% | Flood-200% recall @ frozen clean threshold | Flood-200% observed FPR | % flooded sequences exceeding budget |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| flat_cnn_2048 | 2,048 | 0.879 ± 0.019 | 0.483 ± 0.012 | **0.396** | 0.696 | 0.136 | 0.033 | 81.9% |
| chunk_attention_2048 | 2,048 | 0.920 ± 0.009 | **0.877 ± 0.003** | **0.043** | 0.838 | 0.755 | 0.071 | 81.9% |
| flat_cnn_8192 | 8,192 | 0.948 ± 0.005 | 0.744 ± 0.022 | 0.204 | 0.860 | 0.363 | 0.027 | 20.9% |
| chunk_attention_8192 | 8,192 | 0.928 ± 0.010 | **0.834 ± 0.020** | **0.094** | 0.847 | 0.514 | 0.032 | 20.9% |
| flat_cnn_16384 | 16,384 | 0.951 ± 0.006 | 0.772 ± 0.043 | 0.179 | 0.855 | 0.380 | 0.034 | 5.8% |
| chunk_attention_16384 (= authguard_reference_v3) | 16,384 | 0.929 ± 0.015 | **0.835 ± 0.030** | **0.094** | 0.843 | 0.496 | 0.023 | 5.8% |

**At every one of the three matched budgets, the hierarchical chunk-attention model degrades
far less under flooding than the flat CNN of identical token budget** — roughly 9× less
degradation at 2,048 tokens, and roughly 2× less at 8,192 and 16,384 tokens.

## 3. Family-clustered paired bootstrap (chunk_attention − flat_cnn, Flood-200% AUPRC)

| Budget | ΔAUPRC [95% CI] | Excludes 0? |
|---:|---:|:---:|
| 2,048 | **+0.365 [+0.262, +0.465]** | **Yes** |
| 8,192 | **+0.062 [+0.010, +0.119]** | **Yes** |
| 16,384 | **+0.049 [+0.004, +0.096]** | **Yes** |

**All three intervals exclude zero.** This is the answer to the original audit question
("does the Flood-200% advantage remain when input budgets are matched?"):

## 4. Does the original 0.920 Flood-200% claim remain defensible?

**Yes, with a corrected mechanism.** The prior repository audit's concern was that
AuthGuard-Seq's F200 advantage over Flat CNN might be *entirely* explained by an unequal
input-budget mismatch (AuthGuard-Seq scored uncapped, Flat CNN capped at 2,048). This Phase 1
result shows that even when the two architectures are given the **identical** token budget —
at 2,048, 8,192, and 16,384 tokens — the hierarchical chunk-attention model still degrades
significantly less under flooding, with all three paired bootstrap intervals excluding zero.
**The budget mismatch was a real, previously undisclosed confound, but it is not the sole or
even the primary explanation for the robustness gap** — a genuine architectural
robustness property survives the correction. The magnitude of the raw v2 F200 AUPRC values
(0.920 for AuthGuard-Seq, 0.535 for Flat CNN, per `revision_v2/paper_handoff/FINAL_RESULTS_MANIFEST.md`)
should not be re-quoted directly from this Phase 1 grid (different implementation, different
hardware, different exact protocol details — see caveats below), but the **qualitative and
now quantitatively-confirmed claim** ("AuthGuard-style hierarchical processing is
substantially more robust to Flood-200% than a flat CNN") is supported by data that
specifically controls for the confound the original claim was criticized for.

## 5. Additional observations

- **Budget exceedance**: flooding pushes 81.9% of test contracts over a 2,048-token budget,
  20.9% over 8,192, and 5.8% over 16,384 — confirming the prior audit's finding that flooding
  materially changes the length distribution relative to clean data (max clean length 10,795
  tokens, well under 16,384; but Flood-200% roughly triples length, pushing many contracts
  well past even the largest budget tested).
- **flat_cnn's degradation shrinks as budget grows** (0.396 → 0.204 → 0.179), consistent with
  more of the flooded sequence's original signal surviving the uniform-stride downsampling as
  the budget increases relative to typical flooded length. **chunk_attention's degradation is
  nearly budget-invariant** (0.043 → 0.094 → 0.094) — interestingly, chunk_attention_2048 has
  the *smallest* absolute degradation of all six configurations despite operating at the
  smallest budget and the highest budget-exceedance rate (81.9%), suggesting its robustness
  advantage is not simply "more room to fit the flood" but something more specific to how the
  hierarchical chunk-attention model degrades gracefully under truncation/downsampling itself.
- Flood-200% observed FPR stays low across all six configurations (0.023–0.071), so the
  degradation is concentrated in reduced recall/ranking quality, not runaway false positives.
- The uncapped-diagnostic condition described in the audit brief (evaluating AuthGuard-Seq with
  no budget cap, purely as a diagnostic, never in the main comparison table) was **not run**
  in this Phase 1 pass — the matched-budget comparisons above already answer the confound
  question directly, and an uncapped run would only reproduce the original (confounded)
  v2-style comparison, which is already documented and critiqued in `PROJECT_AUDIT_FOR_TPS.md`.

## 7. Strongest exploratory candidate under matched-budget flooding

Per the audit brief, the strongest exploratory candidate (`authguard_sequence_dense`,
statistically tied with `authguard_reference_v3` on clean AUPRC — see
`MODEL_CANDIDATE_REPORT.md`) was retrained with checkpoint saving and evaluated the same way,
at its native 16,384-token budget:

| Model | Clean AUPRC | Flood-200% AUPRC | Absolute degradation |
|---|---:|---:|---:|
| chunk_attention_16384 (reference) | 0.929 | 0.835 | 0.094 |
| **authguard_sequence_dense** | 0.920 | **0.891** | **0.029** |

**Interesting, unconfirmed lead**: the structural/dense-augmented hybrid degrades noticeably
*less* under flooding than the plain sequence-only reference (0.029 vs. 0.094 absolute AUPRC
loss) despite being statistically tied on clean data — plausibly because dense structural
features (jump/call counts, densities, selector flags) are less disturbed by appended
dead-code than raw opcode-sequence content is. **This is reported as a single point estimate
from one retrain, with no paired family-clustered bootstrap CI computed against the reference
model under flooding** — it should be treated as a promising Phase 2 follow-up question
("does structural-feature augmentation improve flooding robustness specifically, even without
improving clean performance?"), not a confirmed result.

## 6. Threats and caveats

- This is an **inference-time-only** evaluation: no model was retrained on flooded data (no
  G-ADV-style augmentation), so this report speaks only to *clean-trained* model robustness
  under transformation stress, matching the audit brief's Phase 1 scope (retraining on new
  labels/transformations is explicitly out of scope).
- Donor selection here is simpler than the canonical project's fold/partition-role-isolated
  multi-donor pool (not needed at inference-only time, per §1), and the "200%" byte-length
  definition uses total bytecode length rather than a CBOR-metadata-aware executable-region
  split (§1) — both are documented, intentional Phase 1 simplifications, not silent
  deviations.
- Single flooding draw per (recipient, seed) — no repeated-donor-sampling variance estimate
  within a fixed model/fold/seed; the bootstrap CIs above capture family-clustered sampling
  variance across the test set, not donor-selection variance.
- Absolute numbers here (AUPRC, degradation) should not be directly compared to the frozen v2
  `robustness_operational_v2` numbers — different implementation, different training run,
  different hardware (this session's CUDA GPU vs. v2's original training environment). The
  comparative (chunk vs. flat, at matched budget) claim is the one this report supports; a
  cross-generation absolute-number comparison is not attempted.
