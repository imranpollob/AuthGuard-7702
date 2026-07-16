# Gate A Success Criteria — Conservative Terminal-Aware Dual-View (frozen BEFORE results)

Model: XGBoost (frozen v1 hyperparameters) on the dual-view representation:
full-view 773 features + restricted-view 773 features (features computed on the conservative
terminal-aware region) + trailing-byte volume + post-terminal byte ratio + terminal-instruction
statistics + full-vs-restricted feature differences on the dense block. Optional score
disagreement is a Gate B signal, not a Gate A feature.

Restricted region definition (conservative, purely syntactic): the byte prefix up to and
including the first linear-sweep occurrence of an unconditional terminator (STOP, RETURN,
REVERT, INVALID) that is NOT inside PUSH immediate data, computed by the frozen `disasm`
linear sweep on the pre-metadata region. No reachability, CFG, or dynamic-unreachability
claim is made or implied.

Trivial comparator (must be run first): the same XGBoost on 773 features computed on the
bytes before the first STOP only ("first-STOP heuristic").

## Success requires ALL of the following (evaluated on task-aligned v1, stored folds, v2 thresholds):

1. Flooding improvement: recall under at least one of {pure-M0 F200, compound M3+F200}
   improves over the corresponding full-view AuthGuard model by ≥ 0.10 absolute (same
   training regime: M0-trained compared with M0-trained, augmented compared with augmented),
   with the paired family-clustered 95% CI of the difference excluding 0.
2. Clean tolerance: family-grouped clean G-DET AUPRC degradation ≤ 0.02 vs the corresponding
   full-view model (fold-mean).
3. Benign control: benign_general FPR at the frozen operating threshold increases by
   ≤ 0.01 absolute vs the corresponding full-view model.
4. Consistency: the flooding improvement in (1) is positive in ≥ 4 of 5 outer folds.
5. Beats the trivial baseline: criterion (1)'s improvement also holds (≥ 0.05 absolute,
   CI excluding 0) against the first-STOP heuristic under the same condition, OR the
   dual-view model strictly dominates the heuristic on (clean AUPRC, flooding recall).

If ANY criterion fails, Gate A fails: results are retained internally
(`revision_v2/results/gateA/`), reported in the phase report, and the method is NOT added to
the manuscript. Terminology if passed: "conservative terminal-aware dual-view representation".
