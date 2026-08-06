# Dataset Card — AuthGuard-7702 gold dataset (run `v2`)

## Summary

306 EIP-7702 delegate contracts observed on Ethereum mainnet (blocks 25,595,577–25,695,577),
labelled for whether a reachable dangerous capability is protected by an authorization check.
Drawn from a complete collected population of 760 distinct delegates (752 screenable).

## Labels

| Label | Meaning | n |
|---|---|---:|
| R1 | Concrete reachable dangerous operation whose authorization protection is missing/inadequate, under COMPLETE coverage | 48 |
| R2 | Concrete potentially dangerous path, one specific unresolved dependency blocks the decision | 10 |
| B | Reachable capabilities exist but are protected, under sufficiently complete analysis | 149 |
| U | Evidence too incomplete to decide (unresolved proxy target, insufficient control-flow coverage) | 99 |

`U` and `NOTSCREENABLE` are defer classes, not negatives.

## Provenance

Bytecode evidence → rubric v3 (`claude-opus-5`, deterministic decision procedure) → **human
ratification of all 300 reviewed runtimes (300 accepted, 0 changed)** → propagation to 6
contracts with identical runtime bytecode. **Labels are rubric output ratified by one reviewer,
not independent human labels; agreement is 100% by construction and kappa is not computable.**

## Splits

Family-disjoint (exact bytecode ∪ similarity family ∪ resolved proxy implementation) and
temporally cut at block 25,660,356. Train 193 / val 62 / test 51. Zero families, exact hashes, or
split groups cross splits.

## Intended use

Evaluating bytecode-only pre-authorization screening of EIP-7702 delegates, and studying the
coverage ceiling of static screening. **Not** suitable as ground truth for maliciousness: labels
describe protection of capabilities as visible in bytecode, not intent, exploitability, or
real-world harm.

## Known limitations

Small (44 decidable test contracts, 9 positive); single chain; ~2-week window; single reviewer
with 100% acceptance; 43% of the screenable population is undecidable (U). See
`reports/limitations.md`.

## Files

| File | Contents |
|---|---|
| `data/gold_dataset/v2_gold_reviewed.csv` | gold labels + provenance + bytecode |
| `data/gold_dataset/v2_notscreenable.csv` | 8 delegates with no retrievable bytecode |
| `data/gold_dataset/v2_huang_weak_labels.csv` | Huang/USENIX rule labels (2,450 rows) |
| `data/split_manifests/v2_split_manifest.csv` | frozen split assignment (SHA-256 `f87cf8f4…`) |
| `data/human_reviews/frozen/v2_gold_review_FROZEN.csv` | immutable review record (SHA-256 `8a8ad256…`) |
