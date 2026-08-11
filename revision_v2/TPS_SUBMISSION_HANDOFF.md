# AuthGuard-7702 — TPS 2026 Submission Handoff

Purpose of this document: a self-contained record of where this project stands, so a new chat
session (or you, cold) can resume without re-deriving any of it. It supersedes
`revision_v2/HANDOFF_PROMPT.md` (that file targeted ICTAI and a GPU-machine continuation of
revision_v2 experiments — both now moot; kept only for historical record of Phase 0–5 work).

---

## 1. Current target

**Venue:** IEEE TPS 2026 — 8th IEEE International Conference on Trust, Privacy and Security in
Intelligent Systems and Applications.
**Track:** "Security, Privacy, and Trust in Blockchain and Distributed-Ledger Technologies."
**Deadline:** 2026-08-15. Today is 2026-08-11 — **4 days remain.**
**Key difference from the earlier ICTAI target:** no mandatory AI-novelty requirement. This
removes the single biggest source of difficulty in the project's history (see §2, Path 1 and
Path 2 below) and is why the plan is now much simpler than it was a week ago.

## 2. How the project got here — five divergent paths

The repository forked into five paths after a shared checkpoint ("paper rewrite handoff",
2026-07-18). All were investigated via read-only `git show`/`git log` forensic research
(nothing below required checking out a branch). Full findings are in this conversation's
history; this is the condensed version.

### Path 1 — `revision_v2/` (this workspace; branch `revision-v2`, merged into `tps-revision-v3`
then into `main`)
Built for the original ICTAI target. Corrected the original AuthGuard-7702 pipeline's
methodological issues: in-sample threshold selection → inner family-grouped out-of-fold
selection; single fixed flooding donor → partition-isolated multi-donor pools with full
provenance; missing FPR; missing family-clustered uncertainty. All of Phases 0–5 (protocol
correction, construct-validity package, baselines/ablations, decision-gated novelty search,
Gigahorse-feasibility fork) completed and frozen — see `revision_v2/reports/`,
`revision_v2/results/`, `revision_v2/protocols/`.
**The novelty search (Gate A: a "conservative terminal-aware dual-view" bytecode
representation) FAILED** — a trivial "truncate at the first STOP opcode" heuristic beat it on
clean AUPRC (0.969 vs 0.881 for the original XGBoost AuthGuard). Gate B (selective escalation)
also failed. Verdicts frozen at `revision_v2/results/gateA/gateA_verdict.json` and
`revision_v2/results/gateB/gateB_verdict.json`.
**After my session ended, another session continued directly under `revision_v2/`** (not the
`revision_v3/` rewrite) and built a real neural model, `AuthGuard-Seq` (hierarchical
opcode-chunk + attention architecture), with a full statistically-validated evaluation:
`revision_v2/experiments/baseline_v2/`, `revision_v2/experiments/robustness_operational_v2/`,
`revision_v2/experiments/statistical_analysis_v2/`, `revision_v2/experiments/authguard_fusion/`.
Key summaries: `revision_v2/results/robustness_operational_v2/ROBUSTNESS_OPERATIONAL_FINAL_SUMMARY.md`,
`revision_v2/results/statistical_analysis_v2/STATISTICAL_FINAL_SUMMARY.md`. This produced the
numbers that became the paper draft in §3.
**Strong:** rigorous, fully frozen/hashed/reproducible, statistically significant headline
results (paired family-clustered bootstrap CIs excluding zero throughout).
**Weak:** the AI-novelty question (Gates A/B) never got resolved positively — irrelevant for
TPS, was the central blocker for ICTAI.

### Path 2 — `revision_v3/` (branch `tps-revision-v3`, merged into `main` at `cf8e8ea`)
An independent, from-scratch reimplementation (GPU/PyTorch) that treats `revision_v2/` as a
frozen input. Explored real architectural novelty: hierarchical chunk models, a "DCRG"
(Delegation-Context Risk Graph) with typed authority-guard semantics. Extremely high
engineering rigor — caught and fixed a real bug in the parameter count claimed for
`AuthGuard-Seq` (181,877 claimed vs. 63,266 truly active — see §4, M2) and a real
bootstrap-CI-averaging bug that flipped 4 conclusions. Built a genuinely well-designed,
code-tested, score-blind human-annotation pipeline (pre-registered protocol, frozen scoring
locks, ~230 gold-set items + 300 "post-cutoff" temporal items sampled from fresh on-chain data).
**Strong:** self-correcting, honest, real bug-catching, a credible path to solving label
circularity.
**Weak:** **every architectural novelty attempt failed to survive parameter-matching or
donor-isolated ablation** (DCRG typed-guard delta ≈ 0, CI crosses zero; a relational GNN made
things *worse*). **Zero human labels were ever completed** — the entire annotation pipeline is
scaffolding with nothing run through it. The paper draft
(`revision_v3/paper_submission/main.tex`) has `\resultsreadyfalse` hardcoded and every result
macro bound to `\pending{TBD}` — mechanically not submittable. Known-legitimate deployments
(ZeroDev, Coinbase, MetaMask-style infra) get majority `WARN` in broader testing — a real
deployment-credibility problem. **Not usable for the Aug 15 deadline.**

### Path 3 — `main`'s fresh-dataset sprint (commits `46c6ab0`…`55d3e3a`, 2026-08-06, "final
result", now part of current `main` HEAD)
A separate, from-scratch effort: collected ~100k fresh Ethereum blocks, recovered signers,
applied an LLM-assisted labeling rubric, ran two rounds of "human review." Genuinely
independent sourcing (not derived from the USENIX artifact).
**Strong:** honest, well-documented, real leakage checks, real signer-recovery validation.
**Weak:** "LLM labeling" was a Claude session hand-applying a rubric (disclosed, not an API
call); "human review" was **300/300 rubber-stamp acceptance, 0 changes** — the report itself
says this should be called "rubric labels ratified by a human," not independent human
judgment. Final model results are **at chance** (AUPRC ≈ prevalence baseline,
Recall@5%FPR = 0.000 across all three tested arms) on a tiny test set (51 contracts, 9
positives). A legitimate negative result, not a working detector. **Not usable as the paper's
evidence base.** Key docs: `docs/dataset_workflow_plan.md`, `reports/model_results.md`,
`reports/limitations.md` (repo root, not under `revision_v2/`).

### Path 4 — `new-review-based-plan` (branch, not merged)
A single-commit planning/audit document (`PROJECT_AUDIT_FOR_TPS.md`), no execution. Superseded
by Path 2's fuller execution of the same roadmap. No further relevance.

### Path 5 — stub branches `claude-revision-3` and `revision-3` (not merged)
Small, abandoned. `claude-revision-3` ran a real Gigahorse cost comparison (median
2.687s/contract vs. AuthGuard's ~4ms — a genuine 652× number, potentially useful as a
motivating statistic if reproduced under the current paper's own methodology before citing).
`revision-3` is a precursor to Path 2's parameter-matched multiscale work, already absorbed
there. Neither is needed going forward.

## 3. The selected path and artifact

**Decision:** freeze scope on **Path 1 only** (`revision_v2/`). Do not touch `revision_v3/` or
`main`'s fresh-dataset directories before the deadline — both are unfinished and add risk with
no offsetting benefit now that AI novelty isn't required.

**Selected manuscript:** `revision_v2/paper_final/AuthGuard_7702_revision_v2.tex` (also compiled
at `revision_v2/paper_final/AuthGuard_7702_revision_v2.pdf`). This was explicitly identified by
the project owner as "the final submission ready version."

*Note:* a second, broader draft also exists — `revision_v2/paper_extended/main.tex` (846 lines,
more sections including an explicit "Negative Results and Claim Decisions" appendix). It was
**not selected** as the base, but may be worth mining for specific passages (e.g. its more
elaborate Limitations/Discussion structure) when expanding the selected draft's Limitations
section (see §4, M1/M3/M5/M6).

### What the selected draft claims (headline numbers, all sourced from `revision_v2/experiments/{baseline_v2,robustness_operational_v2,statistical_analysis_v2}/`)

- **Benchmark:** "AuthGuardBench-7702" — 2,190 primary rows (727 flagged / 1,463 unflagged),
  790 bytecode-similarity families, plus 797 external benign controls and 5 curated legitimate
  EIP-7702/account-abstraction controls. (This is a further-audited version of the original
  task-aligned corpus — 90 rows were additionally excluded for truncated/corrupted bytecode
  discovered after my original Phase-0–5 work; the shrinkage is documented and consistent.)
- **Model:** `AuthGuard-Seq` — hierarchical opcode-chunk (256 tokens/chunk, ≤64 chunks) +
  learned attention, claimed 181,877 parameters (see M2, this is inflated).
- **Clean:** AUPRC 0.924±0.014, Recall@5%FPR 0.833±0.016 — best of 7 evaluated baselines.
  vs. Flat CNN: Δ+0.039 AUPRC, 95% CI [+0.009,+0.073]. vs. XGBoost: Δ+0.091, CI [+0.045,+0.140].
- **Flood-200%:** AUPRC 0.920±0.007 (execution-preservation spot-checked on 100/2,190 calls).
- **Rewrite+Flood-200%:** AUPRC 0.912±0.005 (representation-stress only, not execution-verified).
- **External benign control (n=797):** FPR 0.015/0.065/0.169 at nominal 1%/5%/10% thresholds.
- **Latency:** full local screening median 4.121 ms, p95 14.547 ms, p99 21.429 ms (AMD Ryzen 5
  3600, CPU, single thread).
- All primary comparisons use 10,000-replicate paired family-clustered percentile bootstrap;
  none of the reported headline CIs cross zero.

## 4. Senior-reviewer critique (TPS "Security, Privacy, Trust in Blockchain/DLT" track perspective)

Full critique delivered in conversation; condensed here with file-pointers. Overall verdict:
**solid enough for major-revision, not reject — several items below are exactly the kind that
sink otherwise-good security papers if left unaddressed.**

### Major concerns

- **M1 — No shortcut-learning check, and there is direct internal evidence this is a live risk.**
  A trivial first-STOP-truncation heuristic nearly matched/beat the full-feature baseline on a
  closely related corpus earlier in this project (`revision_v2/results/gateA/gateA_verdict.json`,
  `revision_v2/protocols/gateA_success_criteria.md`) — a textbook shortcut-learning signature
  (flagged vs. unflagged delegates differing systematically in length/complexity, independent of
  actual risk). **Highest-value fix available**: add a length/complexity-only ablation or the
  first-STOP baseline as a control and report the result either way.
- **M2 — Parameter count (181,877) is provably wrong as stated.** Verified directly in
  `revision_v2/experiments/authguard_fusion/run_authguard_fusion.py`: `AuthGuard-Seq` is the
  `sequence_only` config (`active_views=(True, False, False)`) of a shared `FusionModel`; the
  ngram and dense-structural branches are instantiated but never trained in this configuration,
  so a naive `sum(p.numel())` inflates the true active-path count. (`revision_v3`'s
  `PARAMETER_ACCOUNTING_REPORT.md` independently found the true active count is 63,266 for the
  equivalent architecture.) **~30 minute fix.**
- **M3 — Legitimate-project false-alarm evidence is thin (n=5) and internal evidence elsewhere
  in this project (Path 2, different pipeline) found roughly half of known-legitimate
  deployments got majority high-risk warnings.** Doesn't directly contradict the n=5 result
  (different model), but a security reviewer will not accept n=5 as sufficient for a
  "pre-authorization triage" claim. Expand the control set if time allows; otherwise soften RQ3
  framing and state explicitly in Limitations that it's a preliminary spot-check.
- **M4 — Only 3 training seeds** for the neural variance estimate; reviewers will want 5+ or an
  explicit acknowledgment of this as a limitation.
- **M5 — Track-fit isn't argued.** No engagement with "Trust" or "Privacy" literature; a
  reviewer unfamiliar with EIP-7702 may ask why this is at TPS at all. **Cheap fix, high
  payoff:** one paragraph connecting pre-authorization screening to trust-establishment in
  delegated/account-abstraction systems.
- **M6 — Execution-preservation audit (100/2,190 ≈ 4.6%) is undersized for the claim weight it
  carries.** Table 8 shows the execution-verified Flood-200% and the *unverified*
  Rewrite+Flood-200% conditions with equal visual weight — distinguish them more clearly, or
  expand the audit.

### Minor concerns

- **m1** — Recall@5%FPR = 0.833 means ~17% of flagged-risk delegates are missed at the
  recommended operating point; state this in prose, not just in the table.
- **m2** — Threshold transfer degrades under distribution shift (nominal 5%→observed 6.5% on
  external control, nominal 10%→16.9%); add a sentence on recalibration for deployment.
- **m3** — No artifact/data-availability statement.
- **m4** — No ethics/responsible-disclosure/conflict-of-interest statement (near-standard at
  security venues).
- **m5** — GPU non-determinism: elsewhere in this project (Path 2), cuDNN algorithm selection
  swung a comparable recall metric by up to 0.026 — the reported ±0.014 std may understate
  cross-hardware run-to-run variance. Worth a one-line caveat even without re-running anything.
- **m6** — Table 8 doesn't textually/visually distinguish the execution-verified vs.
  representation-stress-only conditions (see M6).
- **m7** — `smartbugbert2025` and `qi2025eip7702` are arXiv preprints; the primary label source
  `huang2026darkside` is cited as "to appear" — verify these are stable/citable before the
  deadline.
- **m8** — No stated final deployment model (only per-fold/seed cross-validation artifacts are
  described); one sentence would close this gap.

### Presentation nits (fix only if time remains)

- `figure-1-bak.png` / `figure-2-fixed.png` — work-in-progress-looking filenames.
- Add TPS-relevant IEEEkeywords: "trust," "adversarial robustness," "blockchain security
  evaluation."
- Confirm TPS's exact page limit and blind-review policy from the CFP (not yet obtained/checked
  in this project) before final formatting pass.

### If you only fix three things

1. **M2** (parameter count) — ~30 min, removes a credibility landmine.
2. **M1** (shortcut-learning ablation) — highest scientific value; machinery already exists from
   earlier Gate A work; probably a half-day.
3. **M5** (track-fit paragraph) — cheap, directly addresses "why TPS" desk-reject risk.

Everything else is a reasonable candidate for an honestly-expanded Limitations section instead
of an actual fix — TPS reviewers tend to reward candor about deployment risk more than silence.

## 5. Status as of this document

**No edits have been made to the paper yet.** The above is a review, not a changelog. The
natural next actions, in priority order, are M2 → M1 → M5, then triage the rest against
remaining time and the actual TPS page limit (still need to pull the CFP).

## 6. What NOT to do with the remaining time

- Do not reopen `revision_v3/` (unfinished human labels, failed novelty search).
- Do not try to finish or lean on `main`'s fresh-dataset null result.
- Do not restart any architecture/novelty search (Gate A/B are closed questions for this
  submission).
- Do not touch frozen files (`revision_v2/experiments/common/frozen.py verify` should stay
  green — 144 originally-frozen files; run it before/after any edit session as a sanity check,
  though the paper `.tex`/`.pdf` files themselves are not part of that ledger and are fine to
  edit directly).
