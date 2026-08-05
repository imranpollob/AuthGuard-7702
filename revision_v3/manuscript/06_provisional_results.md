# Provisional Results and Claim Boundary

**Every label-dependent number in this section is provisional. None may be promoted to the
abstract or contribution list until the human-final and post-cutoff evaluations pass.**

## DCRG extraction coverage

The `dcrg-1.1` extractor completed on all 1,665 unique runtimes representing the 2,190-row
primary population, with zero analyzer crashes. Bounded semantic coverage was `COMPLETE` for
517 unique runtimes (670 samples, 30.6%) and `PARTIAL` for 1,148 runtimes (1,520 samples,
69.4%). This is itself an operational result: silently treating incomplete traversal as
absence of risk would affect most of the benchmark. Accordingly, the selective policy can
emit `LOW_OBSERVED_RISK` only for the complete-coverage subset.

On an isolated CPU pass over all 1,665 unique runtimes, bytecode-to-DCRG extraction had median
latency 49.9 ms, p95 812.7 ms, p99 1.77 s, and maximum 2.64 s; peak process RSS was 166,160
KiB. No analysis crashed. These timings measure bounded semantic extraction separately from
neural inference, and fast termination with `PARTIAL` coverage remains a defer condition.

## Family-held-out primary evaluation against inherited labels

Pooling each seed's out-of-fold predictions across the 5 family-disjoint test folds, the
sequence+dense baseline obtained mean AUPRC 0.902 and recall 0.844 at validation-derived
nominal 5%-FPR thresholds. DCRG-only obtained AUPRC 0.954 and recall 0.979. The pre-specified
DCRG+sequence noisy-OR obtained AUPRC 0.958, recall 0.933, and observed FPR 0.046. The corrected
10,000-replicate paired family-clustered bootstrap gives fusion-minus-sequence AUPRC +0.056
(95% CI +0.014 to +0.111) and recall +0.088 (+0.048 to +0.137), while the FPR interval crosses
zero. Fusion is not distinguishable from DCRG alone (AUPRC +0.004, -0.010 to +0.025); its
recall point estimate is lower by 0.046 and that interval also crosses zero.

These are **engineering diagnostics, not independent validation**. The inherited primary
labels partly encode static-analysis behavior that overlaps the DCRG evidence, so strong DCRG
performance may measure faithful reconstruction of the label-generating rule. It cannot by
itself establish semantic safety, maliciousness, or generalization to post-cutoff families.

## DCRG representation ablation

Using the same folds and seeds, full DCRG improves pooled AUPRC over a capability-only CFG
summary by +0.0129 (95% paired family-bootstrap CI +0.0019 to +0.0269) on the inherited labels.
However, it does not improve over an untyped guard summary (-0.00004, -0.00219 to +0.00311),
and removing the three protocol-actor/authority-match features changes AUPRC by only +0.00040
(-0.00097 to +0.00325). Thus, the current data support added guard-aware context over bare
capability counts, but do **not** validate the claimed benefit of individual guard types or
authority-relative actors. Historical rows lack authorizing-EOA context, making the latter a
target for the real authority/delegate-pair evaluation rather than a current result.

At the same operating policy, the coverage-aware decision layer was actionable on 52.6% of
outer-test items and deferred 47.4%. Among items assigned `LOW_OBSERVED_RISK`, the mean
positive-label rate was 7.3% with high cross-run variability. This output must therefore retain
the qualified name `LOW_OBSERVED_RISK`; it must never be shortened to `SAFE`.

On 30 documented legitimate deployments, the current fusion policy produces 14 majority
`WARN` and 16 `DEFER`; all 30 have partial bounded-analysis coverage. This negative result
invalidates a broad low-false-warning claim. A separate leave-one-project-out experiment tests
whether adding other project families as benign development controls can improve generalization
without scoring a project using itself or a known related benchmark family. It produces the
same 14 `WARN` / 16 `DEFER` distribution, so the present control augmentation does not repair
the false-warning problem.

## Leakage-repaired Opus-5 reference-label evaluation

Gold-Dev and Gold-Test were sampled from the canonical benchmark. The previous result files
incorrectly ensembled all five fold checkpoints, three of which had trained on each sampled
family. They have now been rescored using only each family's held-out-test checkpoint.

On Gold-Dev (40 binary labels; 20 `UNCERTAIN` excluded), AUPRC was 0.924 for
`authguard_sequence_dense`, 0.948 for the sequence-only reference, 0.936 for the
parameter-matched flat CNN, and 0.955 for the original flat CNN. At the item-specific frozen
thresholds, sequence+dense recall was 0.355 with observed FPR 0.000.

On Gold-Test (108 binary labels; 42 `UNCERTAIN` excluded), AUPRC was 0.896 for
sequence+dense, 0.920 for the sequence-only reference, 0.908 for the parameter-matched flat
CNN, and 0.916 for the original flat CNN. Sequence+dense recall was 0.443 at observed FPR
0.100. The previously selected fine-tuned provisional model is excluded from the independent
ranking because it has not been retrained with all Gold-Test families removed; its old score
is retained only as an explicitly invalid diagnostic.

The source-derived labels remain LLM-provisional despite the checkpoint repair. These tables
may diagnose pipeline behavior, but the paper's acceptance case must come from adjudicated
human labels and provenance-safe post-cutoff controls.

## Unlabeled post-cutoff authority-context extraction

From the frozen authoritative Ethereum later-time checkpoint, 734 authorization tuples yielded valid
recovered signer/delegate pairs and 708 of those delegates had runtime code at the first
observed block. Authority-aware DCRG extraction completed without analyzer errors over 673
unique runtimes: 222 pairs had `COMPLETE` and 486 had `PARTIAL` bounded coverage. Hardcoded
caller checks matched the recovered authorizing EOA in 27 pairs and differed in 295; 28 pairs
contained a recognized ERC-4337 EntryPoint guard. Thus, real authority context makes the typed
features nontrivial, unlike the historical benchmark where authority is unknown.

These are **unlabeled representation counts, not accuracy evidence**. A fixed score-blind
sample of 150 from 564 candidate unseen exact-runtime families is frozen, but all project-family
assignments and human labels remain unresolved. No post-cutoff model score is produced until
those families are audited, every related canonical/control family is held out, all contributing
models are retrained, and dual-review/adjudicated labels are complete.
