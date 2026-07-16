# Uncertainty Protocol v2 (frozen)

Seeds: blake2b(f"7702:{cohort}:{target}") as in `paper_build/statistics/family_clustered_bootstrap.py`.
Replicates: 10,000 percentile bootstrap.

## Family-clustered bootstrap (primary uncertainty)

- Unit of resampling: frozen test family (family_id at 0.85), sampled with replacement.
- Every observation of a sampled family is retained (sampled k times → weight k).
- Pooled across outer folds: each corpus row appears exactly once as a test observation under
  leave-family-out, so pooled per-row test scores form one prediction per row; bootstrap runs
  over families of the pooled frame.
- Paired comparisons resample the SAME families for both models (paired design).
- AUPRC under resampling uses sample_weight = family multiplicity.
- Reported: point estimate, 95% percentile CI, replicate summary (mean/std); replicate
  distributions stored when < 1 MB, otherwise summarized.

## Targets

1. AuthGuard G-DET-v2 AUPRC (primary task).
2. Paired ΔAUPRC: AuthGuard − strongest bytecode baseline (chosen by Phase 3A fold-mean
   AUPRC, identified before reading the CI).
3. AuthGuard random-split minus family-grouped AUPRC (random diagnostic scores pooled the
   same way; families defined by the frozen assignment regardless of the split that produced
   the scores).
4. Donor-isolated G-ADV-v2 changes (Δrecall, ΔFPR at M0/M3/F200/compound; ΔAUPRC at F200 and
   compound), paired AuthGuard-M0 vs AuthGuard-aug.
5. Compound-condition comparisons (aug vs M0-trained; dual-view vs full-view if Gate A runs).

## Separation of uncertainty layers

Fold means ± fold std (ddof=0) describe split-to-split variation; seed std (5 seeds)
describes optimizer noise; family-clustered CIs are the headline inferential statement.
The three are never mixed in one number and each table labels which it shows.
