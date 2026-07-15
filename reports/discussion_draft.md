# Discussion (Paper §8) — outline + draft

For each topic: safe argument · evidence · qualification · statement-to-avoid.

1. **Principal findings.** A decompiler-free pre-signing screen separates rule-labeled malicious
from rule-silent delegates at 0.856 AUPRC / 3.4 ms; the gains survive family holdout, and
augmentation partially restores robustness to heavy padding. *Evidence:* `detection_results.json`,
`advtrain_results.json`. *Avoid:* "solves EIP-7702 malware detection."

2. **Effect of family grouping.** Family holdout is the honest protocol; it costs ~0.10 AUPRC
vs random. *Evidence:* 0.856 vs 0.961. *Qualify:* threshold 0.85, sensitivity-tested. *Avoid:*
"prior work is wrong."

3. **Random-split inflation.** The blocklist rising 0.324→0.558 shows the mechanism is
near-duplicate memorization. *Avoid:* claiming a universal inflation constant.

4. **Original mutation weakness.** Name-match and hashing collapse (0.038→0.000; 0.000);
learned model degrades gracefully on M1–M3 (0.588 retained). *Qualify:* structure-preserving,
not EVM-verified. *Avoid:* "robust to evasion."

5. **Adversarial-training improvement.** Significant held-out +200% recovery (0.624→0.790, CI
[0.131,0.193]) that generalizes to singleton families (0.655→0.850). *Avoid:* "recovers the
0.139 collapse" — that compound condition was not retested.

6. **Clean/robustness trade-off.** Augmentation raises clean AUPRC (+0.019) and lowers benign
FPR (0.192→0.164) at a small clean-recall cost (−0.032, CI excludes 0). *Avoid:* "free lunch."

7. **No padding shortcut.** Aug benign FPR is below M0 at every severity; a shortcut would raise
it. *Evidence:* T6 + score-distribution figure. *Avoid:* "immune to padding."

8. **Residual 27.5% FP under heavy padding.** Honestly reported; benign FPR still climbs with
padding for aug (0.158→0.266). *Avoid:* burying it.

9. **Why partial not full.** Recovery holds on isolated held-out axes but the compound
M3+heavy-flood is untested and absolute FP is high, so robustness is improved-not-achieved.

10. **Label circularity.** All 793 positives are USENIX-rule-derived; the model may inherit the
rule's blind spots. *Mitigation:* M3 removes the name footprint yet detection persists.

11. **Insufficient independent validation.** Independent sourcing yielded 1 confirmed novel
delegate → INSUFFICIENT DATA. *Avoid:* using it as superiority evidence.

12. **Weak / PU negatives.** benign_cleared is rule-silent, ≤8.1% contaminated; treated as a
positive-unlabeled-flavored negative, never "verified clean."

13. **USENIX system vs our approximations.** We reimplement the shipped rule's *facts* as
baselines (sensitive-name approximation, external-call over-approximation); we did **not** run
the full Gigahorse/Datalog pipeline. *Avoid:* "we beat the USENIX detector."

14. **Mutation-equivalence limits.** Opcode-skeleton/control-flow identity verified; full EVM
semantic equivalence not established. Hence "structure/attack-capability-preserving."

15. **Deployment.** Fits a wallet pre-sign hook or CLI; needs `eth_getCode` (or cache) and a
frozen model+threshold. *Qualify:* network fetch latency excluded from the 3.4 ms.

16. **Runtime.** Measured 3.4 ms; decompiler comparison `[NOT MEASURED]` → framed as a
deployment concern, not a speedup claim.

17. **Attacker adaptation.** An adaptive attacker can target the learned features (e.g., heavier
flooding, control-flow obfuscation); our robustness is scoped to the tested transformation
family only.

18. **External validity.** Seven chains, one time snapshot, one label source; cross-chain and
temporal generalization untested.

19. **Reproducibility.** Fixed seeds, deterministic clustering (blake2b), frozen splits, leakage
assertions logged, auto-generated result manifests.

20. **Ethics.** No victim/signer data (stripped); read-only on-chain queries only; the tool is
defensive (pre-sign warning), and mutation code is for robustness evaluation, not weaponization.

21. **Future work.** See `next_improvement_recommendation.md`.

**Future-work paragraph (draft).** The clearest next step is reachability-aware feature
extraction: distinguishing executable from appended-unreachable regions before featurizing would
directly attack the residual dead-code-flooding false positives, and, combined with the existing
augmentation, is the most likely route to turn PARTIALLY RECOVERS into a robust screen.
Complementary directions — an independent post-USENIX authorization-list dataset to break label
circularity, and selective escalation to a heavier analyzer under uncertainty — are valuable but
depend on external data or added system surface, so they are secondary.
