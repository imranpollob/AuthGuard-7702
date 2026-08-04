# Title Options

1. AuthGuard-7702: Coverage-Aware Pre-Authorization Screening of EIP-7702 Delegates
2. Screening EIP-7702 Delegates: Contextual Risk Graphs, Bytecode Models, and Explicit Deferral
3. From Bytecode Scores to Selective Decisions for EIP-7702 Authorization Risk

## Abstract (provisional metric placeholders)

EIP-7702 lets an externally-owned account execute delegate-contract code in the account's own
storage, balance, and identity context. A wallet must therefore decide whether to authorize a
delegate before transaction history, reputation, or verified source may be available. We
present AuthGuard-7702, a coverage-aware pre-authorization screener that combines a compact
opcode-sequence model with a typed Delegation-Context Risk Graph (DCRG). DCRG separates
self-call, signature, stored-authority, fixed-address, caller-supplied, and `tx.origin` guards;
records unguarded capabilities; and makes incomplete analysis explicit. A fixed monotone fusion
feeds a selective policy that returns `WARN`, `LOW_OBSERVED_RISK`, or `DEFER`, rather than
equating a negative classifier output with proof of safety.

On the frozen 2,190-item, 790-family engineering benchmark, the DCRG extractor completed for
all 1,665 unique runtimes but achieved complete bounded coverage for only 30.6% of samples,
motivating explicit deferral. **[PROVISIONAL inherited-label result: across 5 family-held-out
folds and 3 seeds, pooled out-of-fold DCRG+sequence fusion obtains AUPRC 0.958 versus 0.902 for
the sequence model and recall 0.933 versus 0.844 at validation-derived nominal 5%-FPR
thresholds. A paired family bootstrap supports improvement over the sequence model, but not
over DCRG alone.]** Because
these inherited labels partly encode static-analysis behavior, this comparison is treated as
an engineering diagnostic rather than independent semantic validation. The submission claim
must be replaced or confirmed with adjudicated human labels and post-cutoff project-family
controls before finalization.

**The bracketed performance sentence is a placeholder pending independent human review,
paired uncertainty, and post-cutoff evaluation. It must not appear as an accepted result in a
submission until those gates pass.**
