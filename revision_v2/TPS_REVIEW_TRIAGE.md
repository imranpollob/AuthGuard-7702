# TPS 2026 — Review Triage and Fix Plan

Date: 2026-08-11. Deadline: 2026-08-15 (4 days). Base manuscript:
`revision_v2/paper_final/AuthGuard_7702_revision_v2.tex` (8 pages, limit 10).

Review sources triaged here:
- **AIR-1…11** — the 11-item AI review, recorded in
  `revision_v2/paper_final/AI_REVIEW_VERIFICATION_AND_ROADMAP.md` (recover with
  `git show a79a7ea:revision_v2/paper_final/AI_REVIEW_VERIFICATION_AND_ROADMAP.md`).
- **M1…M6 / m1…m8** — senior-reviewer critique, `TPS_SUBMISSION_HANDOFF.md` §4.
- **P1…P6** — `revision_v2/professor_feedback.md`.
- **O1…O3** — hostile-reviewer assessment, `reports/ictai_reviewer_assessment.md`.

---

## 0. Read this first — the finding that reorders everything

Two experiments were run *after* the current draft was frozen, on branches never merged into
`main`. Both contradict the draft's headline claim. Neither has been seen by any reviewer yet,
and both are already computed, verified, and hash-checked.

**(a) Gate 0A — a 15-feature logistic regression matches AuthGuard-Seq.**
`git show f86be6f:reports/gate_0a_rule_emulator.md`

| Model | AUPRC | Recall@5%FPR | Latency |
|---|---|---|---|
| AuthGuard-Seq (181,877 params) | 0.9244 ± 0.0140 | 0.833 | 4.121 ms |
| L2 logreg, 15 hand-coded opcode features | 0.9106 ± 0.0000 | 0.773 | **2.626 ms** |

Paired family-clustered bootstrap: **Δ = −0.0211, 95% CI [−0.0780, +0.0353] — spans zero.**
A *single boolean* (over-approximate fallback→external-call CFG reachability) gets recall
0.996 at precision 0.760. Per-family error profile: AuthGuard-Seq wins on 384/790 families —
a coin flip.

**(b) Long-context ablation v3 — parameter-matched controls, cap-corrected.**
`git show 699ab37:revision_v2/results/long_context_ablation_v3/PAPER_RESULT_PACKET.md`

| Model | Params | Clean AUPRC | F200 AUPRC | F200 Recall@5% |
|---|---:|---:|---:|---:|
| Flat control (16K) | 29,985 | **0.936** | 0.810 | 0.506 |
| Chunk attention (16K) | 30,050 | 0.918 | **0.908** | **0.815** |
| Chunk mean (16K) | 29,985 | 0.879 | 0.728 | 0.274 |
| Legacy AuthGuard-Seq (16K) | 181,877 | 0.914 | 0.894 | 0.786 |

Predeclared mechanism contrasts: **attention SUPPORTED** (M0 +0.0386 CI [+0.0072,+0.0643];
F200 +0.1800 CI [+0.1348,+0.2316]); **hierarchy INCONCLUSIVE on clean** (−0.0181, spans zero)
but **SUPPORTED under F200** (+0.0980); **coverage INCONCLUSIVE** both conditions.

**Consequence.** The draft's abstract/contributions rest on "ranks first among seven models"
at 0.924 AUPRC. Under parameter-matched controls a flat 30K encoder *beats* it on clean
AUPRC, and under a cheap interpretable emulator the advantage is not statistically
distinguishable. This is the paper's real acceptance risk — not because a reviewer will
reproduce it, but because it is true, it is in your own repo, and P3 already told you to
downplay the architecture.

**The surviving, defensible model claim is narrower and still good:** *learned chunk
attention buys robustness, not clean accuracy.* Under Flood-200% it beats a
parameter-matched flat encoder by +0.18 AUPRC and +0.54 Recall@5%FPR, both CIs excluding
zero. That is a real, statistically supported, adversarially-motivated result — and it is a
*security* result, which is what TPS wants.

### Recommended reframe (this is the strategic decision to make today)

Demote the model to one of three contributions; promote the two non-AI ones. This satisfies
P3 and P6 directly, uses only already-computed results, and gives TPS a blockchain-security
systems contribution rather than an ML-novelty one it does not require.

1. **AuthGuardBench-7702** — the audited, family-disjoint benchmark and the leakage-control
   protocol (duplicate quarantine, MinHash families, donor isolation, family-clustered
   bootstrap). P6's point; the longest-lived artifact.
2. **The staged-triage cost boundary** — measured: reference decompiler median **2.687 s**
   (p95 5.618 s, cold Datalog compile 264 s / 10.2 GiB peak) vs **4.121 ms** full local
   screening — a **652× median ratio** on 60/60 successful family-distinct inputs. This is
   the non-AI novelty you asked about, and it is already verified with matching SHA-256s.
3. **The bounded model claim** — attention→robustness under flooding, plus the honest
   negative controls (cheap emulator parity, flat-16K clean parity) reported *as results*.

Reporting your own negative controls is the single strongest anti-reject move available:
it converts the paper's biggest vulnerability into evidence of rigor, and it is exactly what
security-venue reviewers reward.

---

## 1. SOLVABLE — do these

Ordered by (value × certainty) ÷ effort. Total ≈ 3 working days if S5-T2 is attempted,
≈ 1.5 days if not.

### S1 — Fix the parameter count (M2) · 30 min · certainty: total
181,877 is wrong. AuthGuard-Seq is the `sequence_only` config of `FusionModel`
(`active_views=(True, False, False)`) in
`revision_v2/experiments/authguard_fusion/run_authguard_fusion.py`; the ngram and
dense-structural branches are constructed but never trained, so `sum(p.numel())` over the
whole module inflates the count. `revision_v3/…/PARAMETER_ACCOUNTING_REPORT.md` independently
puts the active path at 63,266.

**Plan:** instantiate the sequence-only config, sum parameters reachable from the forward
path only, print both numbers. Replace all four occurrences of 181,877 in the `.tex`
(abstract, contribution 2, §Model, Table `tab:baseline-config`) and the 742,625-byte
checkpoint-size sentence in §RQ4. Add a footnote stating the inactive branches are excluded.

### S2 — Land the architecture ablation (P5, AIR-1, M1-adjacent) · 3–4 h · certainty: total
**Already run.** 5 controlled variants × 3 seeds × 5 folds = 90 units, 78,840 predictions,
with cap-correct transformed inputs and fold-clustered CIs.

**Plan:**
```
git checkout 699ab37 -- revision_v2/experiments/long_context_ablation_v3 \
                        revision_v2/results/long_context_ablation_v3 \
                        revision_v2/protocols/long_context_ablation_v3.md
python3 revision_v2/experiments/common/frozen.py verify   # must print OK: 144
```
Then add one table from `PAPER_RESULT_PACKET.md` (6 rows) and one mechanism-contrast table
(6 rows) — this is exactly P5's requested deliverable (remove attention → `chunk_mean`;
reduce max length → 2K vs 16K controls; hierarchy → flat vs chunked), and it is
parameter-matched, which is stronger than what P5 asked for. Rewrite §Discussion ¶2 around
the "attention buys robustness, not clean accuracy" claim. ~0.8 page.

**Cost:** the clean headline drops from "first of seven" to a bounded mechanism claim. Take
that trade; it is why the paper survives review.

### S3 — Report the cheap-emulator control (M1, O1) · 3 h · certainty: total
**Already run** as Gate 0A. This is the shortcut-learning check M1 called the
highest-value fix, and it came back positive — the shortcut is real.

**Plan:**
```
git checkout f86be6f -- reports/gate_0a_rule_emulator.md reports/gate_0b_knn_baseline.md \
   revision_v2/experiments/gate_0a_rule_emulator revision_v2/results/gate_0a_rule_emulator \
   revision_v2/experiments/gate_0b_knn revision_v2/results/gate_0b_knn
```
Add a 4-row table (AuthGuard-Seq / logreg-15 / tree-d4 / single boolean) with the paired CI
column, plus 2 paragraphs: (i) the reference rule is *cheaply recoverable* from bytecode —
this is a finding about the task, and it strengthens the deployability argument; (ii) the
neural model's justification is therefore robustness (S2's F200 result), not clean accuracy.
Include Gate 0B (kNN 0.6121, Δ=−0.302) as the memorization control — it PASSED, so it is
free evidence that the family-disjoint split works.

### S4 — Add the staged-triage cost result (AIR-5; new non-AI contribution) · 2–3 h · certainty: total
**Already run and verified** (`VERIFICATION.json` status PASS, 60 warm records, restored
artifact SHA-256s match exactly).

**Plan:**
```
git checkout a79a7ea -- revision_v2/experiments/reference_analyzer_cost_v1 \
                        revision_v2/protocols/reference_analyzer_cost_v1.md
git checkout f86be6f -- reports/gate_0c_analyzer_cost.md
```
Add a short §Motivation-for-staged-triage subsection + 1 small table (median / p95 / max /
warm serial wall / cold compile / peak memory). Put the 652× ratio in the abstract and
contribution list.

**Mandatory scoping** (write these sentences, do not omit): pinned official Gigahorse
decompiler/lifter only; **no downstream client rule was attached**; not the exact Huang et al.
analyzer; not an accuracy, utility, or substitutability comparison; 60 deterministic
family-distinct inputs, not the full corpus. And per Gate 0C's own conclusion, note that the
speedup accrues to *bytecode-level screening in general*, of which the 2.626 ms emulator is
also an instance — do not claim it as AuthGuard-Seq's unique advantage.

### S5 — Temporal evaluation (P2, AIR-7) · two tiers · certainty: T1 total, T2 moderate
AIR-7 declared this "unavailable — the frozen corpus has no timestamp." **That is now false.**
`main`'s fresh-dataset sprint collected a strictly later, Ethereum-mainnet delegate
population with block heights and timestamps:

- `data/collected_delegates/v2_ethereum_population.csv` — 760 delegates, 752 screenable
- blocks 25,595,134–25,695,421, **2026-07-23 → 2026-08-06**
- 669 unique runtime bytecodes
- **bytecode-hash overlap with the entire benchmark (all 3,082 rows): 0.** 669/669 are new.
  (22 addresses recur, but with different bytecode.)

That is a clean temporal holdout. Two tiers:

**T1 — unlabeled temporal drift check · 3–4 h · do this regardless.**
Score all 752 with the 15 frozen CV checkpoints, apply the validation-derived 1/5/10%
thresholds unchanged, and report flag rate + score distribution against the benchmark's
negatives and the external benign control. Claim: *operating-point stability on a
temporally disjoint, independently collected delegate population.* No labels asserted, so no
ground-truth claim to defend. **Required first:** run the MinHash family assignment across
the union of the two corpora and confirm no fresh bytecode joins a training family — exact-
hash disjointness alone is not enough for a leakage claim.

**T2 — labeled temporal test · ~1 day, moderate risk · attempt only if T1 lands early.**
Re-run the *actual label-defining rule* on the 752 fresh delegates to get reference labels
under the identical definition, then report true temporal AUPRC / Recall@5%FPR.
- Rule: `USENIX EIP-7702 artifact/eoa_detect/decompile/analyze.dl`; its `../clientlib/`
  includes resolve from `/opt/gigahorse/gigahorse-toolchain/clients/` inside the pinned
  image; `gigahorse.py` takes `-C/--client`.
- Image `ghcr.io/nevillegrech/gigahorse-toolchain@sha256:f676ca8a…910743` (2.69 GB) **has
  been pruned from this host** — re-pull first.
- Compute: cold Datalog compile ≈264 s, then 752 × ~3.5 s ÷ 6 jobs ≈ 8 min. Trivial.
- **Risk:** the client rule has never actually been executed in this project — it is logged
  as the highest-value *unmeasured* item. Budget half a day for it failing, and hard-stop if
  it does; T1 already satisfies P2 at a reduced but honest strength.

This is also the strongest available partial answer to P1/O1: it demonstrates the label rule
is reproducible and that the model transfers to a newly collected, newly labeled population,
without any human-labeling claim.

### S6 — Expand legitimate-delegate controls (P4, M3) · 3 h · certainty: high
`benign_7702_bytecode.csv` holds 45 rows = **8 unique projects / 8 unique bytecodes**
(MetaMask StatelessDeleGator, Ambire, ZeroDev Kernel v3.3, Biconomy Nexus v1.3.1, OKX
SmartWalletEntry, Uniswap Calibur v1.1.0, Alchemy SemiModularAccount7702, Coinbase
EIP7702Proxy) — replicated across 6–7 chains at identical addresses. That takes the
qualitative control from n=5 to n=8 real, nameable, production delegates.

**Blocking constraint from `legitimate_registry_expansion_v1` Phase 0** (already frozen):
the overlap audit found **23 address matches and 3 projects already represented in primary
training/evaluation families.** Scoring current checkpoints on those 3 is leakage.

**Plan (cheap, honest):** report a per-project table (project, chains, bytecode length,
mean score across the 15 CV models, tier at the 5% threshold) that **explicitly marks the 3
overlapping projects and excludes them from any headline number.** State that a
leakage-clean evaluation requires project-family-holdout retraining and is left as future
work. Do *not* do the retrain — it is ~1 day and would invalidate the frozen checkpoints
everything else in the paper uses.

**Optional bonus negative population:** the fresh corpus's 305 rubric-"B" delegates can be
cited as an additional *weak* real-7702 negative control, framed with zero ground-truth
claim ("rubric-assigned, not adjudicated"). Only if space remains.

### S7 — Track-fit paragraph + keywords (M5) · 1 h · certainty: total
One paragraph in §Introduction or §Discussion connecting pre-authorization screening to
*trust establishment under delegated execution*: EIP-7702 transfers execution authority from
a key-holder to unverified third-party code, so the authorization boundary is a trust
decision made under information scarcity; screening is a trust-signal substitute when
reputation and history are absent. Add keywords: trust, delegated execution, adversarial
robustness, blockchain security evaluation. Cheapest desk-reject insurance available.

### S8 — Prose and Limitations honesty pass (m1, m2, m5, m6, m8, M6) · 2 h · certainty: total
- m1: state in prose that Recall@5%FPR = 0.833 means **~17% of flagged delegates are missed**
  at the recommended operating point.
- m2: one sentence that thresholds must be **recalibrated on the deployment population**
  (5%→6.5%, 10%→16.9% observed on the external control).
- M6/m6: in Table `tab:robust`, visually and textually separate **execution-audited**
  Flood-200% (100/2,190 ≈ 4.6% of calls, no divergence observed) from
  **representation-stress-only** Rewrite+Flood-200%. A `\midrule` plus an explicit table note.
- m5: one-line caveat that cuDNN algorithm selection moved a comparable recall metric by up
  to 0.026 elsewhere in this project, so ±0.014 may understate cross-hardware variance.
- m8: one sentence naming the intended final deployment artifact (currently only per-fold /
  per-seed CV checkpoints exist; the timed one is seed-7702/fold-0).

### S9 — Ethics, disclosure, artifact-availability statements (m3, m4) · 1 h · certainty: total
Near-standard at security venues and their absence is noticed. Artifact statement should
promise what you can actually deliver: deterministic reconstruction scripts, split and
family assignments, SHA-256 manifests, per-row predictions — **not** redistribution of the
USENIX-derived bytecode corpus (see N6).

### S10 — Citation stability (m7) · 30 min · certainty: high
`huang2026darkside` is cited "to appear" at USENIX Security '26 — that conference is in
August 2026, so proceedings may now exist; check and update. `qi2025eip7702` and
`smartbugbert2025` are arXiv preprints; check for published versions.

### S11 — Presentation nits · 30 min
Rename `figure-1-bak.png` / `figure-2-fixed.png` to descriptive names. Confirm the TPS CFP's
exact page limit and blind-review policy before the final formatting pass — this has still
not been pulled and it governs the author block.

### S12 — Additional seeds (M4) · 2–4 h GPU · certainty: high · **optional**
3 seeds is thin. Cheapest sufficient version: rerun **only** AuthGuard-Seq, Flat CNN, and
XGBoost at seeds 7705/7706 via `revision_v2/experiments/baseline_v2/run_baseline_v2.py`
(GPU present: RTX 2080 SUPER; authguard_seq is ~10–30 s per fold/seed). If time is short,
skip and state 3 seeds as an explicit limitation — reviewers accept the acknowledgment.

---

## 2. NOT SOLVABLE NOW — and why

### N1 — Human ground-truth labels (P1, O1) — **the central limitation; not closable**
You have ruled out human labeling, and independently the repo shows it cannot be faked:
- `revision_v2/artifact/label_audit/` is a complete 170-item blinded 3-reviewer package with
  **zero completed forms** (`agreement_results.json` → 0), and its evidence packets are
  themselves bytecode-derived, so it would *reproduce* the circularity rather than break it.
- `revision_v3`'s pre-registered pipeline is well-built scaffolding with **zero labels run
  through it**.
- `main`'s "human review" was **300/300 accepted, 0 changes** — its own report says it should
  be called "rubric labels ratified by a human," not independent judgment.

Breaking circularity requires ≥2 independent adjudicators over a stratified sample with
*non-bytecode* evidence (deployment context, transaction traces, victim reports). Days of
human time you do not have. **Mitigation:** S5-T2 (label reproducibility + transfer to a
newly labeled population) plus rigorous claim-scoping per
`revision_v2/audit/LABEL_CLAIM_CONTRACT.md` — the paper already does this correctly, say
"source-flagged delegates," never "malicious," and state the limitation in the abstract, not
only §Limitations.

### N2 — Cross-dataset test on Qi et al. (AIR-8)
No task-compatible bytecode/label artifact for that work exists in the repo, and acquiring,
aligning, and de-duplicating a third-party corpus against 790 families is not a 4-day task
with uncertain data availability.

### N3 — Full USENIX-pipeline accuracy comparison (O2)
S5-T2 would give you the rule's *labels* on fresh data, but a genuine accuracy comparison
additionally requires adjudicating every disagreement between rule and model — which needs
N1's ground truth. Keep the existing correct posture: never write "the USENIX detector," only
"the reimplemented shipped facts," and state the full pipeline was not executed end-to-end.

### N4 — ONNX/WASM browser-extension deployment measurement (AIR-10)
Real engineering (export, opset compatibility, WASM preprocessing port, benchmark harness)
with no scientific payoff for TPS. The existing local CPU measurement already supports the
"lightweight" claim. Explicitly future work.

### N5 — Adaptive / white-box adversarial robustness
Requires designing attacks against the deployed feature path plus adversarial retraining and
re-running the full statistical protocol. The current threat model already scopes robustness
to two named transformation protocols — keep that scoping and do not widen it.

### N6 — Full public benchmark release (P6, AIR-10, m3)
Partially blocked, not fully. The blocker is **licensing for redistributing
USENIX-artifact-derived bytecode**, which cannot be resolved in 4 days. What you *can* ship
now: deterministic reconstruction scripts, family assignments, fold IDs, SHA-256 manifests,
per-row predictions, and the evaluation protocol. Promise exactly that in S9 and frame
AuthGuardBench-7702 as a benchmark *contribution* (P6) whose data-release path is documented
— that argument does not require the bytes to be hosted by the deadline.

### N7 — Large-scale legitimate-delegate scrape (P4, ambitious version)
There is no enumerable registry of legitimate 7702 delegates; the 8 projects in
`benign_7702_bytecode.csv` are close to the nameable universe as of early 2026. Worse, the
frozen overlap audit shows 3 of them are already inside primary training families, so
"more data" mostly buys more leakage to disclose. S6 captures the achievable gain.

### N8 — Recovering a positive architecture-novelty result
Closed by four independent failed searches, all frozen: Gate A (dual-view representation —
beaten by a trivial first-STOP heuristic, 0.969 vs 0.881), Gate B (selective escalation),
`risk_focused_aggregation_v1` (gated aggregation — PARTIAL; significantly worse than plain
attention and attends *more* to benign donor chunks), `revision_v3`'s DCRG typed-guard
semantics (delta ≈ 0, CI crosses zero) and relational GNN (actively worse). Do not restart
this. P3 is right, and following P3 is also the only option.

### N9 — Anything depending on `revision_v3` or `main`'s null result
`revision_v3/paper_submission/main.tex` has `\resultsreadyfalse` hardcoded with every result
macro bound to `\pending{TBD}` — mechanically unsubmittable. `main`'s fresh-dataset model
results are at chance (Recall@5%FPR = 0.000 across all three arms, 51-contract test set with
9 positives) — a legitimate negative result, not evidence. Neither is an evidence base.
**Exception:** `main`'s *collection* artifacts are excellent and are exactly what S5 uses —
take the data, leave the labels and the models.

---

## 3. Suggested execution order

**Day 1 (Aug 11)** — S1, S3, S2 recovery + frozen-guard verify, S7. Decide the reframe.
**Day 2 (Aug 12)** — S2 and S3 write-up, S4, S5-T1.
**Day 3 (Aug 13)** — S5-T2 if T1 landed early (hard-stop by evening), else S6 + S8.
**Day 4 (Aug 14)** — S6, S8, S9, S10, S11, full rebuild, page-limit and CFP-compliance pass.
**Aug 15** — submit with a day of slack, not on the deadline.

Page budget: current 8 pages, limit 10. New content ≈ S2 0.8 p + S3 0.5 p + S4 0.4 p +
S5 0.5 p + S6 0.3 p + S7/S8/S9 0.5 p ≈ **+3.0 p** → over by ~1. Recover it by cutting
Table `tab:clean` from 7 rows to 4 (the ablation table supersedes the model-count ranking
anyway), merging `tab:design-map` into prose, and tightening §Background.

**Guard rail:** run `python3 revision_v2/experiments/common/frozen.py verify` before and
after every session — it must print `OK: 144 frozen files verified unchanged`. The paper
`.tex`/`.pdf` are not in that ledger and are free to edit.
