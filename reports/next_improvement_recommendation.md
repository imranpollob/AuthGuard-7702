# PART C — Next-Improvement Recommendation

Decision grounded in the artifacts, not a default. The strongest *demonstrated* weakness is the
dead-code-flooding failure mode (M0 collapse; aug residual benign FPR 27.5% @+200%,
`advtrain_results.json`), which is exactly what makes contribution C3 "PARTIALLY RECOVERS." The
strongest *acceptance threat* is label circularity (O1) — but the only real fix (independent
dataset) already returned INSUFFICIENT DATA and is not submission-timely.

## Option scoring (value / difficulty / time / risk / external-data / weakness addressed / ICTAI effect)
| # | Option | Value | Diff | Time | Risk | Ext-data | Weakness | ICTAI effect |
|--|--|--|--|--|--|--|--|--|
| 1 | Reachability-aware features | **High** | Med | 2–3 d | Low | none | flooding FP/collapse (O3, C3) | **↑↑** |
| 2 | Reachability + adv-aug | High | Med | 3–4 d | Low | none | O3 fully | ↑↑ |
| 3 | Full USENIX pipeline run | Med-High | High | 5–10 d | Med (may weaken brittleness claim) | toolchain | O2 | ↑ |
| 4 | Independent auth-list dataset | **High** | High | 10+ d | High (low yield seen) | heavy | O1 circularity | ↑↑ but not timely |
| 5 | PU learning | Med | Med | 3–4 d | Med | none | weak negatives | ↑ |
| 6 | Selective prediction/escalation | Med | Low-Med | 2 d | Low | none | operating point | ↑ |
| 7 | Calibration + risk–coverage | Med | Low | 1–2 d | Low | none | FP framing | ↑ |
| 8 | Signer-context relational | Low | High | — | High | victim data (none) | — | ~ |
| 9 | Time-based eval | Med | Med | 3 d | Med | timestamps (absent) | external validity | ↑ |
| 10 | Cross-chain leave-one-chain-out | Med | Low | 1–2 d | Low | none (have chain) | external validity | ↑ |
| 11 | Execution-level mutation validation | Med | Med-High | 4 d | Med | EVM | "semantics" wording | ↑ (but wording fix is free) |
| 12 | Stronger rule baseline | Low-Med | Low | 1 d | Low | none | O2 partial | ~ |

## Top 5 ranked
1. **Reachability-aware feature extraction (#1)** — highest leverage on a demonstrated weakness, no external data, timely.
2. **Cross-chain leave-one-chain-out (#10)** — cheap new generalization axis reviewers value.
3. **Calibration + risk–coverage (#7)** — cheap; reframes the FP problem as selective screening.
4. **Independent auth-list dataset (#4)** — the real circularity fix, but high-effort/low-yield → future.
5. **Full USENIX pipeline (#3)** — closes O2 fully, but heavy and risks the brittleness claim → future.

## Verdicts
- **IMPLEMENT BEFORE SUBMISSION → #1 Reachability-aware feature extraction** (implicitly delivers
  #2 when re-run through the frozen adv-train pipeline).
- **IMPLEMENT ONLY IF TIME REMAINS → #10 cross-chain leave-one-chain-out; #7 calibration/risk–coverage.**
- **DEFER TO FUTURE WORK → #3, #4, #5, #6, #8, #9, #11, #12.** (#4 and #3 are the top journal-extension items.)

## Detailed plan — #1 Reachability-aware feature extraction
- **Research question:** Does excluding provably-unreachable/appended bytecode before
  featurization eliminate the dead-code-flooding failure mode without harming clean performance?
- **Hypothesis:** Since every flooding mutation appends code after a terminal `STOP`/metadata
  boundary (never inside the executable region — verified by preservation), a conservative
  "executable-region" mask (bytes reachable from the dispatch entry, stopping at the first
  top-level terminal + CBOR-metadata boundary) makes features invariant to flooding, driving
  +200% benign FPR toward the clean baseline and lifting AuthGuard-M0 recall at +200% toward its
  M0 value — *without* augmentation.
- **Implementation plan:** add a `reachable_region(bytecode)` pass to `ag_common` (linear sweep +
  jumpdest/terminal analysis, no full decompilation); featurize only that region; keep all other
  features/hyperparameters frozen. Produce `AuthGuard-M0-reach` and (re-run) `AuthGuard-aug-reach`.
- **Leakage controls:** reuse frozen family folds and all five adv-train leakage assertions
  unchanged; the reachability mask is a pure function of a single contract's bytecode (no
  cross-contract information), so it cannot leak.
- **Evaluation protocol:** the exact G-ADV pipeline (`adv_run.py`) with the new feature pass;
  report clean M0, M3, +200% for M0/aug × reach/no-reach; paired bootstrap vs the current models.
- **Baselines:** AuthGuard-M0, AuthGuard-aug (current), opcode-XGBoost-aug (does padding exposure
  still matter once reachability is enforced?).
- **Success criteria:** +200% benign FPR drops from 0.275 to ≤ clean (≈0.16) AND +200% recall
  ≥ M0-clean recall, with clean AUPRC not lower than 0.849 (paired CI).
- **Failure interpretation:** if reachability does *not* help, it means the learned model's
  padding sensitivity comes from features inside the executable region (e.g., normalized 4-gram
  dilution), which would redirect future work to normalization/robust-feature design and would be
  reported honestly as a negative result.
- **Required table:** extend Table 5 with `-reach` rows (clean/M3/+200%: AUPRC,P,R,FPR,
  singleton-recall).
- **Required figure:** overlay reach vs no-reach on `fig_advtrain_heldout.png` (recall + FPR).
- **Effect on the three contributions:** upgrades C3 from "PARTIALLY RECOVERS via augmentation"
  to "a domain-informed reachability feature that structurally removes the dead-code-flooding
  evasion" — a stronger, more AI-methodology-flavored contribution, and directly rebuts O3.
- **Estimated time:** 2–3 days (mask implementation + one adv-train re-run + tables/figure).
