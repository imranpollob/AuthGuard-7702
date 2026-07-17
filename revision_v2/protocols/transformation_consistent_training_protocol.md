# Transformation-Consistent Training Protocol

Frozen before training results. The manuscript remains unchanged until the joint attack/training
decision report is complete.

## Split and models

For outer test fold `f`, validation is frozen fold `(f+1) mod 5` and model fitting uses the
remaining three family-disjoint folds. All four regimes use the same 773-feature AuthGuard
XGBoost estimator and seeds 7702, 7703, and 7704.

1. **Clean:** M0 only.
2. **Ordinary augmentation:** all M0 sources plus M1, M2, F25, F50, and F100 variants of
   malicious sources, unweighted. This represents naive positive-only expansion.
3. **Source-balanced augmentation:** M0, M1, M2, F25, F50, and F100 for both classes, with each
   source's total training weight equal to one.
4. **Transformation-consistent hard training (TC-hard):** a clean seed model scores the
   source's bank `{M0,M1,M2,M3,F25,F50,F100,F200,M3F200}`. For malicious sources the lowest-score
   variant is selected; for benign sources the highest-score variant is selected. The final fit
   uses M0 plus the selected worst variant, with each source's total weight equal to one. This is
   an approximate per-source worst-case (minimax) objective, distinct from mean augmentation.

All generated banks use partition-isolated benign donors and persist segment provenance.

## Matched-FPR operating points

For each fold, regime, and seed, thresholds are selected only from clean validation negatives at
nominal FPR targets 1%, 5%, and 10%. Ties are handled conservatively so achieved validation FPR
does not exceed the target. Test metrics never affect threshold selection.

## Test conditions

- clean M0, both classes;
- donor-isolated F200, both classes;
- donor-isolated M3+F200, both classes; and
- the fixed adaptive-transfer set: random-search candidates generated against the held-out clean
  AuthGuard model for malicious rows, with clean M0 negatives. Defense models do not guide or
  modify this candidate set.

For each condition report AUPRC and recall/FPR at matched 1%, 5%, and 10% validation FPR.
Also report `benign_general` FPR under every selected threshold.

## Uncertainty and contribution decision

Seed 7702 is primary. Paired 10,000-replicate family-clustered bootstraps compare TC-hard with
clean and source-balanced training for AUPRC and recall at each operating point.

TC-hard is a separate Contribution 3 only if all hold against source-balanced augmentation:

1. clean AUPRC is non-inferior (95% CI lower bound for delta at least -0.01);
2. at least one of adaptive-transfer, F200, or M3+F200 AUPRC improves by at least 0.03 with CI
   excluding zero;
3. on at least one adversarial condition, recall improves by at least 0.05 with CI excluding zero
   at two or more matched-FPR targets; and
4. mean `benign_general` FPR increases by no more than 0.01 absolute at each target.

If these criteria fail, adaptive attack and training are merged into one robustness contribution,
and the dependence-aware EIP-7702 benchmark/evaluation protocol becomes Contribution 3.

