# TPS 2026 — Evidence ledger

Every number the target paper will cite, with its provenance and its verification status.
Written 2026-08-11 during the execution session. Sections marked **FINAL** are complete and
independently checked; sections marked **PENDING** are still accumulating seeds.

Frozen-artifact guard was green (`OK: 144 frozen files verified unchanged`) before and after
every run recorded here.

---

## 1. RQ2 centerpiece — adaptive robustness **FINAL** (3 seeds, 87,240 attack records)

New work. Code: `revision_v2/experiments/adaptive_attacks_v2/`
(`run_adaptive_attacks_v2.py`, `scorers.py`, `analyze_adaptive_v2.py`).
Results: `revision_v2/results/adaptive_attacks_v2/`.

Protocol: v2 primary corpus (2,190 rows / 790 families / 727 positives), family-disjoint
folds, validation-only temperature scaling and nominal 5% FPR operating point, query budget
64, beam width 4, max depth 4, byte-overhead cap 2.0x, structural validity enforced per
candidate, flooding donors partition-isolated from the external benign control and never
from the recipient's family. Each architecture is attacked as the target in turn.

### Headline (727 sources x 3 seeds x 5 folds)

| Target | Params | Clean detection @5% FPR | Best-attack ASR | 95% CI | fold→seed mean ± SD |
|---|---:|---:|---:|---|---|
| **AuthGuard-Seq** | 63,266 active | **0.843** | **0.181** | [0.130, 0.244] | 0.209 ± 0.013 |
| 15-feature emulator (logreg) | 15 features | 0.825 | 0.536 | [0.423, 0.644] | 0.540 ± 0.011 |
| Flat CNN | 154,177 | 0.722 | 0.945 | [0.914, 0.972] | 0.953 ± 0.005 |
| Hist.+4-gram XGBoost | — | 0.637 | 0.986 | [0.975, 0.995] | 0.990 ± 0.001 |

"Best-attack" = max over attack strategies = **random search** on every target. Beam search
is weaker everywhere (AuthGuard-Seq 0.146, emulator 0.452, Flat CNN 0.907, XGBoost 0.950):
the score-guided beam follows depth-1 score drops into a local optimum while seeded random
search explores more diverse action sequences on the same budget. **The paper must quote the
max over strategies**; quoting beam alone would understate the attack and flatter the defense.

### Paired family-clustered ASR contrasts vs AuthGuard-Seq (3 seeds)

| Contrast | Flood-200% (fixed) | Best fixed transform | Beam search | Random search |
|---|---|---|---|---|
| Flat CNN − AuthGuard-Seq | +0.649 [+0.539,+0.746] | +0.708 [+0.627,+0.782] | +0.782 [+0.716,+0.841] | +0.786 [+0.727,+0.838] |
| XGBoost − AuthGuard-Seq | +0.583 [+0.522,+0.641] | +0.743 [+0.670,+0.804] | +0.843 [+0.788,+0.886] | +0.844 [+0.786,+0.890] |
| Emulator − AuthGuard-Seq | **+0.082 [−0.047,+0.218]** | +0.221 [+0.067,+0.369] | +0.330 [+0.161,+0.488] | +0.360 [+0.188,+0.518] |

Eleven of twelve CIs exclude zero. **The exception is the load-bearing result** — see below.

### The methodological finding that justifies the whole apparatus

Under the *fixed* Flood-200% transform, the 15-feature emulator and AuthGuard-Seq are
**statistically indistinguishable** (+0.082, CI [−0.047, +0.218], spans zero). The neural
model's advantage over the cheap interpretable baseline emerges *only* under adaptive
search, growing monotonically with attack strength:

| Attack strength | Emulator − AuthGuard-Seq | Excludes zero? |
|---|---|---|
| Fixed Flood-200% | +0.082 [−0.047, +0.218] | **no** |
| Best fixed transform (7 conditions) | +0.221 [+0.067, +0.369] | yes |
| Beam search (64 queries) | +0.330 [+0.161, +0.488] | yes |
| Random search (64 queries) | +0.360 [+0.188, +0.518] | yes |

**A fixed-transformation robustness study — which is all prior bytecode-ML security work
does, and all the current draft does — cannot distinguish these two models. Only adaptive
evaluation can.** This is the strongest available argument for contribution C2: the
methodology is not decoration, it is the only instrument that resolves the question.

### Transfer asymmetry (beam search, 3 seeds)

| Attack built against | → AuthGuard-Seq | → Flat CNN | → XGBoost |
|---|---:|---:|---:|
| AuthGuard-Seq | — | 0.782 | 0.673 |
| Flat CNN | **0.088** | — | 0.596 |
| XGBoost | **0.084** | 0.652 | — |

Evasive directions found against the flat models do not work against chunk attention, while
the reverse transfers freely. Independent corroboration that the robustness is not a
threshold artifact. (Emulator↔neural cells need a combined-process run; not done — the
emulator arm ran standalone on CPU.)

### Interpretation

Clean detection is essentially tied between AuthGuard-Seq and a 15-feature logistic
regression (0.843 vs 0.825), consistent with Gate 0A finding them statistically
indistinguishable on AUPRC. Under a query-budgeted adversary the neural model is ~3x harder
to evade than the emulator and ~5x harder than the flat/histogram models. The emulator's
intermediate position matters twice over: it shows the advantage is about *aggregation*
rather than "neural beats hand-crafted features," and it supplies the fixed-vs-adaptive
contrast above.

---

## 2. Mechanism ablation **FINAL** (recovered, independently re-verified)

Recovered from commit `699ab37` to `revision_v2/{experiments,results,protocols}/long_context_ablation_v3`.
Summary reproduces **exactly** (4 dp) from the raw per-fold `metrics.csv` for all six models
in both conditions; 3 seeds x 5 folds = 15 rows per cell.

| Model | Budget | Params | Clean AUPRC | F200 AUPRC | F200 Recall@5% |
|---|---:|---:|---:|---:|---:|
| Flat control (2K) | 2,048 | 29,985 | 0.879 ± 0.005 | 0.532 ± 0.017 | 0.148 ± 0.013 |
| Flat control (16K) | 16,384 | 29,985 | **0.936 ± 0.003** | 0.810 ± 0.014 | 0.506 ± 0.038 |
| Chunk attention (2K) | 2,048 | 30,050 | 0.902 ± 0.003 | 0.897 ± 0.009 | 0.817 ± 0.022 |
| Chunk mean (16K) | 16,384 | 29,985 | 0.879 ± 0.005 | 0.728 ± 0.020 | 0.274 ± 0.031 |
| Chunk attention (16K) | 16,384 | 30,050 | 0.918 ± 0.007 | **0.908 ± 0.001** | **0.815 ± 0.039** |
| Legacy AuthGuard reference | 16,384 | 181,877 naive / 63,266 active | 0.914 ± 0.013 | 0.894 ± 0.006 | 0.786 ± 0.021 |

Parameter matching verified: 29,985 vs 30,050, a 65-parameter difference (attention vector,
64 weights + 1 bias). The legacy reference is ~2x the controls, so the controls are a
conservative comparison.

### Predeclared mechanism contrasts (2,000 replicates, family-clustered within fold)

| Mechanism | Condition | ΔAUPRC | 95% CI | Verdict |
|---|---|---:|---|---|
| coverage | clean | +0.0152 | [−0.0028, +0.0300] | INCONCLUSIVE |
| attention | clean | +0.0386 | [+0.0072, +0.0643] | **SUPPORTED** |
| hierarchy | clean | −0.0181 | [−0.0400, +0.0182] | INCONCLUSIVE |
| coverage | F200 | +0.0112 | [−0.0051, +0.0252] | INCONCLUSIVE |
| attention | F200 | **+0.1800** | [+0.1348, +0.2316] | **SUPPORTED** |
| hierarchy | F200 | +0.0980 | [+0.0590, +0.1544] | **SUPPORTED** |

F200 Recall@5% for attention: +0.5412 [+0.4741, +0.6307].

**Note for the paper:** these contrasts used **2,000** bootstrap replicates, not the 10,000
used for primary comparisons. State per-table; do not imply a uniform 10,000.

Cap-correctness audit: at the 16,384 budget, 5.7% of F200 inputs and **0%** of clean inputs
exceed capacity; at 2,048, 80.8% of F200 and 32.5% of *clean* inputs exceed. This is why
coverage reads inconclusive rather than null.

---

## 3. Parameter accounting **FINAL** (newly derived this session)

The draft reports **181,877 for three different models** (`tab:baseline-config`:
AuthGuard-Seq, Neural n-gram, Dense structural). `sum(p.numel())` cannot distinguish the
fusion configurations because each constructs all three view branches and trains only one.

Active-path counts, obtained by backward pass and checking which parameters receive gradient:

| Config | Naive sum (in draft) | **Active** | Dead |
|---|---:|---:|---:|
| AuthGuard-Seq | 181,877 | **63,266** | 118,611 |
| Neural n-gram | 181,877 | **108,225** | 73,652 |
| Dense structural | 181,877 | **75,595** | 106,282 |

Dead weight is `ngram_view` (65,536 + 8,192 + 1,024), `dense_view` (33,408 + 8,192),
`gate` (576), `auxiliary_head` (768). Matches `revision_v3`'s independent finding of 63,266.

The checkpoint-size sentence in RQ4 (742,625 bytes) also reflects the inflated model and
needs restating.

---

## 4. Temporal holdout **FINAL** (newly run this session)

Code: `revision_v2/experiments/temporal_holdout_v1/run_temporal_holdout.py`.
Results: `revision_v2/results/temporal_holdout_v1/`.

Population: `data/collected_delegates/v2_ethereum_population.csv` — 752 screenable Ethereum
delegates, blocks 25,595,134–25,695,421, first observed **2026-07-23 → 2026-08-06**, 669
unique runtime bytecodes. Scored with the 15 frozen cross-validation checkpoints from
`robustness_operational_v2/models/` under each checkpoint's own stored thresholds.
**No labels asserted** — these are operating-point transfer statistics, not detection metrics.

### Leakage gate (this is why the check was necessary)

Exact bytecode-hash overlap with the *entire* benchmark: **0**.
But **70/752 (9.3%)** reach the benchmark's 0.85 MinHash family threshold against primary
training bytecode, one at similarity **1.000** (identical opcode 4-gram profile, differing
only in PUSH immediates). Median similarity 0.266.

Hash-level disjointness is *not* sufficient to claim family-level novelty. The paper must
report the MinHash gate.

### Flag rates (mean ± SD over 3 seeds)

| Nominal | Observed (by contract) | Leakage-clean | **Authorization-weighted** |
|---|---:|---:|---:|
| 1% | 9.5% ± 2.1 | 8.8% | **5.9%** |
| 5% | 20.3% ± 3.6 | 19.9% | **9.4%** |
| 10% | 32.7% ± 1.9 | 33.3% | **14.6%** |

Results are robust to excluding the 70 leakage-suspect rows.

**Two readings, both required in the text.** Thresholds drift hard on live traffic: nominal
5% → 20.3% observed, far worse than the 6.5% the draft reports on the 797 curated benign
controls. But this population is real mixed traffic containing genuinely risky delegates, so
20.3% is a *flag rate*, not a false-positive rate, and cannot be decomposed without labels.
The authorization-weighted figures are roughly half the count-weighted ones because
high-volume delegates are popular wallet-infrastructure implementations that score low —
a deployment insight no prior EIP-7702 work reports.

---

## 5. Staged-triage cost **FINAL** (recovered, hashes re-verified)

Recovered from `a79a7ea` / `f86be6f`. Scientific outputs only; ~290 MB of Soufflé compile
caches and fact dumps deliberately not restored.

Pinned image `ghcr.io/nevillegrech/gigahorse-toolchain@sha256:f676ca8a…910743`,
60 deterministic family-distinct inputs, `-j 1`, no downstream client rule attached.

| Statistic | Value |
|---|---|
| Warm median | **2.687 s** |
| Warm p95 | 5.618 s |
| Warm max | 28.067 s |
| Warm serial wall | 210.59 s |
| Status | **60 / 60 SUCCESS** |
| Warm peak memory | 275.7 MB |
| Cold wall (incl. Datalog compile) | 264.23 s |
| Cold peak memory | 10.9 GB |

Against the 4.121 ms full local screening path: **652× median ratio**.

### Integrity

| Artifact | vs recorded SHA-256 |
|---|---|
| `per_contract.csv` | **OK** |
| `summary.json` | **OK** |
| `REFERENCE_ANALYZER_COST_REPORT.md` | **OK** |
| `ARTIFACT_MANIFEST.json` | stale — see below |

The manifest lists `VERIFICATION.json` among its files but not itself, and both commits carry
an identical manifest hash that never matched the recorded one. Circular generation order
(manifest → VERIFICATION.json → manifest regenerated). Benign, but the artifact statement
must say "three of four recorded hashes verify," not "all hashes verified."

### Mandatory scoping (do not omit)

Decompiler/lifter cost only; **no downstream client rule was executed**; not the exact
Huang et al. analyzer; not an accuracy, utility, or substitutability comparison; 60 inputs,
not the full corpus. Per Gate 0C's own conclusion, the speedup accrues to bytecode-level
screening in general — the 2.626 ms emulator is also an instance — so it is not
AuthGuard-Seq's unique advantage.

---

## 6. Cheap-baseline and memorization controls **FINAL** (recovered)

Recovered from `f86be6f`: `reports/gate_0a_rule_emulator.md`, `reports/gate_0b_knn_baseline.md`,
plus experiments and results.

- **Gate 0A**: L2 logreg over 15 hand-coded opcode features reaches **0.9106** AUPRC vs
  AuthGuard-Seq's 0.9244; paired family-clustered Δ = **−0.0211, 95% CI [−0.0780, +0.0353]**
  — spans zero. Emulator latency 2.626 ms vs 4.121 ms. A single boolean
  (over-approximate fallback→external-call CFG reachability) gets recall 0.996 @ precision
  0.760. Per-family: AuthGuard-Seq wins on 384/790 families — a coin flip.
- **Gate 0B**: kNN memorization control **passes** — 0.6121 AUPRC, Δ = **−0.30229**,
  95% CI [−0.3797, −0.2264], excludes zero. Free evidence that the family-disjoint split works.

All Gate 0A/0B figures above were re-verified against `gate_0a_results.json` /
`gate_0b_results.json` this session, not taken from the report prose.

**Replicate count:** both gates used **1,998** bootstrap replicates. With §2's 2,000 and the
primary comparisons' 10,000, the paper has three different replicate counts — state each
per-table rather than claiming a uniform protocol.

**A residual exposure a reviewer can push on.** Gate 0B's similarity strata show only
27/2,190 (1.2%) of test rows have a >0.9-similar training neighbour, and kNN scores exactly
at prevalence (0.185) on those — good. But **955 rows (43.6%) sit in the 0.7–0.9 similarity
band**, where kNN reaches 0.663–0.749 AUPRC. The 0.85 family threshold therefore leaves
substantial near-duplicate structure crossing folds. This is a defensible choice, not a
defect, but it should be stated, and `revision_v2/experiments/family_sensitivity/` already
holds 0.75/0.90 variants if a sensitivity row is wanted.

These are reported as our own controls and are the premise of the RQ2 argument, not a
concession.

---

## 7. Known corrections to carry into the draft

1. Parameter counts: 181,877 → 63,266 / 108,225 / 75,595 (§3). Checkpoint size too.
2. Quote **max over attack strategies** (random search), never beam alone (§1).
3. Ablation contrasts are 2,000 replicates, not 10,000 (§2).
4. Temporal novelty claim must be family-level (MinHash), not hash-level (§4).
5. Gigahorse artifact statement: three of four hashes verify (§5).
6. Clean-accuracy superiority over a parameter-matched flat encoder is **not** supported
   (hierarchy contrast CI spans zero); the supported clean claim is attention vs mean (§2).
