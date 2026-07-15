# AuthGuard-7702 — Executive Summary

**Problem (one sentence).** Decide, from a delegate contract's bytecode alone and before the
user signs an EIP-7702 authorization, whether granting it authority over their account is
dangerous.

**Solution (one sentence).** AuthGuard-7702 is a decompiler-free, bytecode-only gradient-boosted
screen, evaluated under a frozen leave-family-out protocol and hardened with source-balanced
structure-preserving augmentation, that scores a contract in ~3.4 ms.

**Three contributions.**
1. The first pre-signing, decompiler-free bytecode screen for EIP-7702 delegates (0.856 AUPRC under family holdout, 3.4 ms/contract).
2. A frozen, deterministic family-grouped evaluation showing random splits inflate AUPRC by ~0.10 and that leave-family-out is materially harder (blocklist 0.324→0.558 exposes the memorization).
3. A verified structure-preserving mutation benchmark + leakage-safe augmentation that significantly improves robustness to a held-out +200% flooding severity (recall 0.624→0.790, paired 95% CI [0.131, 0.193]), generalizing to singleton families (0.655→0.850), without clean-data cost or a padding shortcut.

**Strongest result.** The evasion + augmentation story: the deployed rule's discriminating
components collapse to zero under a byte-level rename while the learned model degrades
gracefully, and augmentation then recovers most of the heavy-flooding loss with paired
confidence intervals excluding zero and benign false positives that *fall* rather than rise.

**Strongest limitation.** Robustness is improved, not achieved — a residual 27.5% benign
false-positive rate under the heaviest padding, and the compound worst case (mutation + heavy
flooding together) was left untested by the leakage-safe design. Compounding this: all positives
are USENIX-rule-derived (circular labels), and independent prospective sourcing yielded only one
confirmed novel delegate (INSUFFICIENT DATA).

**Project status.** Tool and all four experiment families (detection, mutation/evasion,
adversarial training, independent validation) are implemented, reproduced with fixed seeds, and
leakage-asserted. All flagged numerical discrepancies are reconciled (differences trace to
train-set size, threshold-selection protocol, and mutation-base condition — never contradictions).

**Recommended next experiment.** Reachability-aware feature extraction: mask provably-unreachable
appended bytecode before featurization to structurally remove the dead-code-flooding evasion,
then re-run the frozen adversarial-training evaluation. No external data; ~2–3 days; directly
upgrades contribution 3 and rebuts the residual-false-positive objection.

**Venue.** ICTAI 2026 tools track is appropriate *if* framed as methodology + tool (leakage-safe
family-grouped evaluation and structure-preserving evasion robustness), since the estimator is
standard; a blockchain-security venue would value the domain more but scrutinize label
circularity and expect the full USENIX-pipeline comparison.
