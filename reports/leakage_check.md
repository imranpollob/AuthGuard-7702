# Leakage Validation Report

Run `v2`. Produced by `dataset_pipeline/scripts/12_build_gold_and_splits.py`; values read from
`data/gold_dataset/v2_gold_summary.json`.

## Split unit

The atomic split unit is a **split group**: the transitive closure of

    exact runtime-bytecode SHA-256  →  opcode-similarity family (Jaccard ≥ 0.85)  →  resolved
    proxy implementation address

computed with union-find. Identical bytecode, similar bytecode, and a proxy together with its
resolved implementation therefore always land in the same split. 306 gold contracts form
**223 split groups**; 1 proxy→implementation link was contributed by the resolved-proxy stage.

## Results

| Check | Violations |
|---|---:|
| Similarity families crossing splits | **0** |
| Exact bytecode hashes crossing splits | **0** |
| Split groups crossing splits | **0** |

## Temporal separation

A hard cutoff block is used rather than ordering groups by their earliest member. Ordering by
earliest member was tried first and **failed**: a group whose first member is early can contain
much later members, which put 
development contracts after the test set began. The test split is therefore restricted to groups
lying entirely at or after the cutoff.

| | |
|---|---|
| Temporal cutoff block | 25,660,356 |
| All test contracts observed at/after cutoff | **yes** |
| Test block range | 25,660,901 – 25,694,941 |
| Train block range | 25,595,134 – 25,692,610 |
| Val block range | 25,624,609 – 25,692,511 |
| Groups straddling the cutoff, kept in development | 6 |
| Development contracts observed after the cutoff | 11 |

Every test contract was first observed at or after the cutoff, and no test contract shares a
family, exact bytecode, or proxy implementation with any development contract. 11 development
contracts were first observed after the cutoff because their family began before it; keeping
them in development (never in test) is the leakage-safe direction, and the count is reported
rather than suppressed. The strict statement "every test contract is later than every
development contract" is therefore **false**, while "no test contract precedes the cutoff and no
family is shared" is **true**.

## Model-selection hygiene

- Thresholds at 1/5/10% FPR are derived from validation negatives only.
- Isotonic calibration is fitted on validation only.
- The model used for the decision-strategy comparison was selected by **validation** AUPRC
  (`C_pretrain_finetune`, val AUPRC 0.289 vs 0.242 / 0.226).
- The test split was read once, to produce the reported metrics.

## Caveat on scale

The test set is small: 51 contracts, 44 decidable, 9 positive. Leakage control is sound, but the
statistical power is very low — see `reports/limitations.md`.
