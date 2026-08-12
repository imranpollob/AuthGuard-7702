# Reviewer readiness audit — TPS 2026 draft

Audit of `revision_v2/paper_final/AuthGuard_7702_tps2026.tex` (9 pp) against all 34 recorded
review items, plus a hostile-reviewer read of the risks the rewrite itself introduces.
Written 2026-08-11.

Sources: **AIR-1..11** (AI review), **M1..M6 / m1..m8** (senior-reviewer critique),
**P1..P6** (professor), **O1..O3** (hostile ICTAI assessment).

---

## 1. Scorecard

### Fully addressed (18)

| Item | Where |
|---|---|
| AIR-1, P5 — architecture ablations | Table IV, parameter-matched, 3 mechanisms with CIs |
| AIR-2 — Flood-200% budget confound | Cap-correct ablation; capacity audit (0% clean inputs exceed at 16K) |
| AIR-5 — measure source-analyzer cost | Table IX; 2.687 s median, 652×, fully scoped |
| AIR-7, P2 — temporal split | §VI-C, 752 live delegates, family-level leakage gate |
| AIR-9 — baseline credibility | 7 clean baselines + emulator + kNN + 5 matched ablation variants |
| AIR-11 — framing and title | Retitled; leads with the adversarial finding |
| M1 — shortcut-learning check | §VI-A reports the 15-feature emulator tying the neural model, as a result |
| M2 — parameter count | 63,266 active; §IV-C paragraph explains the naive-sum error |
| m2 — threshold transfer degrades | §VI-C; "recalibration is mandatory before deployment" |
| m3 — artifact statement | §VII-C |
| m4 — ethics / disclosure / COI | §VII-B |
| m5 — GPU non-determinism | §VII-D limitations |
| m6 — exec-verified vs representation-stress | §V-C: flooding 100/100, address rewrite 23/100, marked separately |
| P3 — downplay architecture novelty | Explicit: "We do not claim architectural novelty" |
| O1 (partial→strong) — circular labels | §III-A: relative comparison under shared label does not require ground truth |
| Presentation nits | Figures restored, tables reflowed, 0 overfull boxes |
| Replicate-count honesty | Stated per table (10,000 / 2,000 / 1,998) |
| Family-threshold exposure | §VII-D limitations: 43.6% in the 0.7–0.9 band |

### Partially addressed (9)

| Item | State | Residual risk |
|---|---|---|
| **M3, P4 — legitimate controls** | 8 named projects, but **3 excluded for training-family overlap → effectively n=5 usable**, same as the criticised draft | Reviewer sees the original objection unfixed |
| **M6 — execution-preservation audit** | Now honest and split, but still 100 calls / 10 delegates | Undersized for the weight it carries |
| **M5 — track fit** | Keywords + one intro sentence on trust | No dedicated paragraph; "why TPS" only implicitly answered |
| **AIR-4 — expand legitimate controls** | Registry frozen, overlap audited | Leakage-clean evaluation needs project-family-holdout retraining, not done |
| **AIR-10 — artifact packaging** | Statement written, manifests exist | No public release; no ONNX/WASM |
| **P6 — benchmark as lasting contribution** | Claimed as C2 | Not actually released; licensing unresolved, so the claim is a promise |
| **O2 — no full-pipeline comparison** | Carefully scoped; client rule explicitly not run | A reviewer may still want the real rule executed |
| **O3 — residual high FP** | Now *measured* on live traffic: 20.3% / 9.4% weighted | More exposed than before (see §2.5) |
| **AIR-3 — first-STOP finding** | Dropped from the paper | Defensible (judged "overstated") but it was a real internal finding |

### Not addressed (7)

| Item | Why |
|---|---|
| **P1, AIR-6 — human ground-truth labels** | Out of scope by your decision; mitigated structurally by the relative framing, not solved |
| **M4 — more than 3 seeds** | Still 3; acknowledged in limitations |
| **AIR-8 — Qi et al. cross-dataset** | No task-compatible artifact available |
| **m1 — state the ~17% miss rate in prose** | **Genuinely missed.** The paper states the 0.181 residual ASR but never says Recall@5%=0.833 means ~17% of flagged-risk delegates go undetected |
| **m7 — citation stability** | Left for you; USENIX Sec '26 has likely occurred |
| **m8 — final deployment model** | **Genuinely missed.** Only per-fold/seed CV artifacts are described; no sentence on what would actually ship |
| **AIR-10b — browser runtime** | Deliberately deferred |

---

## 2. Hostile-reviewer read: what will actually get attacked

Ranked by how much damage it does if unanswered.

### 2.1 "Why not just adversarially train the baselines?" — **RESOLVED 2026-08-11**

The paper's core claim is architectural: attention aggregation confers robustness. The
obvious counter is that robustness could come from *training* rather than *architecture* —
augment Flat CNN's training set with flooded examples and the gap may close. The paper does
not mention adversarial training anywhere.

This is not speculative. `revision_v2/results/gadv_v2/` already shows augmentation helps
materially on the older pipeline:

| Model | F200 AUPRC, standard | F200 AUPRC, augmented |
|---|---:|---:|
| opcode-histogram XGBoost | 0.461 | **0.530** |
| AuthGuard (feature-based, v1) | 0.550 | **0.675** |

Augmentation buys +0.07 to +0.13 AUPRC. It does not reach AuthGuard-Seq's 0.920 under F200,
which is the defence — but that comparison is across different corpora and pipelines, and
**augmented Flat CNN under the adaptive attack has never been run**. A reviewer asking this
question currently gets no answer from the paper.

**Fix:** train Flat CNN and XGBoost with flooding augmentation on the v2 corpus and attack
them adaptively. If the gap persists, the architectural claim is enormously strengthened and
this becomes a headline row rather than a vulnerability. If it closes, we need to know before
a reviewer tells us. Estimated 4–6 h using existing machinery.

### 2.2 Mechanism attribution vs the instrument — **RESOLVED 2026-08-11**

Table VI argues fixed-transformation evaluation cannot rank screeners. Table IV attributes
robustness to attention using **only clean + fixed Flood-200%**. A sharp reviewer will note
that the mechanism claim rests on exactly the protocol the paper declares inadequate two
subsections later.

There is a real defence — Table VI's point is that fixed transforms fail to separate models
that are *close* (emulator vs AuthGuard-Seq), whereas the ablation gaps are large and their
CIs exclude zero — but the paper never states it, so right now it reads as an inconsistency.

**Fix, strong:** run the adaptive attack against `chunk_mean_control_16384` and
`flat_control_16384`. That directly tests "is it attention or just chunking?" under the
adaptive protocol and closes the loop. Estimated 3–4 h.
**Fix, cheap:** two sentences reconciling the two tables. 15 minutes.

### 2.3 Threat model vs deployment — **framing fix applied**

The paper positions AuthGuard-7702 as a wallet-side screener. If it ships in a wallet, the
adversary has the weights, and the natural threat model is **white-box**, not 64-query score
access. §III-C explicitly withholds gradient access, and §VII-A lists white-box attacks as
unevaluated — honest, but a reviewer can reasonably say the evaluation is weaker than the
stated deployment demands.

**Fix:** either argue the score-access model (server-side screening service, or attacker
without model extraction), or add a bounded white-box gradient attack, or state plainly that
client-side deployment implies a stronger adversary than evaluated and scope the claim to
service-side screening. The framing fix is cheap and should happen regardless.

### 2.4 "0.181 means one in five gets through"

Within our own, arguably weak, threat model, 18% of detected risky delegates are already
evadable at zero attacker cost. The paper states this honestly in limitations, which helps,
but does not answer the deployability question it raises.

**Fix:** report ASR at the stricter 1% operating point, and frame explicitly as defence in
depth — the screener raises attacker cost and routes to deeper analysis, it does not
terminate the attack. Cheap.

### 2.5 "You flag 20% of live traffic"

RQ3 self-reports a 20.3% flag rate at the nominal 5% point on real traffic. This is
excellent scientific practice and a reviewer may still read it as the paper disproving its
own deployability. The 9.4% authorization-weighted figure and the "flag rate not FPR"
argument both help, but neither can be verified without labels.

**Fix:** lead the paragraph with the authorization-weighted number, and add the alerts-per-1000
framing already computed in the results file. Also consider reporting the 1% point (5.9%
weighted) as the deployment-realistic operating point. Cheap.

### 2.6 "Your attack is weak — random beats your guided search"

Random search outperforming beam search on every target invites the reading that the beam
was badly tuned, which undercuts "we tried hard." The paper explains the local-optimum
mechanism in one sentence.

**Fix:** state the budget-matched framing more assertively (we report max over strategies, so
a weak beam cannot inflate the defence), and note that random search *is* the strong attack.
Cheap.

### 2.7 The benchmark contribution is a promise

C2 claims a benchmark contribution but nothing is released and licensing is unresolved.
P6's ImageNet framing does not survive without an actual artifact.

**Fix:** either soften C2 to "protocol + reconstruction pipeline" or commit to a concrete
release vehicle in the artifact statement. Cheap, and worth doing honestly.

---

## 3. Recommended priority

**Must do before submission (about a day)**
1. Adversarially-trained baselines under adaptive attack (§2.1) — the one experiment that can
   still overturn the paper's central claim.
2. Adaptive attack on the two ablation controls (§2.2) — closes the structural inconsistency.
3. m1 and m8 one-liners; §2.3 threat-model framing; §2.4/2.5/2.6 framing fixes.

**Should do if time (half a day)**
4. Dedicated trust/TPS paragraph (M5).
5. Soften or substantiate the benchmark claim (§2.7, P6).
6. Citation stability (m7) and the author block.

**Explicitly not doing**
Human labelling (P1), Qi et al. transfer (AIR-8), ONNX/WASM (AIR-10b), >3 seeds (M4),
full USENIX pipeline execution (O2). All are recorded as limitations.


---

## 4. Update — 2026-08-11, after the two recommended experiments

**§2.1 resolved.** Augmentation does not substitute for architecture. Augmented Flat CNN and
XGBoost remain +0.774 and +0.786 worse than clean-trained AuthGuard-Seq under adaptive
search (CIs exclude zero); augmentation helps mainly against the fixed transform it was
trained on. The same intervention cuts AuthGuard-Seq from 0.181 to 0.062 at no clean cost,
so the two are complementary. Now a table block and three paragraphs in RQ2.

**§2.2 resolved.** The mechanism attribution was re-tested with the adaptive attack on the
parameter-matched controls: chunk attention 0.075 vs flat 0.889 vs mean 0.986 at ~30K
parameters each. Not an artefact of the weaker protocol.

**Bonus finding to act on.** The 30,050-parameter matched attention control is more robust
than the 63,266-parameter deployed model at equal clean detection. The paper now says the
smaller configuration is the one to deploy.

**New mechanistic evidence (not previously planned).** Attention mass on appended chunks was
measured directly across all 727 positives: 0.376 at Flood-200% where uniform weighting
would give 0.631 — 25.5 points of dilution resisted, widening monotonically with flooding.
This converts the design claim from inference to measurement, and its partiality explains
the residual 0.181 ASR.

**§2.3, §2.4, §2.5, §2.6, §2.7, m1, m8, M5** — framing fixes applied; see the manuscript.

**Still open:** M3/P4 (legitimate controls effectively n=5), M4 (3 seeds; new blocks are
single-seed), P1/AIR-6 (human labels), AIR-8 (Qi et al.), m7 (citations), O2 (full pipeline),
white-box adversary, public artifact release.
