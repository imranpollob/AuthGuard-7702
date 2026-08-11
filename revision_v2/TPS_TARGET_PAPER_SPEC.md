# Target end-state for the TPS 2026 submission

This is the paper we are aiming at, decided before any work starts. Written 2026-08-11.
It supersedes the triage list in `TPS_REVIEW_TRIAGE.md` as the statement of *intent*; that
file remains useful only as an inventory of reviewer objections.

---

## 1. The thesis

> **Pre-authorization screening of EIP-7702 delegates is an adversarial problem, and clean
> accuracy does not measure it.** Every strong clean model on this task — histogram XGBoost,
> a flat CNN, even a 15-feature interpretable rule emulator — is evaded by cheap,
> structurally valid, execution-preserving bytecode padding that any attacker can apply for
> gas cost alone. We identify the single design property that survives this adversary,
> isolate it with parameter-matched controls, quantify it under a query-budgeted adaptive
> attacker, and show the surviving screener holds on a temporally disjoint live delegate
> population at millisecond cost.

Everything below follows from that sentence. It is what makes this a *security* paper rather
than an ML-application paper, and TPS is a security venue.

### Why this thesis is strong rather than defensive

Three findings that read as weaknesses under the current draft's framing become the
paper's evidence under this one:

| Finding | Under current framing | Under this thesis |
|---|---|---|
| A 15-feature logreg matches AuthGuard-Seq on clean AUPRC (Δ=−0.021, CI spans zero) | Fatal — "why a neural net?" | **Premise.** Clean accuracy is cheap and uninformative on this task. Report it as our own control, then show it collapsing under attack. |
| A parameter-matched flat encoder is at least as good on clean (0.936 vs 0.918; hierarchy contrast CI spans zero) | Contradicts "ranks first of seven" | **Centerpiece.** The clean-best model is the attack-worst model: flat loses 0.098 AUPRC and 0.309 Recall@5%FPR under Flood-200%, both CIs excluding zero. |
| Labels come from the source analyzer's rule, not adjudicated ground truth | Near-fatal for a detection claim (O1, professor P1) | **Materially defused.** The headline is a *relative robustness comparison between architectures on a shared label*, not an absolute detection claim. Relative claims are far less sensitive to label validity: whatever the label means, the ranking under attack is valid. This is the strongest available answer to P1 without human labeling — and it is honest. |

That third row is the important one. It is the reason this reframe beats every other path we
have considered for handling label circularity, including the ones that failed.

---

## 2. Contributions we are claiming

Exactly three. Each is defensible today, each maps to a section, none requires new
architecture search.

### C1 — Problem formulation and a benchmark with a live temporal holdout
First formulation of pre-authorization delegate screening at the EIP-7702 authorization
boundary. **AuthGuardBench-7702**: 2,190 audited delegates in 790 bytecode-similarity
families with family-disjoint folds, an 797-contract external benign control, an 8-project
audited-implementation registry, and — new — a **temporally disjoint live holdout**: 752
screenable Ethereum delegates first observed 2026-07-23 → 2026-08-06, 669 unique runtime
bytecodes, **zero bytecode-hash overlap with any benchmark population**. Plus the leakage
protocol: exact-duplicate quarantine, MinHash family construction, partition-isolated
transformation donors, family-clustered paired bootstrap.

This is professor P6's point, and it is the contribution most likely to outlive the model.

### C2 — An adversarial evaluation methodology for bytecode security classifiers, and the design finding it yields
Prior bytecode-ML security work (PhishingHook, ContractWard, Eth2Vec, SmartBugBERT) reports
clean classification metrics and does not evaluate an adversary who controls the input
program. We contribute:
- a **query-budgeted adaptive attack** over a defined action space (metadata rewrite,
  address/selector rewrite, neutral insertion, flooding at 25/50/100/200%), with a bounded
  byte-overhead constraint, per-candidate structural-validity checking, and deterministic
  seeded search;
- a **bounded execution-preservation audit** that separates actions we can support as
  behavior-preserving from those we cannot (already measured: flooding preserves 100/100
  audited calls; address rewrite preserves only 23/100 — we report that honestly and scope
  the corresponding condition as representation-stress only);
- **cross-model and cross-seed transfer** of successful attacks.

The design finding: robustness is conferred by **length-invariant, evidence-selective
aggregation**, not by sequence coverage and not by hierarchy per se. Parameter-matched
controls separate the three mechanisms. This is the architecture contribution — a
robustness-motivated design *requirement*, isolated and validated — not a novel layer.
Professor P3 is satisfied and the claim is stronger than a novelty claim would have been.

### C3 — Operational evidence: staged triage on live authorization traffic
Full local screening path at **4.121 ms median** against a measured reference decompiler cost
of **2.687 s median** (p95 5.618 s; cold Datalog compile 264 s at 10.2 GiB peak; 60/60
inputs succeeded) — a **652× median ratio** motivating millisecond screening ahead of
selective deep analysis. Extended to the live population: alert rate per 1,000 real
authorization events, threshold transfer, and temporal stability.

---

## 3. The architecture we are targeting

**AuthGuard-Seq, re-specified as the ~30K-parameter chunk-attention model** from the
parameter-matched ablation — not the legacy 181,877-parameter variant.

Reasons: correct parameter accounting (the 181,877 figure counts two branches that are
constructed but never trained in the sequence-only configuration); clean mechanism
isolation against equal-budget controls; and a 6× smaller model is a *better* deployment
story, not a concession.

Each mechanism is presented as a defense against a named attack and backed by an ablation row:

| Mechanism | Attack it answers | Ablation control | Status |
|---|---|---|---|
| Full-stream coverage, no prefix truncation | Push the payload past a fixed input window | 2,048 vs 16,384 budget at equal params | Coverage alone: **inconclusive** (M0 +0.015, F200 +0.011; CIs span zero) — reported as such |
| Local dilated convolution over opcode order | Break histogram/n-gram statistics while preserving order | vs histogram + hashed-n-gram XGBoost | Supported |
| **Attention aggregation over chunks** | **Dilute the risk signal by appending arbitrary bytes** | vs mean-pooled chunks, equal params/budget | **Supported: M0 +0.0386 CI [+0.0072,+0.0643]; F200 +0.1800 CI [+0.1348,+0.2316]; F200 Recall +0.5412 CI [+0.4741,+0.6307]** |
| Chunked hierarchy vs flat encoding | — | Flat-16K vs chunk-attention-16K, equal params | Clean: **inconclusive** (−0.0181, CI spans zero). Under F200: **supported** (+0.0980 CI [+0.0590,+0.1544]) |

We state plainly that coverage and hierarchy are not supported on clean data. Reporting our
own inconclusive rows is what makes the supported rows credible.

**We are not searching for a new architecture.** Four independent searches have already
failed and are frozen (dual-view representation, selective escalation, risk-focused gated
aggregation, DCRG typed-guard semantics + relational GNN). That path is closed and will not
be reopened.

---

## 4. The evaluation we are targeting

Four research questions. RQ2 is the centerpiece and the main new work.

**RQ1 — What does clean family-disjoint screening actually require?**
Clean performance across model families, *plus* the parameter-matched mechanism ablation,
*plus* the 15-feature interpretable emulator and the kNN memorization control. Expected
conclusion, stated up front: clean accuracy on this task is achievable by cheap models and
does not by itself justify a learned sequence model. This sets up RQ2 instead of hiding from it.

**RQ2 — Which screeners survive an adversary who controls the bytecode?** ← centerpiece
Attack-success rate under the query-budgeted adaptive search, at matched byte-overhead
budgets, with structural validity enforced and execution preservation audited, evaluated
against: AuthGuard-Seq, Flat CNN, histogram+n-gram XGBoost, and the 15-feature emulator.
Plus cross-seed and cross-model transfer ASR. Reference point already measured against the
feature-based model: **ASR 59.3% at Flood-200% with ≤2× byte overhead and 100% structural
validity**, transferring at 66.5% to a different seed and 66.5% to a different model family.

**RQ3 — Does it generalize across time and across populations?**
The live temporal holdout (752 delegates, zero bytecode overlap, 2-week window), the 797
external benign controls, and the 8-project audited-implementation registry with the
three training-overlapping projects explicitly marked and excluded from headline numbers.
Threshold transfer reported honestly (nominal 5% → 6.5% observed; 10% → 16.9%).

**RQ4 — Is staged triage operationally justified?**
Latency distribution of the complete local path, the 652× decompiler ratio, and alert
volume on real authorization traffic.

---

## 5. What must be built, and the one real gamble

Ordered by risk, not by effort.

**G1 — Port the adaptive attack to neural targets. This is the gamble.**
The machinery is built, unit-tested, deterministic, donor-isolated, with leakage assertions
and an execution audit — but it currently targets the feature-based XGBoost model
(`revision_v2/experiments/adaptive_attacks/`, `TARGET = "authguard_seed7702"` over
`featurize`/`XGBClassifier`). Porting means giving the beam search a neural scoring
interface and rerunning. Half a day to a day.

**The risk is real and I will not pretend otherwise: we do not know AuthGuard-Seq's ASR
until we run it.** The fixed-transformation evidence is encouraging — under Flood-200% it
holds 0.920 AUPRC / 0.747 recall where XGBoost falls to 0.576 / 0.226 — but an adaptive
search that picks the best of 64 queries per contract is strictly stronger than a fixed
transform. Three outcomes:
- **ASR well below XGBoost's 59%** → the thesis lands exactly as written. Most likely.
- **ASR moderate (~25–40%)** → thesis holds directionally; soften "survives" to "degrades
  gracefully where others collapse," report the residual attack surface as a limitation.
  Still a strong security paper.
- **ASR comparable to XGBoost** → the design claim fails. Fallback: the paper becomes
  "no evaluated bytecode screener resists a query-budgeted adaptive adversary," which is a
  legitimate and publishable negative security result, but a distinctly weaker paper.
  We would then lead with C1 and C3.

**Decision rule: run G1 first, before writing anything.** It determines which paper we are
writing. Do not invest in prose until the number exists.

**G2 — Run the 15-feature emulator under the transformation and attack conditions.**
Cheap (hours), and it closes the "why not a simple model" question decisively in whichever
direction it goes. Must be done regardless of G1's outcome.

**G3 — Temporal holdout evaluation.** Score the 752 live delegates with the frozen
checkpoints under unchanged validation-derived thresholds; report flag rate, score
distribution, and alert rate weighted by real authorization frequency. Low risk, 3–4 h.
**Prerequisite:** recompute MinHash families across the union of both corpora and confirm no
live bytecode joins a training family — exact-hash disjointness is verified but is not
sufficient for a leakage claim. Optional stretch: re-run the source rule on the live corpus
for true labeled temporal metrics.

**G4 — Recovery and integration (low risk, mechanical).** The parameter-matched ablation
(`git checkout 699ab37 -- …long_context_ablation_v3`), the Gigahorse cost study
(`a79a7ea -- …reference_analyzer_cost_v1`), and the emulator/kNN controls
(`f86be6f -- …gate_0a_rule_emulator, …gate_0b_knn`). Verify
`python3 revision_v2/experiments/common/frozen.py verify` prints `OK: 144` before and after.

**G5 — Correct the parameter count and adopt the 30K model as the reference architecture
throughout.**

Not doing, and not revisiting: human ground-truth labeling; new architecture search;
ONNX/WASM deployment; cross-dataset transfer to Qi et al.; large-scale legitimate-delegate
scraping; full USENIX-pipeline accuracy comparison.

---

## 6. What a reviewer will say, and our answer

| Objection | Answer in the target paper |
|---|---|
| "Labels are the analyzer's rule, not ground truth." | Acknowledged in the abstract, not buried. The headline is a relative robustness comparison on a shared label, which does not depend on the label being ground truth. Task scoped as screening for a source-analyzer-identified structural condition throughout. |
| "Why a neural model when a 15-feature logreg matches it?" | We ran that experiment ourselves and report it. It matches on clean data and it does not survive the adversary. That is the paper's point. |
| "The architecture is not novel." | We do not claim it is. We claim a robustness design *requirement*, isolated with parameter-matched controls. Each mechanism is tied to an attack and an ablation row, including the two that came back inconclusive. |
| "Robustness to one fixed transform proves nothing." | Query-budgeted adaptive search with bounded overhead, enforced structural validity, audited execution preservation, and cross-model/cross-seed transfer. |
| "No temporal evaluation." | 752 live delegates over a 2-week window, zero bytecode overlap with any training population. |
| "External validation is n=5." | 797 external benign controls plus 8 named production implementations, with the 3 that overlap training families marked and excluded from headline numbers. |
| "Is it deployable?" | 4.121 ms median local path, ~30K parameters, 652× cheaper than the reference decompiler, with alert volume measured on real authorization traffic. |

---

## 7. Success condition

A paper whose central claim is *adversarial*, whose negative controls are reported as
evidence rather than omitted, and whose three contributions — benchmark, adversarial
evaluation methodology, operational deployment evidence — are each defensible without
depending on the label being ground truth or on the architecture being novel.

Go/no-go on the thesis is **G1**. Run it first.
