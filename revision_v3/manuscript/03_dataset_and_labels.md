# Dataset Provenance and Label-Source Explanation

## Dataset provenance

The canonical benchmark (`revision_v2/data/authguardbench_7702_v2.csv.gz`, PRIMARY_EVALUATION
population: 2,190 rows / 727 positive / 1,463 negative / 790 families) underlies all model
training in this project. Three additional, disjoint samples exist specifically for
independent evaluation, drawn without overlap from the same population and frozen before any
review began: Pilot (20 items), Gold-Dev (60 items), Gold-Test (150 items, frozen — never
resampled, verified by MD5 at every subsequent phase of this project). Family-disjointness
between Gold-Dev and Gold-Test is enforced and independently re-tested
(`test_family_isolation_between_gold_dev_and_gold_test`).

## Label-source explanation

Every evaluation item in this project carries up to three, always-separated label fields,
never conflated:

1. **`source_rule_label`** — a heuristic label computed during original dataset construction
   (Phase 1), used only as one comparison baseline, never as a training or evaluation target
   presented to the LLM labeling process.
2. **`llm_provisional_label`** (this manuscript's current metric source) — produced by the
   documented, two-stage protocol in `LLM_PROVISIONAL_LABELING_PROTOCOL.md`: (a) a
   deterministic evidence-collection stage (live verified-source checks against Sourcify v2
   and Blockscout v2; full bytecode decompilation via `evmole`; an automated guard-tracer
   that classifies each dispatched function's caller-restriction status as GUARDED/OPEN/
   AMBIGUOUS by tracing CALLER/ORIGIN opcode usage back to comparison instructions), followed
   by (b) LLM interpretation of that structured evidence into a SAFE/UNSAFE/UNCERTAIN label
   with a cited reason category. The LLM is never shown `source_rule_label`, any AuthGuard
   score, or sampling-stratum metadata (enforced structurally — the evidence-construction
   code path has no code that reads those columns).
3. **`human_final_label`** — reserved for independent human review, currently blank for
   every item in the dataset (verified:
   `test_human_final_label_never_populated_by_this_pipeline`). This manuscript's provisional
   results (Section 6) use `llm_provisional_label` exclusively and label every such result
   PROVISIONAL. `human_final_label` is never copied from `llm_provisional_label`
   (structurally impossible in the current pipeline — see the same test).

## Why LLM-provisional labels, honestly stated

Human review (via `Pilot_Code_Review.xlsx`, `Gold_Dev_Code_Review.xlsx`,
`Gold_Test_Code_Review.xlsx`) is in progress on its own timeline and is explicitly not
substitutable by an LLM's output. The provisional labels exist to let the technical pipeline
(model evaluation, retraining experiments, deployment benchmarking, cascade design) proceed
and be fully exercised in parallel, so that the moment human labels land, the entire
downstream pipeline can be rerun with one command
(`python3 revision_v3/run_reference_pipeline.py --label-source human_final`) rather than
requiring the pipeline itself to be built from scratch at that point.
