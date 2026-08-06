# Reproducibility

All commands run from the repository root with system `python3` (3.12.12).
Config: `configs/dataset_pipeline.json` (`run_id`, chains, block ranges, seed 7702, paths).

## Environment

```bash
python3 -m pip install numpy pandas scikit-learn xgboost matplotlib openpyxl \
                       rlp eth-keys eth-utils cbor2 pycryptodome coincurve
```

`coincurve` matters: without it `eth_keys` silently falls back to a pure-Python backend and
signer recovery is ~50× slower (~2.7 h vs ~3 min for 1.34 M authorizations).

## Pipeline

```bash
# Stage 2 — collect + recover signers + fetch bytecode (network; public RPC, no keys)
python3 dataset_pipeline/scripts/01_collect_authorizations.py
python3 dataset_pipeline/scripts/02_recover_signers_and_bytecode.py

# Stage 3 — exact-bytecode and similarity families
python3 dataset_pipeline/scripts/03_build_families.py

# Stage 4 — evidence packages, then reachability/guard-dominance evidence
python3 dataset_pipeline/scripts/04_extract_evidence.py          # network: Sourcify
python3 dataset_pipeline/scripts/04b_add_reachability_evidence.py # offline, ~8 min
python3 dataset_pipeline/scripts/04c_resolve_proxy_targets.py     # network; resumable

# Stage 5 — rubric v3 labelling (offline, deterministic)
python3 dataset_pipeline/scripts/05c_llm_review_v3.py

# Stage 6 — queues (human input required)
python3 dataset_pipeline/scripts/06b_build_review_queues.py
python3 dataset_pipeline/scripts/06c_build_pilot_queue.py

# Stages 7-10 — after human review is filled in
python3 dataset_pipeline/scripts/11_validate_reviews.py
python3 dataset_pipeline/scripts/12_build_gold_and_splits.py
python3 dataset_pipeline/scripts/13_experiments.py
python3 dataset_pipeline/scripts/14_decision_strategies.py
python3 dataset_pipeline/scripts/15_artifacts.py
```

Validation utilities (independent of the pipeline):

```bash
python3 dataset_pipeline/validation/validate_signer_recovery.py --sample-size 150
python3 dataset_pipeline/validation/investigate_selfdestruct.py
python3 dataset_pipeline/validation/validate_r1_rule.py
```

## Determinism

| Component | Basis |
|---|---|
| Sampling / bootstrap | seed 7702 (`configs/dataset_pipeline.json`) |
| XGBoost | `seed=7702`, fixed params, 150 rounds |
| Family clustering | blake2b-seeded k-grams, exact Jaccard, deterministic union-find |
| Rubric v3 | pure function of the evidence package |
| Split assignment | deterministic given the frozen review + cutoff rule |

Stages that touch the network (01, 02, 04, 04c) depend on live chain state and public RPC
availability; they are checkpointed/cached and resumable. Everything downstream of
`data/collected_delegates/` is fully offline and reproducible.

## Frozen hashes

| Artifact | SHA-256 |
|---|---|
| Frozen human review | `8a8ad2562bdd612399d53e224e65c0815ec72b24b140c4388907507fbf2b3f97` |
| Split manifest | `f87cf8f419e7fede843b50b47182851f2250ddd62e3e17321ef99b8cd9eb64de` |

Verify with:

```bash
sha256sum data/human_reviews/frozen/v2_gold_review_FROZEN.csv
sha256sum data/split_manifests/v2_split_manifest.csv
```
