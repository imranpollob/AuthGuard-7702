# Revision v3 strengthening notes

## Completed source corrections

- Corrected the compact Transformer budget from 2,048 to 1,024 positions in both
  protocol prose and the configuration table.
- Corrected the maximum primary-benchmark program from an erroneous 16,081-opcode
  statement to 10,795 opcode tokens (16,136 runtime bytes).
- Added the concrete long-context prevalence: 712/2,190 primary delegates (32.5%) exceed
  the 2,048-opcode Flat CNN/BiGRU view.

## Completed manuscript integration

The full long-context verifier passed before the abstract, contribution statement,
controlled-method paragraph, result tables, discussion, limitations, and conclusion
were replaced.  The manuscript now promotes the 30,050-parameter attention model and
frames it as a clean--robustness tradeoff rather than as universally superior.

## Evidence packet to use

- `revision_v2/results/long_context_ablation_v3/PAPER_RESULT_PACKET.md`
- `revision_v2/results/long_context_ablation_v3/paper_tables_v3.tex`
- `revision_v2/results/long_context_ablation_v3/FOLD_CLUSTERED_CONTRIBUTION_DECISION.md`
- `revision_v2/results/long_context_ablation_v3/fold_clustered_contrasts.csv`
- `revision_v2/results/long_context_ablation_v3/length_stratified_summary.csv`
- `revision_v2/results/long_context_ablation_v3/capacity_audit.csv`

The controlled coverage, attention, and hierarchy gates determine claim wording. The
full AuthGuard-Seq row is a transfer check and must not be presented as a
parameter-matched causal comparison.

## Verified long-context v3 outcome

Full verification passed for 90 model/seed/fold units and 78,840 predictions.

- Clean AUPRC: 16K flat control 0.936; 16K controlled attention 0.918; retrained
  AuthGuard reference 0.914.
- Learned attention versus mean pooling is supported on clean inputs:
  +0.0386 AUPRC, fold-stratified family-bootstrap 95% CI [0.0072, 0.0643].
- Clean hierarchy versus the matched 16K flat control is not supported:
  -0.0181, CI [-0.0400, 0.0182].
- The 2K-to-16K attention coverage effect is inconclusive on clean inputs:
  +0.0152, CI [-0.0028, 0.0300].
- Under cap-correct F200, controlled attention reaches 0.908 AUPRC and is supported over
  the 16K flat control by +0.0980, CI [0.0590, 0.1544], and over mean pooling by
  +0.1800, CI [0.1348, 0.2316].
- The retrained current AuthGuard reference reaches 0.894 F200 AUPRC. The manuscript's
  old 0.920 headline came from transformed rows that bypassed the declared 16K cap and
  must be replaced.

The v3 result supports learned chunk aggregation as a robustness mechanism under severe
flooding. It does not support universal clean superiority of hierarchy or a claim that
increased attention-model coverage alone explains performance.

## Confirmatory model branch

Fold 0 is explicitly development-only for the compact AuthGuard-MSP architecture frozen
in `revision_v2/protocols/multiscale_confirmation_v1.md`. Manuscript integration follows
these rules:

- If clean AUPRC is supported over the 16K attention control and the 16K flat control on
  untouched folds 1--4, AuthGuard-MSP becomes the architecture contribution and its
  confirmatory result is reported separately from development.
- If it improves only over attention-only pooling, it is reported as evidence for
  multi-statistic aggregation but not as superiority over the flat budget control.
- If confirmation is inconclusive or negative, the current model is not replaced and no
  further architecture is tuned on folds 1--4.

The confirmation verifier passed for 12 model/seed/fold units and 10,464 predictions.
The frozen multi-statistic model reached 0.949 clean AUPRC on folds 1--4, but its clean
AUPRC differences from the attention and flat controls were inconclusive.  It was
significantly worse than attention under F200 by 0.107 AUPRC, CI
[-0.145, -0.073].  The manuscript therefore reports the negative confirmation and
retains the simpler attention model, as predeclared.

## Operational evidence

The operational-control verifier passed for 11,955 external predictions, 75
qualitative-control predictions, and 500 latency rows.  The promoted checkpoint has
30,050 parameters, occupies 125,300 bytes, and has 2.942 ms median complete-local-path
latency with one PyTorch thread.  At its nominal 5% FPR threshold, the observed external
FPR is 0.059 +/- 0.007 across checkpoints.  The manuscript keeps the five curated
controls qualitative and states the external-distribution limitations.

## First-STOP review correction

The manuscript retains full linear-sweep tokenization and adds the bounded semantic-audit
result: post-first-STOP code executed in 92/100 fixed calls, while truncation preserved the
recorded fingerprint in only 22/100.  This supports rejecting first-STOP truncation as
canonicalization; it does not support the review's proposed recall-collapse or
semantics-preserving attack claim.
