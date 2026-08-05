# Manuscript Workspace Status

This is a NEW workspace (`revision_v3/manuscript/`) and does **not** overwrite the currently
submitted manuscript (`revision_v2/manuscript/`). All metric placeholders in this draft are
sourced from LLM-provisional results and are marked accordingly; none are final-claim-ready.

> The original fusion/selective-policy draft sections predate the completed multi-path research
> search. The retained direction is documented in
> `reports/RESEARCH_ENDPOINT_AND_SUBMISSION_PLAN.md`; `01_title_and_abstract.md` has been updated,
> while the remaining section drafts are an audit trail until the untouched final evaluation.

## Two required wordings — use the correct one per context

**Current, accurate description of the review process already completed (Phase 3A/3B and
this pass's Parts 1-4):**

> "Evidence-grounded LLM provisional security review"

Use this whenever describing the labels currently backing any reported metric. Do **not**
call this process "human review," "expert annotation," or "ground truth" anywhere in the
manuscript while only LLM-provisional labels exist.

**Reserved wording for when human labels exist** (do not use until
`LLM_VS_HUMAN_AGREEMENT_REPORT.md` moves off `PENDING_HUMAN_LABELS`):

> "LLM-assisted collaborative human review with lead-author adjudication"

## Section files in this workspace

| File | Section | Status |
|---|---|---|
| `01_title_and_abstract.md` | Title options, abstract with provisional placeholders | Draft |
| `02_introduction_motivation.md` | Introduction, motivation, problem formulation, threat model | Draft |
| `02_related_work_and_novelty.md` | Direct EIP-7702, bytecode-graph, and selective-prediction novelty boundary | Draft |
| `03_dataset_and_labels.md` | Dataset provenance, label-source explanation | Draft |
| `04_architecture_and_training.md` | Sequence+dense architecture, training protocol | Draft |
| `05_evaluation_methodology.md` | Family-disjoint eval, corrected bootstrap, parameter-matched analysis, final robustness | Draft |
| `06_provisional_results.md` | Provisional reference-label methodology + Gold-Dev/Gold-Test/cascade results | Draft, metrics=PROVISIONAL |
| `07_temporal_and_deployment.md` | Temporal collection methodology, deployment evaluation | Draft, temporal=PARTIAL |
| `08_artifact_limitations_ethics_conclusion.md` | Artifact description, limitations, ethics, conclusion | Draft |

## What is explicitly NOT filled in

Per the stop condition, no "final human claims" appear anywhere in this workspace. Every
metric drawn from `results/llm_provisional/` carries an inline **[PROVISIONAL]** marker. The
manuscript is not to be submitted or finalized using these placeholders.
