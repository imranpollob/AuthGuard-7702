# PART B — Hostile ICTAI Reviewer Assessment

Role: a reviewer trying to reject. No defense; objections selected from the artifacts.

## 1. Three strongest rejection arguments

### O1 — Circular labels (positives are all rule-derived) — **MAJOR (near-fatal for a "detection" framing)**
- **Objection:** all 793 positives come from the one USENIX rule, so "detection" may be
  rule-mimicry; the model has never seen a positive the rule missed.
- **Evidence:** `capability_dataset.csv` label provenance; independent validation surfaced only
  1 confirmed novel delegate (`funnel.json`).
- **Rebuttable now?** Partly. **Rebuttal:** the name-match footprint fires on ~4% of held-out
  positives and is removed at M3, yet AuthGuard retains detection (`mutation_curve.json`), so
  0.856 is not the rule verbatim. **Residual risk:** the *structural* core of the rule is shared,
  so circularity is mitigated, not eliminated.
- **Experiment if not rebuttable:** an independent, rule-independent labeled positive set at
  scale (≥30–50) — currently INSUFFICIENT DATA.

### O2 — Simplified USENIX baselines / no full-pipeline comparison — **MAJOR**
- **Objection:** the paper compares against reimplemented *approximations* (sensitive-name,
  external-call), not the full Gigahorse/Datalog pipeline, then claims the deployed rule is
  brittle.
- **Evidence:** no Gigahorse run anywhere; baselines are bytecode reimplementations.
- **Rebuttable now?** Yes, with disciplined wording. **Rebuttal:** the paper must claim
  brittleness only of the rule's *shipped facts* it reimplements, never of "the USENIX detector,"
  and must state the full pipeline was not executed. The brittle components (name lexicon, hash)
  are defeated by construction (rename/metadata), independent of decompiler quality.
- **Experiment if not rebuttable:** faithfully run the full USENIX pipeline on M0–M3 variants.

### O3 — Weak/noisy negatives + residual high FP — **MAJOR**
- **Objection:** `benign_cleared` is rule-silent and contaminated (≤8.1%), and at the operating
  point AuthGuard already flags ~16–19% of benign, rising to 27.5% under heavy padding — too high
  for a wallet.
- **Evidence:** `supporting.json` contamination; `advtrain_results.json` FPR column.
- **Rebuttable now?** Partly. **Rebuttal:** contamination is bounded and disclosed; a
  cleaner-negative secondary task raises AUPRC (0.877); FP levels reflect a max-F1 threshold, and
  a higher-precision operating point exists. **Residual:** the padding FP is a genuine
  limitation, honestly reported, not fixed.
- **Experiment if not rebuttable:** reachability-aware features + PU-aware training to cut padded
  FP (see `next_improvement_recommendation.md`).

*(Lesser objections: limited AI-model novelty — see venue §5; mutation-equivalence uncertainty —
scoped by "structure-preserving"; independent validation insufficiency — reported as such.)*

## 2. Soundness hygiene audit
- **"semantics-preserving" in the current `.tex` (abstract + §mutation)** — **MUST FIX** to
  "structure-preserving" (only opcode-skeleton verified). Ground-rule 3 violation.
- **Abstract robustness sentence** predates the augmentation study; update to reflect PARTIALLY
  RECOVERS rather than an unmitigated weakness.
- **TESSERACT attribution** — Pendlebury et al., USENIX Security 2019: correct.
- **Transcend attribution** — Jordaney et al., USENIX Security 2017: correct text, but the
  **bibkey `pendlebury` points to the Jordaney/Transcend entry** — rename bibkey to avoid
  confusion (cosmetic but reviewer-visible).
- **Baseline names** — consistent ("sensitive-name rule approximation", "external-call structural
  over-approximation"); ensure the `.tex` never abbreviates these to "USENIX detector."
- **Inconsistent result values** — the `.tex` currently mixes G-DET (0.856) with G-VOL flooding
  numbers; ensure Tables follow the protocol-group rule (`recommended_tables.md`).
- **Full-USENIX-reproduced claim** — not present; keep it that way.
- **Independent-validation-succeeded claim** — must be stated as INSUFFICIENT DATA.
- **Arbitrary-adversary robustness** — not claimed; keep scoped.
- **Explanation claims** — evaluated (50-case audit, coverage 1.0, NN-mal 0.34); keep modest.
- **Decompiler runtime** — not measured; the `.tex` correctly avoids a speedup claim — keep.
- **`.tex` line 115** `0xef0100\textbackslash,\textbar{}address` renders wrong — fix escaping.

## 3. Safe-claims matrix (summary; full in `paper_claims_safe_vs_unsafe.md`)
See dedicated file.

## 4. ICTAI reviewer scores (1–5)
| Axis | Score | Accept-support | Reject-concern | Fixable? |
|--|--|--|--|--|
| Originality | 3 | first pre-signing EIP-7702 screen + evasion benchmark | applied, not conceptual | framing |
| AI novelty | **2** | leakage-safe protocol, source-balanced aug | standard XGBoost; no new architecture/loss | partly (frame as methodology) |
| Technical quality | 4 | leakage assertions, paired CIs, deterministic freezes | weak negatives | yes |
| Experimental rigor | 4 | family holdout, protocol groups, honest reconciliation | circular labels | partly |
| Tool usefulness | 4 | 3.4 ms pre-sign, real live-sweeper motivation | FP rate at operating point | yes |
| Reproducibility | 5 | seeds, frozen files, manifests, assertion logs | — | — |
| Presentation | 3 | clear narrative | `.tex` needs the reconciliation/wording fixes | yes |
| **Overall acceptance likelihood** | **3 (borderline)** | rigor + honesty + timely surface | AI-novelty + circularity | with revisions |

## 5. Venue assessment
ICTAI's tools track is defensible: the paper is an *applied AI tool* with a concrete decision
setting, a deployed-model evaluation, and an adversarial-robustness study — all within scope. The
weakest ICTAI fit is AI novelty: there is no new architecture, loss, or representation, so the
paper must be pitched as *methodology and tool*, foregrounding the leakage-safe family-grouped
protocol and the structure-preserving evasion benchmark rather than the estimator.

A blockchain-security venue (e.g., a smart-contract-security workshop) would value the EIP-7702
domain more and be more forgiving of the modest ML core, but would scrutinize the security
threat model and the label circularity harder, and would expect the full USENIX-pipeline
comparison. For ICTAI, reviewers are AI experts who will accept "standard estimator, rigorous
protocol" if the methodological contributions (leakage control, evasion robustness with paired
statistics, honest negative results) are the headline.

The emphasis that maximizes ICTAI acceptance: (1) generalization under family holdout as an
AI-evaluation contribution; (2) adversarial robustness with augmentation as an AI-robustness
contribution; (3) the tool/latency as the applied payoff. De-emphasize any implication of
detection completeness or full-pipeline superiority.

Overall: ICTAI tools track is appropriate provided the paper is framed as methodology+tool and
the wording fixes in §2 are made; it contains enough AI content (evaluation methodology +
adversarial training) for the venue, but not enough novel *modeling* to survive an
AI-novelty-first reviewer, so framing is decisive.
