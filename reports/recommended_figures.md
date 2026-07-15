# Recommended Figures

Existing figure files: `fig_family_size.png`, `fig_random_vs_family.png`, `fig_auprc.png`,
`fig_mutation_curve.png`, `fig_mutation_volume.png`, `fig_advtrain_clean.png`,
`fig_advtrain_seen.png`, `fig_advtrain_heldout.png`, `fig_advtrain_scoredist.png`,
`fig_independent_funnel.png`.

| # | Title | Purpose | x / y | Models/conditions | Takeaway | File | Main/App | Visual issues → fix |
|--|--|--|--|--|--|--|--|--|
| F1 | System architecture | orient AI reviewer | — | — | pre-signing, decompiler-free | (make TikZ) | MAIN | not yet drawn; build from `system_architecture.md` |
| F2 | Family-size distribution | show real diversity | family rank / size (log) | malicious | long singleton tail, not clones | `fig_family_size.png` | MAIN | ensure log-y labeled |
| F3 | Random vs family AUPRC | contribution C2 | model / AUPRC | AuthGuard,opcode-XGB,RF,blocklist | ~0.10 inflation; blocklist rescued | `fig_random_vs_family.png` | MAIN | keep |
| F4 | Mutation curve M0–M3 | contribution C3 (evasion) | tier / retained recall | rules,blocklist,opcode-XGB,AuthGuard | name-rule→0, struct flat-but-useless, learned graceful | `fig_mutation_curve.png` | MAIN | keep; label "structure-preserving" |
| F5 | Held-out robustness (aug) | contribution C3 (recovery) | condition {M3,+200%} / recall & FPR | AuthGuard-M0/-aug, XGB/-aug | +200% recovery, aug beats XGB-aug | `fig_advtrain_heldout.png` | MAIN | keep |
| F6 | Score distributions under padding | shortcut evidence (RQ5) | score / density | AuthGuard-M0 vs -aug @ M0,F100,F200 | aug keeps malicious high, benign low | `fig_advtrain_scoredist.png` | MAIN or App | keep; strong anti-shortcut visual |
| F7 | Original flooding sweep | motivate weakness | +% flood / retained | AuthGuard,opcode-XGB | M0 collapses at heavy pad (0.139) | `fig_mutation_volume.png` | APP | label as *M3-base compound* (G-VOL), distinct from F5 |
| F8 | AUPRC bars (LFO) | contribution C1 | method / AUPRC | all 8 | AuthGuard best discriminative | `fig_auprc.png` | APP (redundant w/ Table 2) | drop if space |
| F9 | Independent funnel | honesty/limitation | funnel stage / count | — | 7915→1 truly-novel | `fig_independent_funnel.png` | APP | keep only if independent-set discussed |

## Minimum non-redundant set for 8 pages (5 figures)
**F1 (architecture), F3 (random-vs-family), F4 (mutation curve), F5 (held-out robustness),
F6 (score distributions).** These carry C1(via F1+text), C2(F3), and C3(F4+F5+F6) with no
redundancy. Move F2/F7/F8/F9 to appendix; F8 is fully redundant with Table 2.

## Cross-figure protocol hygiene (must fix)
- F4 (G-MUT, in-sample threshold) and F5/F6 (G-ADV, val threshold) use **different threshold
  protocols**; do not place them on a shared axis or imply their recall numbers are comparable.
- F7 (G-VOL, M3-base flood, 0.139) and F5 (G-ADV, M0-base flood, 0.624) are **different
  conditions**; caption F7 as the compound worst case to avoid implying F5 recovered it.
- Every mutation figure caption: "structure-preserving," never "semantics-preserving."
